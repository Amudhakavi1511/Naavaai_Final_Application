from __future__ import annotations

from app.feasibility.congestion import estimate_turnaround
from app.feasibility.port_engine import evaluate_port, run_port_feasibility
from app.schemas.common import CongestionObservation, Port


def make_port(**overrides) -> Port:
    base = dict(
        port_id="P-TEST", name="Test Port", country="Testland",
        max_draft_m=17.0, max_loa_m=300.0, max_beam_m=48.0, berth_count=2,
        cargo_handling_rate_tonnes_per_day=20000, base_turnaround_days=2.5,
    )
    base.update(overrides)
    return Port(**base)


# ---------------------------------------------------------------------------
# Congestion / turnaround estimator (Section 9, issue #9 fix — base and
# current congestion returned SEPARATELY, never pre-summed)
# ---------------------------------------------------------------------------

def test_turnaround_returns_base_and_congestion_separately_not_summed():
    port = make_port(base_turnaround_days=2.5)
    obs = [CongestionObservation(port_id="P-TEST", observation_timestamp="2026-08-30", current_congestion_days=1.0)]
    base, congestion = estimate_turnaround(port, obs)
    assert base == 2.5
    assert congestion == 1.0
    # explicitly NOT a combined 3.5 -- callers must compose these themselves


def test_turnaround_defaults_congestion_to_zero_when_no_observation():
    port = make_port(base_turnaround_days=2.5)
    base, congestion = estimate_turnaround(port, [])
    assert base == 2.5
    assert congestion == 0.0


def test_turnaround_uses_latest_observation_when_multiple_exist():
    port = make_port()
    obs = [
        CongestionObservation(port_id="P-TEST", observation_timestamp="2026-08-20", current_congestion_days=5.0),
        CongestionObservation(port_id="P-TEST", observation_timestamp="2026-08-30", current_congestion_days=1.0),
    ]
    _, congestion = estimate_turnaround(port, obs)
    assert congestion == 1.0


# ---------------------------------------------------------------------------
# Boundary case tests for individual checks
# ---------------------------------------------------------------------------

def test_draft_check_exact_equal_is_feasible_for_draft():
    port = make_port(max_draft_m=17.0)
    result = evaluate_port(port, _dummy_cargo(), window_days=45, required_draft_m=17.0, congestion_observations=[])
    assert result.draft_ok is True


def test_draft_check_fails_when_required_exceeds_port_limit():
    port = make_port(max_draft_m=17.0)
    result = evaluate_port(port, _dummy_cargo(), window_days=45, required_draft_m=18.1, congestion_observations=[])
    assert result.draft_ok is False
    assert "draft" in result.reason_text.lower()


def test_handling_check_fails_when_window_too_short():
    port = make_port(cargo_handling_rate_tonnes_per_day=1000)  # would need 80 days for 80,000t
    result = evaluate_port(port, _dummy_cargo(), window_days=45, required_draft_m=14.0, congestion_observations=[])
    assert result.handling_ok is False


def test_congestion_check_fails_above_threshold():
    port = make_port()
    obs = [CongestionObservation(port_id="P-TEST", observation_timestamp="2026-08-30", current_congestion_days=11.5)]
    result = evaluate_port(port, _dummy_cargo(), window_days=45, required_draft_m=14.0, congestion_observations=obs, congestion_threshold_days=10.0)
    assert result.congestion_acceptable is False
    assert "congestion" in result.reason_text.lower()


def _dummy_cargo():
    from datetime import date
    from app.schemas.common import CargoRequirement
    return CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="AU-HAY", destination_port_id="IN-PARADIP",
        delivery_deadline=date(2026, 10, 15), earliest_departure=date(2026, 9, 1),
    )


# ---------------------------------------------------------------------------
# Full-chain integration tests against the mock fixture ports
# ---------------------------------------------------------------------------

def test_paradip_is_feasible_for_panamax_draft(cargo, ports_by_id, congestion_observations, vessels):
    result = run_port_feasibility("RUN-1", cargo, ports_by_id, vessels, congestion_observations)
    paradip = result.get("IN-PARADIP")
    assert paradip.feasible is True
    assert paradip.base_turnaround_days == 2.5
    assert paradip.current_congestion_days == 1.0


def test_gangavaram_fails_congestion_threshold(cargo, ports_by_id, congestion_observations, vessels):
    """Gangavaram fixture is deliberately set above the 10-day threshold."""
    gangavaram = ports_by_id["IN-GANGAVARAM"]
    result = evaluate_port(
        gangavaram, cargo, window_days=45, required_draft_m=14.3,
        congestion_observations=congestion_observations,
    )
    assert result.feasible is False
    assert "congestion_acceptable" in result.failed


def test_result_status_ok_when_both_ports_feasible(cargo, ports_by_id, congestion_observations, vessels):
    result = run_port_feasibility("RUN-1", cargo, ports_by_id, vessels, congestion_observations)
    assert result.status == "OK"


def test_no_feasible_port_status_when_both_ports_fail(cargo, congestion_observations, vessels):
    """Force both origin and destination to fail by requiring a draft neither can serve."""
    tiny_ports = {
        "AU-HAY": make_port(port_id="AU-HAY", max_draft_m=5.0),
        "IN-PARADIP": make_port(port_id="IN-PARADIP", max_draft_m=5.0),
    }
    result = run_port_feasibility("RUN-1", cargo, tiny_ports, vessels, congestion_observations)
    assert result.status == "NO_FEASIBLE_PORT"


def test_no_feasible_port_status_when_only_destination_fails(cargo, ports_by_id, congestion_observations, vessels):
    """[Regression test for the bug found via the API integration test]
    Origin feasible + destination infeasible must STILL be NO_FEASIBLE_PORT
    overall -- the original status property was wrong (it only required AT
    LEAST ONE port feasible, so a fine origin masked a broken destination)."""
    mixed_ports = {
        "AU-HAY": ports_by_id["AU-HAY"],  # feasible
        "IN-PARADIP": make_port(port_id="IN-PARADIP", max_draft_m=5.0),  # infeasible
    }
    result = run_port_feasibility("RUN-1", cargo, mixed_ports, vessels, congestion_observations)
    assert result.status == "NO_FEASIBLE_PORT"
    assert result.get("AU-HAY").feasible is True
    assert result.get("IN-PARADIP").feasible is False


def test_draft_check_is_not_tautological_against_3_1_prefiltered_vessels(cargo, ports_by_id, congestion_observations, vessels):
    """
    Regression test for the code-review fix: if required_draft_m were derived
    from vessels ALREADY filtered by 3.1 (which only lets vessels through that
    already clear both ports' draft limits), this check could never fail.
    Using the full candidate fleet against a port shallower than EVERY
    vessel in it (including the shallowest, the Handysize at 10.2m) must
    still correctly reject the port.
    """
    ultra_shallow_port = {
        "AU-HAY": ports_by_id["AU-HAY"],
        "IN-PARADIP": make_port(port_id="IN-PARADIP", max_draft_m=9.0),  # shallower than every fixture vessel
    }
    result = run_port_feasibility("RUN-1", cargo, ultra_shallow_port, vessels, congestion_observations)
    paradip = result.get("IN-PARADIP")
    assert paradip.feasible is False
    assert "draft_ok" in paradip.failed


def test_draft_requirement_uses_shallowest_vessel_in_whole_fleet_not_capacity_filtered(cargo, ports_by_id, congestion_observations, vessels):
    """[Regression test for the split-cargo draft bug] required_draft_m must
    be the shallowest draft across the ENTIRE fleet (including undersized,
    split-eligible vessels like the 35,000t Handysize at 10.2m draft), not
    just vessels big enough to carry the cargo alone -- otherwise a port
    that's perfectly fine for the vessels an ACTUAL split plan would use
    gets wrongly rejected because only a much-deeper-draft Capesize could
    carry the cargo solo."""
    port_ok_for_handysize_not_capesize = {
        "AU-HAY": ports_by_id["AU-HAY"],
        "IN-PARADIP": make_port(port_id="IN-PARADIP", max_draft_m=11.0),  # clears Handysize (10.2m), not Capesize (18m+)
    }
    result = run_port_feasibility("RUN-1", cargo, port_ok_for_handysize_not_capesize, vessels, congestion_observations)
    assert result.get("IN-PARADIP").feasible is True
