from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _base_body(changes: dict) -> dict:
    return {
        "cargo": _load("cargo_requirement.json"),
        "scenario_set": _load("mock_forecast_scenario.json"),
        "changes": changes,
    }


def test_no_changes_produces_identical_baseline_and_modified():
    resp = client.post("/optimization/what-if", json=_base_body({}))
    assert resp.status_code == 200
    r = resp.json()
    assert r["baseline"]["optimization_result"]["expected_cost"] == r["modified"]["optimization_result"]["expected_cost"]
    assert r["delta"]["decision_changed"] is False


def test_freight_shock_increases_cost_by_the_freight_share_of_total():
    resp = client.post("/optimization/what-if", json=_base_body({"freight_shock_pct": 10.0}))
    r = resp.json()
    base_cost = r["baseline"]["optimization_result"]["expected_cost"]
    mod_cost = r["modified"]["optimization_result"]["expected_cost"]
    assert mod_cost > base_cost
    # freight is roughly 60% of total for this demo scenario -> a 10% freight
    # shock should move total cost by roughly 5-7%, NOT the full 10%
    # (fixed costs are untouched by a freight shock).
    pct_change = (mod_cost - base_cost) / base_cost * 100
    assert 3.0 < pct_change < 9.0
    assert r["delta"]["expected_cost_change_pct"] == pytest.approx(pct_change, rel=1e-3)


def test_risk_preference_override_changes_lambda_not_cargo_object():
    resp = client.post("/optimization/what-if", json=_base_body({"risk_preference": "HIGH"}))
    r = resp.json()
    assert r["baseline"]["optimization_result"]["risk_aversion_lambda"] == pytest.approx(0.35)  # original was BALANCED
    assert r["modified"]["optimization_result"]["risk_aversion_lambda"] == pytest.approx(0.1)   # HIGH tolerance -> lowest lambda


def test_congestion_shock_increases_cost():
    resp = client.post("/optimization/what-if", json=_base_body({"congestion_shock_days": 5.0}))
    r = resp.json()
    assert r["modified"]["optimization_result"]["expected_cost"] > r["baseline"]["optimization_result"]["expected_cost"]


def test_invalid_deadline_shift_returns_422_not_500():
    """A deadline shift that would move delivery_deadline before
    earliest_departure must be a clean client-input error, not a crash."""
    resp = client.post("/optimization/what-if", json=_base_body({"deadline_shift_days": -100}))
    assert resp.status_code == 422
    assert "INVALID_WHATIF_CHANGES" in resp.json()["detail"]


def test_vessel_availability_shock_can_make_baseline_optimal_and_modified_infeasible():
    """A large fleet-wide availability delay should be able to push a
    normally-OPTIMAL scenario to NO_FEASIBLE_STRATEGY, with a specific,
    non-generic diagnostic reason -- not silently still return OPTIMAL,
    and not crash."""
    resp = client.post("/optimization/what-if", json=_base_body({"vessel_availability_shock_days": 30.0}))
    assert resp.status_code == 200
    r = resp.json()
    assert r["baseline"]["status"] == "OPTIMAL"
    assert r["modified"]["status"] == "NO_FEASIBLE_STRATEGY"
    assert r["delta"]["decision_changed"] is True
    assert "Status changed" in r["delta"]["summary"]
    # the diagnostic must be specific, not the old generic wrong-in-this-case guess
    notes = r["modified"]["optimization_result"]["notes"]
    assert any("LIKELY_TIMING_OR_BERTH_CONFLICT" in n or "INSUFFICIENT_COMBINED_CAPACITY" in n for n in notes)


def test_decision_changed_flag_reflects_a_different_winning_vessel():
    """Construct a scenario where a large freight shock is likely to flip
    the winner between candidates with different cost structures (voyage
    vs. TC pricing react differently to a freight shock)."""
    resp = client.post("/optimization/what-if", json=_base_body({"freight_shock_pct": 200.0}))
    r = resp.json()
    baseline_vessels = set(r["delta"]["baseline_winning_vessel_ids"])
    modified_vessels = set(r["delta"]["modified_winning_vessel_ids"])
    # whether or not the vessel actually changes, decision_changed must be
    # computed consistently with the vessel-id sets shown
    expected_changed = (r["baseline"]["status"] != r["modified"]["status"]) or (baseline_vessels != modified_vessels)
    assert r["delta"]["decision_changed"] == expected_changed


def test_baseline_and_modified_do_not_share_mutated_state():
    """[Design correctness check] Running a what-if with vessel_availability_shock
    must not affect the BASELINE run's vessel availability -- the two runs
    must use independently-copied reference data."""
    resp = client.post("/optimization/what-if", json=_base_body({"vessel_availability_shock_days": 30.0}))
    r = resp.json()
    # baseline must be completely unaffected -- same result as a plain /optimization/run call
    plain_resp = client.post("/optimization/run", json={"cargo": _load("cargo_requirement.json"), "scenario_set": _load("mock_forecast_scenario.json")})
    plain_r = plain_resp.json()
    assert r["baseline"]["optimization_result"]["expected_cost"] == plain_r["optimization_result"]["expected_cost"]
