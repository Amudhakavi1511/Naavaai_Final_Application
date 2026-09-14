from __future__ import annotations

from datetime import date

from app.feasibility import rules
from app.feasibility.vessel_engine import evaluate_vessel, run_vessel_feasibility
from app.schemas.common import CargoRequirement, Port, RouteDistance, Vessel, VesselAvailability

# ---------------------------------------------------------------------------
# Rule-by-rule boundary case tests (isolated predicates, per spec Section 2.5)
# ---------------------------------------------------------------------------

def make_vessel(**overrides) -> Vessel:
    base = dict(
        vessel_id="V-TEST", name="Test Vessel", vessel_class="PANAMAX",
        dwt_tonnes=80000, loa_m=229.0, beam_m=32.3, draft_laden_m=14.3,
        service_speed_knots=14.0,
    )
    base.update(overrides)
    return Vessel(**base)


def make_port(**overrides) -> Port:
    base = dict(
        port_id="P-TEST", name="Test Port", country="Testland",
        max_draft_m=17.0, max_loa_m=300.0, max_beam_m=48.0, berth_count=2,
        cargo_handling_rate_tonnes_per_day=20000, base_turnaround_days=2.5,
    )
    base.update(overrides)
    return Port(**base)


def test_capacity_ok_exact_equal_is_feasible():
    vessel = make_vessel(dwt_tonnes=80000)
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    assert rules.capacity_ok(vessel, cargo) is True


def test_capacity_ok_one_tonne_short_is_infeasible():
    vessel = make_vessel(dwt_tonnes=79999)
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    assert rules.capacity_ok(vessel, cargo) is False


def test_draft_ok_exact_equal_is_feasible():
    vessel = make_vessel(draft_laden_m=17.0)
    origin = make_port(max_draft_m=19.0)
    dest = make_port(max_draft_m=17.0)
    assert rules.draft_ok(vessel, origin, dest) is True


def test_draft_ok_exceeds_limiting_port_is_infeasible():
    vessel = make_vessel(draft_laden_m=18.1)
    origin = make_port(max_draft_m=19.0)
    dest = make_port(max_draft_m=17.0)
    assert rules.draft_ok(vessel, origin, dest) is False


def test_draft_uses_shallower_of_the_two_ports():
    """The limiting draft must be the MIN of origin and destination, not just destination."""
    vessel = make_vessel(draft_laden_m=15.0)
    origin = make_port(max_draft_m=14.0)  # shallower than destination
    dest = make_port(max_draft_m=19.0)
    assert rules.draft_ok(vessel, origin, dest) is False


# ---------------------------------------------------------------------------
# Full-chain integration tests against the mock fixture fleet
# ---------------------------------------------------------------------------

def _run(cargo, vessels, availabilities, ports_by_id, distances):
    return run_vessel_feasibility(
        feasibility_run_id="RUN-1",
        cargo=cargo,
        vessels=vessels,
        availabilities=availabilities,
        ports_by_id=ports_by_id,
        distances=distances,
    )


def test_known_feasible_panamax_passes_all_checks(cargo, vessels, availabilities, ports_by_id, distances):
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-PMX-014")
    assert v.feasible is True
    assert v.failed == []


def test_capesize_fails_draft_check_matching_spec_worked_example(cargo, vessels, availabilities, ports_by_id, distances):
    """Reproduces the exact worked example from the Decision Engine spec:
    'Draft 18.1m exceeds Paradip limit 17.0m'."""
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-CPE-002")
    assert v.feasible is False
    assert "draft_ok" in v.failed
    assert "18.1" in v.reason_text and "17.0" in v.reason_text


def test_late_open_date_fails_availability(cargo, vessels, availabilities, ports_by_id, distances):
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-PMX-030")
    assert v.feasible is False
    assert "avail_ok" in v.failed


def test_undersized_vessel_flagged_as_split_candidate_not_hard_infeasible(cargo, vessels, availabilities, ports_by_id, distances):
    """A vessel that fails ONLY capacity_ok should be flagged split_candidate=True
    so 3.3 can still consider it for a multi-vessel strategy."""
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-SPX-101")
    assert v.feasible is False
    assert v.failed == ["capacity_ok"]
    assert v.split_candidate is True


def test_vessel_already_at_destination_can_still_reposition_and_be_feasible(cargo, vessels, availabilities, ports_by_id, distances):
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-PMX-045")
    assert v.feasible is True


def test_far_and_late_vessel_fails_both_avail_and_origin(cargo, vessels, availabilities, ports_by_id, distances):
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    v = next(v for v in result.vessels if v.vessel_id == "V-CPE-005")
    assert v.feasible is False
    assert "avail_ok" in v.failed
    assert "origin_ok" in v.failed


def test_result_status_ok_when_at_least_one_vessel_feasible(cargo, vessels, availabilities, ports_by_id, distances):
    result = _run(cargo, vessels, availabilities, ports_by_id, distances)
    assert result.status == "OK"
    assert len(result.feasible_vessels) > 0


def test_no_feasible_vessel_status_when_entire_fleet_fails(cargo, availabilities, ports_by_id, distances):
    """Every vessel intentionally fails on MULTIPLE checks (not just
    capacity) -> genuinely NO_FEASIBLE_VESSEL. Undersized-but-otherwise-fine
    vessels are NOT this case -- they're split_candidate=True and make
    status "OK" (the split-cargo path can use them; see the status property's
    docstring), covered by test_undersized_vessel_flagged_as_split_candidate_not_hard_infeasible."""
    unusable_fleet = [
        make_vessel(vessel_id="V-TINY-1", dwt_tonnes=5000, draft_laden_m=30.0),  # tiny AND draft-fails everywhere
        make_vessel(vessel_id="V-TINY-2", dwt_tonnes=6000, draft_laden_m=30.0),
    ]
    tiny_avail = [
        VesselAvailability(vessel_id="V-TINY-1", open_date=date(2026, 8, 30), open_port_id="AU-HAY"),
        VesselAvailability(vessel_id="V-TINY-2", open_date=date(2026, 8, 30), open_port_id="AU-HAY"),
    ]
    result = _run(cargo, unusable_fleet, tiny_avail, ports_by_id, distances)
    assert result.status == "NO_FEASIBLE_VESSEL"
    assert all(set(v.failed) == {"capacity_ok", "draft_ok"} for v in result.vessels)
    assert all(v.split_candidate is False for v in result.vessels)  # fails MORE than just capacity -> not split-eligible


def test_undersized_only_fleet_is_still_status_ok_via_split_eligibility(cargo, ports_by_id, distances):
    """[Regression test for the API integration bug found in test_api_orchestration.py]
    A fleet where every vessel fails ONLY capacity_ok (genuinely split-eligible)
    must report status="OK", not NO_FEASIBLE_VESSEL -- otherwise the
    orchestration layer would short-circuit before 3.3 ever builds the split
    candidates that 3.5's MIP path depends on."""
    undersized_fleet = [make_vessel(vessel_id="V-U1", dwt_tonnes=5000), make_vessel(vessel_id="V-U2", dwt_tonnes=6000)]
    avail = [
        VesselAvailability(vessel_id="V-U1", open_date=date(2026, 8, 30), open_port_id="AU-HAY"),
        VesselAvailability(vessel_id="V-U2", open_date=date(2026, 8, 30), open_port_id="AU-HAY"),
    ]
    result = _run(cargo, undersized_fleet, avail, ports_by_id, distances)
    assert result.status == "OK"
    assert all(v.split_candidate for v in result.vessels)
    assert result.feasible_vessels == []  # none can carry it ALONE, but the fleet is still usable


def test_no_availability_record_treated_as_infeasible_not_crash(cargo, ports_by_id, distances):
    vessel = make_vessel(vessel_id="V-NOAVAIL", dwt_tonnes=80000)
    result = _run(cargo, [vessel], [], ports_by_id, distances)
    v = result.vessels[0]
    assert v.feasible is False
    assert "avail_ok" in v.failed
    assert v.reason_text == "No availability record for this vessel"


# ---------------------------------------------------------------------------
# Vessel reliability score — non-blocking flag (backlog item, Section 5.2)
# ---------------------------------------------------------------------------

def test_reliability_score_passed_through_unchanged():
    vessel = make_vessel(reliability_score=0.85)
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    origin = make_port(port_id="A")
    dest = make_port(port_id="B")
    availability = VesselAvailability(vessel_id="V-TEST", open_date=date(2026, 9, 1), open_port_id="A")
    distances = [RouteDistance(from_port_id="A", to_port_id="A", distance_nm=0), RouteDistance(from_port_id="A", to_port_id="B", distance_nm=1000)]
    result = evaluate_vessel(vessel, availability, cargo, origin, dest, distances)
    assert result.reliability_score == 0.85
    assert result.reliability_flag is None  # above threshold (0.6)


def test_low_reliability_score_flagged_but_does_not_affect_feasibility():
    """[Regression test — the core design constraint of this backlog item]
    A low reliability_score must be surfaced as a flag but must NEVER change
    `feasible`, since 3.1 is a deterministic PHYSICAL-constraints-only gate."""
    vessel = make_vessel(reliability_score=0.3)  # below VESSEL_RELIABILITY_FLAG_THRESHOLD (0.6)
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    origin = make_port(port_id="A")
    dest = make_port(port_id="B")
    availability = VesselAvailability(vessel_id="V-TEST", open_date=date(2026, 9, 1), open_port_id="A")
    distances = [RouteDistance(from_port_id="A", to_port_id="A", distance_nm=0), RouteDistance(from_port_id="A", to_port_id="B", distance_nm=1000)]
    result = evaluate_vessel(vessel, availability, cargo, origin, dest, distances)
    assert result.reliability_flag == "LOW_RELIABILITY_RISK"
    assert result.feasible is True  # physically feasible regardless of reliability


def test_unknown_reliability_score_is_none_not_flagged():
    vessel = make_vessel(reliability_score=None)
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="A", destination_port_id="B",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )
    origin = make_port(port_id="A")
    dest = make_port(port_id="B")
    availability = VesselAvailability(vessel_id="V-TEST", open_date=date(2026, 9, 1), open_port_id="A")
    distances = [RouteDistance(from_port_id="A", to_port_id="A", distance_nm=0), RouteDistance(from_port_id="A", to_port_id="B", distance_nm=1000)]
    result = evaluate_vessel(vessel, availability, cargo, origin, dest, distances)
    assert result.reliability_score is None
    assert result.reliability_flag is None
