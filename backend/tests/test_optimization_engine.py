from __future__ import annotations

from datetime import date

import pytest

from app import config
from app.cost.delivered_cost import compute_cost_matrix
from app.cost.params_loader import load_cost_parameters
from app.feasibility.port_engine import run_port_feasibility
from app.feasibility.vessel_engine import run_vessel_feasibility
from app.optimization.enumerate import enumerate_single_vessel_candidates
from app.optimization.mip_model import solve_split_cargo
from app.optimization.solver_runner import run_optimization
from app.optimization.strategy_generator import generate_candidates
from app.risk.metrics import risk_adjusted_objective
from app.schemas.candidates import CandidateOption, CandidateSet, CharterStrategy, CostBreakdown, CostMatrix, CostRow, PricingBasis
from app.schemas.common import CargoRequirement, DailyRate, Port, PortCheckResult, PortFeasibilityResult, RouteDistance, Scenario, ScenarioSet, Vessel, VesselAvailability

PARAMS = load_cost_parameters()


# ---------------------------------------------------------------------------
# Full-fixture integration tests
# ---------------------------------------------------------------------------

def test_enumeration_path_selected_on_normal_demo_cargo(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult = run_vessel_feasibility("R1", cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", cargo, cset, matrix, scenario_set, presult, distances, vessels)

    assert result.solve_method == "ENUMERATION"
    assert result.status == "OPTIMAL"
    assert len(result.selected) == 1
    assert result.selected[0].tonnage == cargo.quantity_tonnes
    assert result.expected_cost > 0
    assert result.cvar_80 >= result.expected_cost  # CVaR can never be below expected cost


def test_ranked_alternatives_sorted_ascending_by_objective(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult = run_vessel_feasibility("R1", cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", cargo, cset, matrix, scenario_set, presult, distances, vessels)

    objectives = [a.expected_cost for a in result.ranked_alternatives]
    assert objectives == sorted(objectives)
    assert result.ranked_alternatives[0].candidate_id == result.selected[0].candidate_id


def test_mip_path_selected_when_cargo_exceeds_every_single_vessel(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    big_cargo = cargo.model_copy(update={"cargo_requirement_id": "BIG", "quantity_tonnes": 140000})
    vresult = run_vessel_feasibility("R1", big_cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", big_cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", big_cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", big_cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", big_cargo, cset, matrix, scenario_set, presult, distances, vessels)

    assert result.solve_method == "MIP"
    assert result.status == "OPTIMAL"
    assert len(result.selected) >= 2
    total = sum(leg.tonnage for leg in result.selected)
    assert total == pytest.approx(big_cargo.quantity_tonnes)


def test_mip_respects_min_economic_lot_per_leg(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    big_cargo = cargo.model_copy(update={"cargo_requirement_id": "BIG", "quantity_tonnes": 140000})
    vresult = run_vessel_feasibility("R1", big_cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", big_cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", big_cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", big_cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", big_cargo, cset, matrix, scenario_set, presult, distances, vessels)
    for leg in result.selected:
        assert leg.tonnage >= config.MIN_ECONOMIC_LOT_TONNES


def test_mip_respects_max_vessels_per_cargo(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    big_cargo = cargo.model_copy(update={"cargo_requirement_id": "BIG", "quantity_tonnes": 140000})
    vresult = run_vessel_feasibility("R1", big_cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", big_cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", big_cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", big_cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", big_cargo, cset, matrix, scenario_set, presult, distances, vessels)
    assert len(result.selected) <= config.MAX_VESSELS_PER_CARGO


def test_mip_never_double_books_same_vessel(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    """Regression test for the self-review fix: two candidate ROWS for the
    same vessel (different epochs) must never both be selected."""
    big_cargo = cargo.model_copy(update={"cargo_requirement_id": "BIG", "quantity_tonnes": 140000})
    vresult = run_vessel_feasibility("R1", big_cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", big_cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", big_cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", big_cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)
    result = run_optimization("OPT-1", big_cargo, cset, matrix, scenario_set, presult, distances, vessels)

    vessel_ids_used = []
    for leg in result.selected:
        c = next(x for x in cset.non_null_candidates if x.candidate_id == leg.candidate_id)
        vessel_ids_used.append(c.vessel_id)
    assert len(vessel_ids_used) == len(set(vessel_ids_used))


def test_no_feasible_strategy_propagates_from_upstream(cargo, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    tiny_ports = {"AU-HAY": _make_port("AU-HAY", 5.0), "IN-PARADIP": _make_port("IN-PARADIP", 5.0)}
    from app.schemas.common import Vessel as V
    vessels = [V(vessel_id="V1", name="x", vessel_class="PANAMAX", dwt_tonnes=80000, loa_m=229, beam_m=32.3, draft_laden_m=14.3, service_speed_knots=14)]
    avail = [VesselAvailability(vessel_id="V1", open_date=date(2026, 8, 30), open_port_id="AU-HAY")]
    vresult = run_vessel_feasibility("R1", cargo, vessels, avail, tiny_ports, distances)
    presult = run_port_feasibility("R1", cargo, tiny_ports, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, avail, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, avail, presult, distances, PARAMS)
    result = run_optimization("OPT-1", cargo, cset, matrix, scenario_set, presult, distances, vessels)
    assert result.status == "NO_FEASIBLE_STRATEGY"
    assert result.solve_method == "NONE"
    assert len(result.rejected_summary) > 0


def _make_port(port_id, max_draft):
    return Port(port_id=port_id, name="x", country="x", max_draft_m=max_draft, max_loa_m=300, max_beam_m=48, berth_count=2, cargo_handling_rate_tonnes_per_day=20000, base_turnaround_days=2.5)


# ---------------------------------------------------------------------------
# Risk-neutral regression test (spec Section 6.6: lambda=0 sanity check)
# ---------------------------------------------------------------------------

def test_lambda_zero_enumeration_matches_pure_expected_cost_ranking(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult = run_vessel_feasibility("R1", cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, availabilities, presult, distances, PARAMS)

    full_cap = [c for c in cset.non_null_candidates if c.capacity_tonnes >= cargo.quantity_tonnes]
    scores_risk_neutral = enumerate_single_vessel_candidates(full_cap, cargo, matrix, scenario_set, risk_lambda=0.0)
    # at lambda=0, objective_value must equal expected_cost EXACTLY for every candidate
    for s in scores_risk_neutral:
        assert s.objective_value == pytest.approx(s.expected_cost)
    # and the winner must be whichever candidate has the lowest expected_cost, full stop
    cheapest_by_expected = min(scores_risk_neutral, key=lambda s: s.expected_cost)
    assert scores_risk_neutral[0].candidate.candidate_id == cheapest_by_expected.candidate.candidate_id


# ---------------------------------------------------------------------------
# Berth-overlap constraint — small, hand-controlled synthetic MIP scenario
# (spec-review issue #5: this is the piece most likely to have a subtle bug)
# ---------------------------------------------------------------------------

def _synthetic_split_setup(epoch_1: date, epoch_2: date, turnaround_days: float = 2.0):
    """Two Supramax-sized vessels, each individually undersized for a 100,000t
    cargo, forcing a 2-vessel split. Distances chosen so laden voyage is short
    and controllable, so we can precisely control arrival/departure windows
    via the charter epochs alone."""
    cargo = CargoRequirement(
        cargo_requirement_id="SPLIT-TEST", commodity="coal", quantity_tonnes=100000,
        origin_country="X", origin_port_id="ORIG", destination_port_id="DEST",
        delivery_deadline=date(2026, 12, 1), earliest_departure=date(2026, 9, 1),
    )
    vessel_a = Vessel(vessel_id="VA", name="A", vessel_class="SUPRAMAX", dwt_tonnes=58000, loa_m=190, beam_m=32.3, draft_laden_m=12.5, service_speed_knots=12.0)
    vessel_b = Vessel(vessel_id="VB", name="B", vessel_class="SUPRAMAX", dwt_tonnes=58000, loa_m=190, beam_m=32.3, draft_laden_m=12.5, service_speed_knots=12.0)
    distances = [
        RouteDistance(from_port_id="ORIG", to_port_id="ORIG", distance_nm=0),
        RouteDistance(from_port_id="ORIG", to_port_id="DEST", distance_nm=288),  # 288nm / 12kt / 24 = exactly 1.0 day laden
    ]
    port_feasibility = PortFeasibilityResult(
        feasibility_run_id="R", cargo_requirement_id="SPLIT-TEST",
        ports=[
            PortCheckResult(port_id="DEST", feasible=True, draft_ok=True, berth_ok=True, handling_ok=True, congestion_acceptable=True, base_turnaround_days=turnaround_days, current_congestion_days=0.0),
            PortCheckResult(port_id="ORIG", feasible=True, draft_ok=True, berth_ok=True, handling_ok=True, congestion_acceptable=True, base_turnaround_days=1.0, current_congestion_days=0.0),
        ],
    )
    candidate_a = CandidateOption(
        candidate_id="CA", vessel_id="VA", vessel_class="SUPRAMAX", strategy=CharterStrategy.SPOT_NOW,
        pricing_basis=PricingBasis.VOYAGE_PER_TONNE, charter_epoch=epoch_1,
        origin_port_id="ORIG", destination_port_id="DEST", capacity_tonnes=58000, split_eligible=True,
    )
    candidate_b = CandidateOption(
        candidate_id="CB", vessel_id="VB", vessel_class="SUPRAMAX", strategy=CharterStrategy.SPOT_NOW,
        pricing_basis=PricingBasis.VOYAGE_PER_TONNE, charter_epoch=epoch_2,
        origin_port_id="ORIG", destination_port_id="DEST", capacity_tonnes=58000, split_eligible=True,
    )
    dates = [date(2026, 9, 1) + __import__("datetime").timedelta(days=i) for i in range(60)]
    scenario = Scenario(
        scenario_id="S1", probability=1.0,
        voyage_freight_path_usd_per_tonne=[DailyRate(date=d, rate=15.0) for d in dates],
    )
    scenario_set = ScenarioSet(scenario_run_id="SR", forecast_run_id="FR", scenario_count=1, scenarios=[scenario])

    cost_matrix = CostMatrix(
        cost_run_id="CR", cargo_requirement_id="SPLIT-TEST", cost_param_version="v1",
        rows=[
            CostRow(candidate_id="CA", scenario_id="S1", freight_cost_per_tonne=15.0, fixed_cost=50000,
                    breakdown=CostBreakdown(port_cost=50000, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
            CostRow(candidate_id="CB", scenario_id="S1", freight_cost_per_tonne=15.0, fixed_cost=50000,
                    breakdown=CostBreakdown(port_cost=50000, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
        ],
    )
    return cargo, [vessel_a, vessel_b], [candidate_a, candidate_b], cost_matrix, scenario_set, port_feasibility, distances


def test_berth_overlap_allows_non_overlapping_epochs():
    """Vessel A arrives day 1, occupies berth [1,3) (2-day turnaround).
    Vessel B departs day 5 -> arrives day 6, occupies [6,8). No overlap ->
    both must be selectable together (MIP must find OPTIMAL, using both)."""
    cargo, vessels, candidates, cost_matrix, scenario_set, port_feasibility, distances = _synthetic_split_setup(
        epoch_1=date(2026, 9, 1), epoch_2=date(2026, 9, 5), turnaround_days=2.0
    )
    result = solve_split_cargo(cargo, candidates, cost_matrix, scenario_set, vessels, port_feasibility, distances)
    assert result.status == "OPTIMAL"
    selected_ids = {cid for cid, _ in result.selected}
    assert selected_ids == {"CA", "CB"}  # both needed to cover 100,000t (58k each, need both)


def test_berth_overlap_rejects_combination_that_cannot_be_sequenced():
    """Both vessels aim for the EXACT SAME arrival/departure window at the
    same destination port. Under this model's single-berth assumption (see
    mip_model.py's stated simplification), neither ordering (A-before-B or
    B-before-A) can satisfy the non-overlap constraint when the windows are
    identical -- so this combination is genuinely INFEASIBLE, and since both
    vessels are required to cover the cargo (only 2 candidates, both needed),
    the whole MIP must correctly report INFEASIBLE rather than silently
    ignoring the clash."""
    cargo, vessels, candidates, cost_matrix, scenario_set, port_feasibility, distances = _synthetic_split_setup(
        epoch_1=date(2026, 9, 1), epoch_2=date(2026, 9, 1), turnaround_days=2.0
    )
    result = solve_split_cargo(cargo, candidates, cost_matrix, scenario_set, vessels, port_feasibility, distances)
    assert result.status == "INFEASIBLE"


def test_berth_overlap_boundary_case_exact_handoff_is_feasible():
    """Vessel B's arrival exactly equals Vessel A's departure (a back-to-back
    berth handoff, the tightest legitimately feasible case) -- the >= in the
    big-M constraint must accept equality, not reject it off-by-one."""
    # arrival[A] = epoch1 + 1 laden day; departure[A] = arrival[A] + 2 turnaround days.
    # Set epoch2 so arrival[B] lands exactly on departure[A]: epoch2 = epoch1 + 2 days.
    cargo, vessels, candidates, cost_matrix, scenario_set, port_feasibility, distances = _synthetic_split_setup(
        epoch_1=date(2026, 9, 1), epoch_2=date(2026, 9, 3), turnaround_days=2.0
    )
    result = solve_split_cargo(cargo, candidates, cost_matrix, scenario_set, vessels, port_feasibility, distances)
    assert result.status == "OPTIMAL"
    selected_ids = {cid for cid, _ in result.selected}
    assert selected_ids == {"CA", "CB"}


def test_infeasibility_diagnosis_identifies_timing_conflict_not_capacity():
    """[Regression test — found via a real what-if scenario, not invented]
    When combined capacity and lot size are both sufficient but the MIP is
    still infeasible, the diagnosis must correctly identify a timing/berth
    conflict, NOT the (wrong, in this case) generic capacity/lot-size guess
    the code used to always give regardless of the actual cause."""
    cargo, vessels, candidates, cost_matrix, scenario_set, port_feasibility, distances = _synthetic_split_setup(
        epoch_1=date(2026, 9, 1), epoch_2=date(2026, 9, 1), turnaround_days=2.0  # identical windows -> INFEASIBLE
    )
    result = solve_split_cargo(cargo, candidates, cost_matrix, scenario_set, vessels, port_feasibility, distances)
    assert result.status == "INFEASIBLE"
    assert result.infeasibility_reason.startswith("LIKELY_TIMING_OR_BERTH_CONFLICT")


def test_infeasibility_diagnosis_identifies_insufficient_capacity():
    """The other diagnostic branch: when even the best MAX_VESSELS_PER_CARGO
    vessels can't reach the cargo quantity, the diagnosis must say so
    specifically, not blame timing."""
    from app.optimization.mip_model import _diagnose_infeasibility
    from app.schemas.candidates import CandidateOption, CharterStrategy, PricingBasis
    from app.schemas.common import CargoRequirement as CR
    tiny_cargo = CR(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=500000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 12, 1), earliest_departure=date(2026, 9, 1),
    )
    tiny_candidates = [
        CandidateOption(candidate_id="C1", vessel_id="V1", vessel_class="SUPRAMAX", strategy=CharterStrategy.SPOT_NOW,
                         pricing_basis=PricingBasis.VOYAGE_PER_TONNE, charter_epoch=date(2026, 9, 1),
                         origin_port_id="A", destination_port_id="B", capacity_tonnes=58000, split_eligible=True),
    ]
    reason = _diagnose_infeasibility(tiny_candidates, tiny_cargo)
    assert reason.startswith("INSUFFICIENT_COMBINED_CAPACITY")
