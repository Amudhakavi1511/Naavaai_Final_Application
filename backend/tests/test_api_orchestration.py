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


def _demo_request_body() -> dict:
    return {
        "cargo": _load("cargo_requirement.json"),
        "scenario_set": _load("mock_forecast_scenario.json"),
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # Health also reports dataset size, so "up but loaded nothing" is
    # distinguishable from "up" without a second call.
    assert body["ports"] > 0
    assert body["vessels"] > 0
    assert body["routes"] > 0
    assert body["scenarios"] > 0


# ---------------------------------------------------------------------------
# Full happy path: Cargo -> Forecast/Scenario -> Feasibility -> Optimization
# -> Recommendation, exactly the integration chain spec Section 39 requires.
# ---------------------------------------------------------------------------

def test_full_pipeline_returns_optimal_on_demo_cargo():
    resp = client.post("/optimization/run", json=_demo_request_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OPTIMAL"
    assert body["stage_reached"] == "3.5"
    assert body["vessel_feasibility"] is not None
    assert body["port_feasibility"] is not None
    assert body["candidate_set"] is not None
    assert body["cost_matrix_summary"]["row_count"] > 0
    assert body["optimization_result"]["solve_method"] == "ENUMERATION"
    assert len(body["optimization_result"]["selected"]) == 1
    assert body["optimization_result"]["selected"][0]["tonnage"] == pytest.approx(80000)


def test_reliability_score_surfaced_end_to_end_via_api():
    """[Backlog item, Section 5.2] Vessel reliability must be passed through
    at 3.1 (informational, non-blocking) AND surfaced on the final winning
    candidate in the API response -- verified against the real fixture fleet
    where V-PMX-014 (the known winner) has a fixture-set score of 0.88."""
    resp = client.post("/optimization/run", json=_demo_request_body())
    body = resp.json()
    pmx014 = next(v for v in body["vessel_feasibility"]["vessels"] if v["vessel_id"] == "V-PMX-014")
    assert pmx014["reliability_score"] == 0.88
    assert pmx014["reliability_flag"] is None
    # a fixture vessel with a deliberately low score (V-SPX-101, 0.4) must be flagged
    spx101 = next(v for v in body["vessel_feasibility"]["vessels"] if v["vessel_id"] == "V-SPX-101")
    assert spx101["reliability_flag"] == "LOW_RELIABILITY_RISK"
    # winner's reliability must surface on the OptimizationResult itself too
    assert body["optimization_result"]["vessel_reliability_score"] == 0.88


def test_carbon_cost_disabled_by_default_end_to_end_via_api():
    """[Backlog item, Section 5.4] With no config override, the demo pipeline
    must produce identical costs whether or not carbon accounting logic
    exists — this locks in the disabled-by-default contract at the API layer."""
    resp = client.post("/optimization/run", json=_demo_request_body())
    body = resp.json()
    # expected_cost is a known, previously-verified figure for this exact
    # demo scenario; if carbon cost were silently enabled this would shift.
    assert body["optimization_result"]["expected_cost"] == pytest.approx(895437.35, rel=1e-4)


def test_response_includes_every_upstream_stage_for_transparency():
    """The 'engine room' panel (spec Section 9) needs every module's result
    in one response, not just the final recommendation."""
    resp = client.post("/optimization/run", json=_demo_request_body())
    body = resp.json()
    # Full fleet, feasible AND infeasible: the nine fixture vessels plus the
    # nine in config/fleet_extension.json, which were added so the widened
    # loading-port network has vessels open in the right basins.
    assert len(body["vessel_feasibility"]["vessels"]) == 18
    assert len(body["port_feasibility"]["ports"]) == 2
    assert len(body["candidate_set"]["candidates"]) > 100  # incl. null candidate


def test_split_cargo_via_api_routes_to_mip():
    body = _demo_request_body()
    body["cargo"]["quantity_tonnes"] = 140000
    body["cargo"]["cargo_requirement_id"] = "CARGO-SPLIT-API"
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 200
    result = resp.json()["optimization_result"]
    assert result["solve_method"] == "MIP"
    assert result["status"] == "OPTIMAL"
    assert len(result["selected"]) >= 2


# ---------------------------------------------------------------------------
# Typed failure states — each must be a 200 with the right status, not a 500
# ---------------------------------------------------------------------------

def test_no_feasible_vessel_returns_200_with_typed_status():
    """[Fix — test premise corrected] Oversized cargo alone doesn't trigger
    NO_FEASIBLE_VESSEL anymore -- it makes every vessel split_candidate=True,
    which is a valid "OK" status (the split path can use them). Genuine
    NO_FEASIBLE_VESSEL requires vessels to be unusable in EVERY way, e.g. an
    impossibly tight delivery window that fails avail_ok/origin_ok too."""
    body = _demo_request_body()
    body["cargo"]["delivery_deadline"] = body["cargo"]["earliest_departure"]  # zero-day window
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "NO_FEASIBLE_VESSEL"
    assert result["stage_reached"] == "3.1"
    assert result["vessel_feasibility"] is not None
    assert result["port_feasibility"] is None  # never reached — 3.2 wasn't called
    assert result["optimization_result"] is None


def test_oversized_cargo_makes_vessels_split_eligible_not_no_feasible_vessel():
    """Companion test making the corrected semantics explicit: a cargo too
    big for any single vessel does NOT short-circuit at 3.1 -- it proceeds
    (every vessel split-eligible) and is expected to fail later, typically
    at NO_FEASIBLE_STRATEGY once MAX_VESSELS_PER_CARGO can't cover it."""
    body = _demo_request_body()
    body["cargo"]["quantity_tonnes"] = 500000  # exceeds every vessel, even 2 combined
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] != "NO_FEASIBLE_VESSEL"
    assert result["vessel_feasibility"] is not None
    assert result["port_feasibility"] is not None  # DID proceed past 3.1


def test_no_feasible_port_returns_200_with_typed_status():
    """IN-GANGAVARAM has deep-enough draft (18.5m) to clear 3.1's per-vessel
    check for every vessel in the fleet, but its congestion (11.5 days,
    fixture-set above the 10-day threshold) is a dimension 3.1 never checks
    -- so this genuinely exercises 3.2 rejecting a port AFTER 3.1 passed,
    rather than both failing for the same underlying (draft) reason."""
    body = _demo_request_body()
    body["cargo"]["destination_port_id"] = "IN-GANGAVARAM"
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "NO_FEASIBLE_PORT"
    assert result["stage_reached"] == "3.2"
    assert result["vessel_feasibility"] is not None
    assert result["vessel_feasibility"]["vessels"]  # 3.1 DID find usable vessels
    assert result["candidate_set"] is None  # 3.3 wasn't reached


def test_missing_reference_data_returns_clean_500_not_a_crash():
    """[Regression test — found while fixing the NO_FEASIBLE_PORT test above,
    which originally crashed with an unhandled 500 traceback for exactly this
    reason] An origin/destination port pair absent from the distance
    reference table must surface as a clean REFERENCE_DATA_INCOMPLETE 500,
    not an unhandled stack trace leaking through the API.

    [Updated when the port network was widened] IN-VIZAG no longer works as
    the trigger: the routing-graph generator now derives a distance for it.
    IN-SANDHEADS is carried deliberately without coordinates or a routing
    gateway (it is a lighterage anchorage whose particulars are not modelled),
    so it is the honest remaining case of a port the distance table cannot
    cover."""
    body = _demo_request_body()
    body["cargo"]["origin_port_id"] = "IN-SANDHEADS"
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 500
    assert "REFERENCE_DATA_INCOMPLETE" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Request validation — malformed scenario probabilities rejected automatically
# ---------------------------------------------------------------------------

def test_malformed_scenario_probabilities_returns_422():
    """FORECAST_INPUT_INVALID (spec Section 8) — ScenarioSet's own validator
    rejects a scenario bank whose probabilities don't sum to 1.0. This must
    happen automatically via Pydantic/FastAPI request validation, with NO
    extra code in the orchestration or route layer."""
    body = _demo_request_body()
    # break probabilities: scale the first scenario's probability way up
    body["scenario_set"]["scenarios"][0]["probability"] = 0.9
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 422


def test_missing_required_field_returns_422():
    body = _demo_request_body()
    del body["cargo"]["quantity_tonnes"]
    resp = client.post("/optimization/run", json=body)
    assert resp.status_code == 422
