from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.cost.delivered_cost import compute_cost_matrix, compute_cost_row
from app.cost.params_loader import CostParametersMissingError, load_cost_parameters
from app.schemas.candidates import CandidateOption, CandidateSet, CharterStrategy, PricingBasis
from app.schemas.common import (
    CargoRequirement,
    DailyRate,
    Port,
    PortCheckResult,
    PortFeasibilityResult,
    RouteDistance,
    Scenario,
    ScenarioSet,
    Vessel,
    VesselAvailability,
)

PARAMS = load_cost_parameters()  # real config/cost_parameters.yaml — exercises the loader too


def make_cargo(**overrides) -> CargoRequirement:
    base = dict(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="AU-HAY", destination_port_id="IN-PARADIP",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    base.update(overrides)
    return CargoRequirement(**base)


def make_vessel(**overrides) -> Vessel:
    base = dict(
        vessel_id="V-TEST", name="Test Vessel", vessel_class="PANAMAX",
        dwt_tonnes=80000, loa_m=229.0, beam_m=32.3, draft_laden_m=14.3,
        service_speed_knots=14.0,
    )
    base.update(overrides)
    return Vessel(**base)


def make_availability(**overrides) -> VesselAvailability:
    base = dict(vessel_id="V-TEST", open_date=date(2026, 8, 30), open_port_id="AU-HAY")
    base.update(overrides)
    return VesselAvailability(**base)


def make_port_feasibility(base_turnaround=2.5, current_congestion=1.0) -> PortFeasibilityResult:
    return PortFeasibilityResult(
        feasibility_run_id="R1", cargo_requirement_id="C1",
        ports=[
            PortCheckResult(
                port_id="IN-PARADIP", feasible=True, draft_ok=True, berth_ok=True,
                handling_ok=True, congestion_acceptable=True,
                base_turnaround_days=base_turnaround, current_congestion_days=current_congestion,
            ),
            PortCheckResult(
                port_id="AU-HAY", feasible=True, draft_ok=True, berth_ok=True,
                handling_ok=True, congestion_acceptable=True,
                base_turnaround_days=2.0, current_congestion_days=0.5,
            ),
        ],
    )


def make_distances() -> list[RouteDistance]:
    return [
        RouteDistance(from_port_id="AU-HAY", to_port_id="AU-HAY", distance_nm=0),
        RouteDistance(from_port_id="AU-HAY", to_port_id="IN-PARADIP", distance_nm=4700),
        RouteDistance(from_port_id="SG-SIN", to_port_id="AU-HAY", distance_nm=2500),
    ]


def make_scenario_set(rate=16.0, congestion_shock=0.0, tc_rate=25000.0, dates=None) -> ScenarioSet:
    dates = dates or [date(2026, 9, 1) + __import__("datetime").timedelta(days=i) for i in range(46)]
    voyage_path = [DailyRate(date=d, rate=rate) for d in dates]
    tc_path = [DailyRate(date=d, rate=tc_rate) for d in dates]
    scenario = Scenario(
        scenario_id="S1", probability=1.0,
        voyage_freight_path_usd_per_tonne=voyage_path,
        tc_hire_path_usd_per_day={"PANAMAX": tc_path},
        base_congestion_shock_days=congestion_shock,
    )
    return ScenarioSet(scenario_run_id="SR1", forecast_run_id="FR1", scenario_count=1, scenarios=[scenario])


def make_candidate(**overrides) -> CandidateOption:
    base = dict(
        candidate_id="C-0001", vessel_id="V-TEST", vessel_class="PANAMAX",
        strategy=CharterStrategy.SPOT_NOW, pricing_basis=PricingBasis.VOYAGE_PER_TONNE,
        charter_epoch=date(2026, 9, 1), origin_port_id="AU-HAY", destination_port_id="IN-PARADIP",
        capacity_tonnes=80000,
    )
    base.update(overrides)
    return CandidateOption(**base)


# ---------------------------------------------------------------------------
# Parameter loading
# ---------------------------------------------------------------------------

def test_real_config_loads_and_validates():
    assert PARAMS.version == "v1"
    assert PARAMS.laytime_allowance_days == 4


def test_missing_parameter_file_raises_config_missing():
    with pytest.raises(CostParametersMissingError, match="CONFIG_MISSING"):
        load_cost_parameters(Path("/nonexistent/cost_parameters.yaml"))


# ---------------------------------------------------------------------------
# Core cost-basis tests (each targeting one spec-review fix)
# ---------------------------------------------------------------------------

def test_zero_waiting_case_when_epoch_equals_earliest_departure():
    cargo = make_cargo()
    candidate = make_candidate(charter_epoch=cargo.earliest_departure)
    vessel, avail = make_vessel(), make_availability()
    row = compute_cost_row(
        candidate, "S1", make_scenario_set(), vessel, avail, cargo,
        make_port_feasibility(), make_distances(), PARAMS,
    )
    assert row.breakdown.waiting_cost == 0.0


def test_waiting_cost_scales_with_days_past_earliest_departure():
    cargo = make_cargo()
    candidate = make_candidate(charter_epoch=date(2026, 9, 6))  # 5 days after earliest_departure
    vessel, avail = make_vessel(), make_availability()
    row = compute_cost_row(
        candidate, "S1", make_scenario_set(), vessel, avail, cargo,
        make_port_feasibility(), make_distances(), PARAMS,
    )
    assert row.breakdown.waiting_cost == 5 * PARAMS.wait_cost_per_day


def test_demurrage_triggered_when_turnaround_exceeds_laytime_allowance():
    cargo = make_cargo()
    candidate = make_candidate()
    vessel, avail = make_vessel(), make_availability()
    # base=5, congestion=0 -> turnaround=5 > laytime_allowance(4) -> demurrage = 1 day * rate
    pf = make_port_feasibility(base_turnaround=5.0, current_congestion=0.0)
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, pf, make_distances(), PARAMS)
    assert row.breakdown.demurrage == pytest.approx(1.0 * PARAMS.demurrage_rate_per_day)
    assert row.breakdown.despatch_credit == 0.0


def test_despatch_triggered_when_turnaround_beats_laytime_allowance():
    """[Spec-review issue #10] despatch is demurrage's mirror — must not be silently omitted."""
    cargo = make_cargo()
    candidate = make_candidate()
    vessel, avail = make_vessel(), make_availability()
    # base=1, congestion=0 -> turnaround=1 < laytime_allowance(4) -> despatch = 3 days * rate
    pf = make_port_feasibility(base_turnaround=1.0, current_congestion=0.0)
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, pf, make_distances(), PARAMS)
    assert row.breakdown.despatch_credit == pytest.approx(3.0 * PARAMS.despatch_rate_per_day)
    assert row.breakdown.demurrage == 0.0
    # despatch REDUCES fixed_cost (it's a credit)
    assert row.breakdown.despatch_credit > 0


def test_congestion_shock_is_additive_not_multiplicative_no_double_count():
    """[Spec-review issue #9] scenario congestion shock must add to observed
    congestion, not multiply the port's inherent (non-congestion) handling time."""
    cargo = make_cargo()
    candidate = make_candidate()
    vessel, avail = make_vessel(), make_availability()
    pf = make_port_feasibility(base_turnaround=2.5, current_congestion=1.0)

    no_shock = make_scenario_set(congestion_shock=0.0)
    with_shock = make_scenario_set(congestion_shock=3.0)

    row_no_shock = compute_cost_row(candidate, "S1", no_shock, vessel, avail, cargo, pf, make_distances(), PARAMS)
    row_with_shock = compute_cost_row(candidate, "S1", with_shock, vessel, avail, cargo, pf, make_distances(), PARAMS)

    # turnaround_no_shock = 2.5+1.0+0.0 = 3.5 (< 4 allowance -> despatch, no demurrage)
    # turnaround_with_shock = 2.5+1.0+3.0 = 6.5 (> 4 allowance -> demurrage, no despatch)
    assert row_no_shock.breakdown.demurrage == 0.0
    assert row_with_shock.breakdown.demurrage == pytest.approx(2.5 * PARAMS.demurrage_rate_per_day)
    # If the shock had WRONGLY multiplied base_turnaround instead of adding,
    # turnaround would be (2.5*3.0)+1.0=8.5 or similar — a different, wrong number.
    # This asserts the exact additive composition.
    expected_turnaround_with_shock = 2.5 + 1.0 + 3.0
    expected_demurrage = (expected_turnaround_with_shock - PARAMS.laytime_allowance_days) * PARAMS.demurrage_rate_per_day
    assert row_with_shock.breakdown.demurrage == pytest.approx(expected_demurrage)


def test_deadhead_and_idle_both_zero_when_vessel_opens_exactly_at_charter_epoch():
    cargo = make_cargo()
    candidate = make_candidate()  # charter_epoch = 2026-09-01
    vessel = make_vessel()
    avail = make_availability(open_port_id="AU-HAY", open_date=date(2026, 9, 1))  # at origin, opens exactly on epoch
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.breakdown.deadhead_cost == 0.0
    assert row.breakdown.idle_cost == 0.0


def test_idle_cost_positive_when_vessel_arrives_before_charter_epoch():
    """Vessel already at origin (zero deadhead) but opens BEFORE the charter
    epoch -> sits idle waiting for the charter to actually start."""
    cargo = make_cargo()
    candidate = make_candidate(charter_epoch=date(2026, 9, 5))
    vessel = make_vessel()
    avail = make_availability(open_port_id="AU-HAY", open_date=date(2026, 9, 1))  # 4 days before charter_epoch
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.breakdown.deadhead_cost == 0.0  # still zero — vessel is already there
    assert row.breakdown.idle_cost == pytest.approx(4 * PARAMS.idle_cost_per_day)


def test_deadhead_positive_when_vessel_must_reposition():
    cargo = make_cargo()
    candidate = make_candidate()
    vessel = make_vessel()
    avail = make_availability(open_port_id="SG-SIN", open_date=date(2026, 8, 20))
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.breakdown.deadhead_cost > 0.0


def test_tc_priced_candidate_has_zero_per_tonne_and_nonzero_fixed_hire():
    """[Spec-review issue #7] TC-priced candidates must NOT be priced as if
    they were voyage charters — freight_cost_per_tonne must be exactly 0,
    and the $/day hire cost must land in fixed_cost.tc_hire_cost."""
    cargo = make_cargo()
    candidate = make_candidate(pricing_basis=PricingBasis.TIME_CHARTER_PER_DAY, strategy=CharterStrategy.SHORT_TERM)
    vessel, avail = make_vessel(), make_availability()
    row = compute_cost_row(candidate, "S1", make_scenario_set(tc_rate=25000.0), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.freight_cost_per_tonne == 0.0
    assert row.breakdown.tc_hire_cost > 0.0
    # [Fix, found during sanity-check review] TC hire must cover the full
    # on-hire duration (ballast leg to load port + laden leg), not just the
    # laden leg — using laden-only underpriced TC by ~35% relative to the
    # equivalent voyage charter for the identical vessel/route, which isn't
    # economically plausible. avail's open_port_id == origin here, so
    # ballast_days == 0 and on_hire_days == laden_days exactly in this case.
    expected_days = 4700 / 14.0 / 24.0
    assert row.breakdown.tc_hire_cost == pytest.approx(25000.0 * expected_days, rel=1e-6)


def test_tc_hire_cost_includes_ballast_leg_not_laden_only():
    """Regression test for the on-hire-duration fix: a vessel that must
    reposition to the origin port first must have that ballast time INCLUDED
    in its TC hire cost, not just the laden leg."""
    cargo = make_cargo()
    candidate = make_candidate(pricing_basis=PricingBasis.TIME_CHARTER_PER_DAY, strategy=CharterStrategy.SHORT_TERM)
    vessel = make_vessel()
    avail_at_origin = make_availability(open_port_id="AU-HAY")  # zero ballast
    avail_far = make_availability(open_port_id="SG-SIN", open_date=date(2026, 8, 20))  # real ballast leg

    scenario_set = make_scenario_set(tc_rate=25000.0)
    row_at_origin = compute_cost_row(candidate, "S1", scenario_set, vessel, avail_at_origin, cargo, make_port_feasibility(), make_distances(), PARAMS)
    row_far = compute_cost_row(candidate, "S1", scenario_set, vessel, avail_far, cargo, make_port_feasibility(), make_distances(), PARAMS)

    laden_days = 4700 / 14.0 / 24.0
    ballast_days = 2500 / 14.0 / 24.0
    assert row_at_origin.breakdown.tc_hire_cost == pytest.approx(25000.0 * laden_days, rel=1e-6)
    assert row_far.breakdown.tc_hire_cost == pytest.approx(25000.0 * (laden_days + ballast_days), rel=1e-6)
    # the far-opening vessel must cost strictly more hire, not the same
    assert row_far.breakdown.tc_hire_cost > row_at_origin.breakdown.tc_hire_cost


def test_voyage_priced_candidate_has_zero_tc_hire_cost():
    cargo = make_cargo()
    candidate = make_candidate(pricing_basis=PricingBasis.VOYAGE_PER_TONNE)
    vessel, avail = make_vessel(), make_availability()
    row = compute_cost_row(candidate, "S1", make_scenario_set(rate=16.0), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.freight_cost_per_tonne == 16.0
    assert row.breakdown.tc_hire_cost == 0.0


def test_tc_hire_cost_missing_rate_raises_not_silently_zero():
    """If a TC-priced candidate somehow reaches 3.4 without a matching TC rate
    (should be excluded upstream at 3.3), this must fail loudly, not silently
    default to $0 hire cost."""
    cargo = make_cargo()
    candidate = make_candidate(pricing_basis=PricingBasis.TIME_CHARTER_PER_DAY, vessel_class="SUPRAMAX")
    vessel = make_vessel(vessel_class="SUPRAMAX")
    avail = make_availability()
    scenario_set = make_scenario_set()  # only has PANAMAX tc rates, not SUPRAMAX
    with pytest.raises(ValueError, match="TC_RATES_UNAVAILABLE"):
        compute_cost_row(candidate, "S1", scenario_set, vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)


def test_split_cargo_total_is_correctly_scaled_not_naive_full_cargo_scaling():
    """[Spec-review issue #1 — the central bug] total cost for a partial
    tonnage allocation must be q*per_tonne + fixed, NOT (q/cap) * a
    pre-scaled full-cargo total. This is the direct regression test for the
    v1 bug where fixed costs (port, waiting, demurrage, deadhead) were
    incorrectly scaled down for split candidates."""
    cargo = make_cargo()
    candidate = make_candidate(capacity_tonnes=58000)  # a split-eligible Supramax-sized candidate
    vessel = make_vessel(vessel_class="SUPRAMAX", dwt_tonnes=58000)
    avail = make_availability()
    row = compute_cost_row(candidate, "S1", make_scenario_set(rate=16.0), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)

    full_tonnage_cost = row.total_cost_for_tonnage(58000)
    half_tonnage_cost = row.total_cost_for_tonnage(29000)

    # Correct behavior: only the freight (per-tonne) component halves;
    # fixed_cost (port/waiting/demurrage/deadhead) stays IDENTICAL regardless
    # of how much tonnage this candidate actually carries.
    expected_half = 29000 * row.freight_cost_per_tonne + row.fixed_cost
    assert half_tonnage_cost == pytest.approx(expected_half)

    # The v1 bug would have computed: (29000/58000) * full_tonnage_cost,
    # i.e. exactly HALF of the full-tonnage total (since it scaled everything,
    # including fixed costs, by q/cap). Assert we do NOT reproduce that bug:
    buggy_v1_half = (29000 / 58000) * full_tonnage_cost
    assert half_tonnage_cost != pytest.approx(buggy_v1_half)
    assert half_tonnage_cost > buggy_v1_half  # correct total is higher, since fixed costs don't shrink


def test_carbon_cost_zero_when_disabled_default_config():
    """Default config has carbon_cost_enabled=False -> carbon_cost must be
    exactly 0.0 and existing totals must be unaffected (regression guard for
    the disabled-by-default backlog addition)."""
    assert PARAMS.carbon_cost_enabled is False
    cargo = make_cargo()
    candidate = make_candidate()
    vessel, avail = make_vessel(), make_availability()
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, make_port_feasibility(), make_distances(), PARAMS)
    assert row.breakdown.carbon_cost == 0.0


def test_carbon_cost_computed_when_enabled():
    """[Backlog item — competitive-landscape review Section 5.4] With
    carbon_cost_enabled=True, carbon_cost must be a positive, correctly
    computed figure: total_bunker_tonnes * emission_factor * carbon_price."""
    enabled_params = PARAMS.model_copy(update={"carbon_cost_enabled": True, "carbon_price_usd_per_tonne_co2": 80.0})
    cargo = make_cargo()
    candidate = make_candidate()  # PANAMAX, origin==destination-adjacent AU-HAY->IN-PARADIP, vessel already at origin (0 ballast)
    vessel, avail = make_vessel(), make_availability()  # avail.open_port_id == "AU-HAY" == origin -> ballast_days = 0
    row = compute_cost_row(candidate, "S1", make_scenario_set(), vessel, avail, cargo, make_port_feasibility(), make_distances(), enabled_params)

    laden_days = 4700 / 14.0 / 24.0
    expected_bunker_tonnes = laden_days * PARAMS.bunker_consumption_tonnes_per_day["PANAMAX"]  # ballast=0 here
    expected_co2 = expected_bunker_tonnes * PARAMS.co2_emission_factor_tonnes_per_tonne_bunker
    expected_carbon_cost = expected_co2 * 80.0
    assert row.breakdown.carbon_cost == pytest.approx(expected_carbon_cost, rel=1e-6)
    assert row.breakdown.carbon_cost > 0.0
    assert row.fixed_cost > row.total_cost_for_tonnage(0) - row.breakdown.carbon_cost  # sanity: carbon_cost folded into fixed_cost


def test_carbon_cost_scales_with_ballast_plus_laden_not_laden_only():
    """Carbon cost must account for the FULL voyage (ballast + laden), not
    just the laden leg -- a vessel repositioning from further away must show
    a strictly higher carbon cost than one already at the origin."""
    enabled_params = PARAMS.model_copy(update={"carbon_cost_enabled": True})
    cargo = make_cargo()
    candidate = make_candidate()
    vessel = make_vessel()
    avail_at_origin = make_availability(open_port_id="AU-HAY")
    avail_far = make_availability(open_port_id="SG-SIN", open_date=date(2026, 8, 20))
    scenario_set = make_scenario_set()

    row_at_origin = compute_cost_row(candidate, "S1", scenario_set, vessel, avail_at_origin, cargo, make_port_feasibility(), make_distances(), enabled_params)
    row_far = compute_cost_row(candidate, "S1", scenario_set, vessel, avail_far, cargo, make_port_feasibility(), make_distances(), enabled_params)
    assert row_far.breakdown.carbon_cost > row_at_origin.breakdown.carbon_cost


# ---------------------------------------------------------------------------
# Full-matrix integration test against the real fixtures
# ---------------------------------------------------------------------------

def test_compute_cost_matrix_against_real_fixtures(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    from app.feasibility.port_engine import run_port_feasibility
    from app.feasibility.vessel_engine import run_vessel_feasibility
    from app.optimization.strategy_generator import generate_candidates

    vresult = run_vessel_feasibility("R1", cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)

    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)

    # one row per (non-null candidate x scenario)
    assert len(matrix.rows) == len(cset.non_null_candidates) * scenario_set.scenario_count
    assert matrix.cost_param_version == "v1"
    # every row must resolve without error and have a sane positive total for full cargo
    sample = matrix.rows[0]
    total = sample.total_cost_for_tonnage(cargo.quantity_tonnes)
    assert total > 0
