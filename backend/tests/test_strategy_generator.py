from __future__ import annotations

from app import config
from app.feasibility.port_engine import run_port_feasibility
from app.feasibility.vessel_engine import run_vessel_feasibility
from app.optimization.strategy_generator import NULL_CANDIDATE_ID, generate_candidates
from app.schemas.candidates import CharterStrategy


def _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations):
    vresult = run_vessel_feasibility("RUN-1", cargo, vessels, availabilities, ports_by_id, distances)
    presult = run_port_feasibility("RUN-1", cargo, ports_by_id, vessels, congestion_observations)
    return vresult, presult


def test_null_candidate_always_present(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    assert any(c.candidate_id == NULL_CANDIDATE_ID and c.is_null for c in cset.candidates)


def test_candidate_count_is_bounded(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    # 9-vessel fixture fleet, ~23-day epoch window / 2-day step -> should stay
    # comfortably in the tens, not thousands.
    assert 1 <= len(cset.non_null_candidates) <= 300


def test_status_ok_when_candidates_generated(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    assert cset.status == "OK"


def test_feasible_vessels_produce_spot_and_wait_candidates(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    pmx014 = [c for c in cset.non_null_candidates if c.vessel_id == "V-PMX-014"]
    strategies_seen = {c.strategy for c in pmx014}
    assert CharterStrategy.SPOT_NOW in strategies_seen
    assert CharterStrategy.WAIT_THEN_CHARTER in strategies_seen
    assert CharterStrategy.SHORT_TERM in strategies_seen  # TC rates ARE available in the fixture


def test_medium_term_and_coa_excluded_for_small_cargo(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    """80,000t is below MULTI_VOYAGE_THRESHOLD_TONNES -> no MEDIUM_TERM/COA candidates."""
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    strategies_seen = {c.strategy for c in cset.non_null_candidates}
    assert CharterStrategy.MEDIUM_TERM not in strategies_seen
    assert CharterStrategy.COA not in strategies_seen


def test_split_eligible_undersized_vessel_still_generates_candidates(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    """V-SPX-101 (58,000t) is split_candidate=True in 3.1 and >= MIN_ECONOMIC_LOT_TONNES -> should appear."""
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    spx101 = [c for c in cset.non_null_candidates if c.vessel_id == "V-SPX-101"]
    assert len(spx101) > 0
    assert all(c.split_eligible for c in spx101)


def test_infeasible_vessels_never_produce_candidates(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations, scenario_set):
    """V-CPE-002 (draft fails, not split-eligible either) must not appear at all."""
    vresult, presult = _run_upstream(cargo, vessels, availabilities, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    cpe002 = [c for c in cset.non_null_candidates if c.vessel_id == "V-CPE-002"]
    assert cpe002 == []


def test_no_feasible_port_short_circuits_to_null_only(cargo, vessels, availabilities, distances, congestion_observations, scenario_set):
    from tests.test_port_feasibility import make_port
    tiny_ports = {"AU-HAY": make_port(port_id="AU-HAY", max_draft_m=5.0), "IN-PARADIP": make_port(port_id="IN-PARADIP", max_draft_m=5.0)}
    vresult, presult = _run_upstream(cargo, vessels, availabilities, tiny_ports, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, availabilities, vresult, presult, distances, scenario_set)
    assert cset.status == "NO_FEASIBLE_STRATEGY"
    assert cset.candidates == [cset.candidates[0]]  # only the null candidate
    assert cset.candidates[0].is_null


def test_no_feasible_vessel_short_circuits_to_null_only(cargo, ports_by_id, distances, congestion_observations, scenario_set):
    from app.schemas.common import Vessel, VesselAvailability
    from datetime import date
    tiny = [Vessel(vessel_id="V-T1", name="Tiny", vessel_class="HANDYSIZE", dwt_tonnes=5000, loa_m=100, beam_m=15, draft_laden_m=6, service_speed_knots=12)]
    tiny_avail = [VesselAvailability(vessel_id="V-T1", open_date=date(2026, 8, 30), open_port_id="AU-HAY")]
    vresult, presult = _run_upstream(cargo, tiny, tiny_avail, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, tiny, tiny_avail, vresult, presult, distances, scenario_set)
    assert cset.status == "NO_FEASIBLE_STRATEGY"


def test_min_economic_lot_excludes_tiny_split_vessel(cargo, ports_by_id, distances, congestion_observations, scenario_set):
    """A vessel with capacity below MIN_ECONOMIC_LOT_TONNES must never generate a candidate."""
    from app.schemas.common import Vessel, VesselAvailability
    from datetime import date
    assert config.MIN_ECONOMIC_LOT_TONNES == 15_000  # sanity on the constant this test relies on
    tiny = Vessel(
        vessel_id="V-MICRO", name="Micro", vessel_class="HANDYSIZE", dwt_tonnes=8_000,
        loa_m=120, beam_m=18, draft_laden_m=7, service_speed_knots=12,
    )
    normal = Vessel(
        vessel_id="V-PMX-014", name="x", vessel_class="PANAMAX", dwt_tonnes=82000,
        loa_m=229, beam_m=32.3, draft_laden_m=14.4, service_speed_knots=14,
    )
    vessels = [tiny, normal]
    avail = [
        VesselAvailability(vessel_id="V-MICRO", open_date=date(2026, 8, 30), open_port_id="AU-HAY"),
        VesselAvailability(vessel_id="V-PMX-014", open_date=date(2026, 8, 30), open_port_id="SG-SIN"),
    ]
    vresult, presult = _run_upstream(cargo, vessels, avail, ports_by_id, distances, congestion_observations)
    cset = generate_candidates("CAND-1", cargo, vessels, avail, vresult, presult, distances, scenario_set)
    assert all(c.vessel_id != "V-MICRO" for c in cset.non_null_candidates)
    assert any("MIN_ECONOMIC_LOT_TONNES" in n for n in cset.generation_notes)
