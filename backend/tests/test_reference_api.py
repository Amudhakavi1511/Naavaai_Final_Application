"""
Tests for the read-only reference surface and the widened port network.

The point of these is not that the numbers are right — the distances are
DERIVED and stated as illustrative. The point is that the reference data the
frontend builds its form from and the reference data the engine solves against
cannot drift apart. Every option the API offers must be an option the API can
actually service; that invariant is what test_every_offered_lane_is_servable
locks down, and it is the bug class that made a hardcoded frontend port list
unsafe in the first place.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.reference_data import load_demo_reference_data
from app.api.route_distances import RouteGraph, great_circle_nm
from app.feasibility import rules

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _cargo() -> dict:
    with open(FIXTURES_DIR / "cargo_requirement.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Reference endpoints
# ---------------------------------------------------------------------------

def test_bootstrap_returns_everything_the_form_needs_in_one_call():
    resp = client.get("/reference/bootstrap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["origins"], "no loading countries offered"
    assert body["discharge_ports"], "no discharge ports offered"
    assert body["commodities"], "no commodities offered"
    assert body["fleet_size"] > 0
    assert body["scenario_bank"]["scenario_count"] > 0


def test_origins_cover_the_countries_india_imports_dry_bulk_from():
    countries = {c["country"] for c in client.get("/reference/origins").json()}
    for expected in ("Australia", "Indonesia", "Mozambique", "United States", "South Africa", "Brazil"):
        assert expected in countries


def test_every_origin_port_declares_its_commodities():
    for country in client.get("/reference/origins").json():
        assert country["ports"], f"{country['country']} has no loading ports"
        for port in country["ports"]:
            assert port["commodities"], f"{port['port_id']} has no commodities label"


def test_discharge_ports_are_east_coast_india_and_carry_operational_context():
    ports = client.get("/reference/discharge-ports").json()
    assert {p["state"] for p in ports} <= {"Odisha", "Andhra Pradesh", "West Bengal"}
    for port in ports:
        assert port["max_draft_m"] > 0
        assert port["current_congestion_days"] >= 0


def test_vessels_endpoint_reports_open_positions():
    vessels = client.get("/reference/vessels").json()
    assert len(vessels) > 9, "fleet extension not loaded"
    assert all(v["open_port_id"] for v in vessels), "a vessel has no open position"


def test_sandheads_is_not_offered_as_a_dischargeable_gateway():
    """It exists in the port master (it is in the problem-statement scope) but
    its particulars and approach distances aren't modelled, so it must never
    reach the picker — that is exactly the drift this surface prevents."""
    offered = {p["port_id"] for p in client.get("/reference/discharge-ports").json()}
    assert "IN-SANDHEADS" not in offered


# ---------------------------------------------------------------------------
# The invariant: nothing is offered that can't be solved
# ---------------------------------------------------------------------------

def test_every_offered_lane_is_servable():
    """Every (loading port, discharge port) pair the reference API offers must
    have a distance behind it. Without this, a user can pick a lane from the
    form and get a 500 — which is precisely what happened while the frontend
    carried its own hardcoded port list."""
    reference_data = load_demo_reference_data()
    body = client.get("/reference/bootstrap").json()
    origin_ids = [p["port_id"] for c in body["origins"] for p in c["ports"]]
    discharge_ids = [p["port_id"] for p in body["discharge_ports"]]

    missing = []
    for origin in origin_ids:
        for destination in discharge_ids:
            try:
                rules.lookup_distance(reference_data.distances, origin, destination)
            except ValueError:
                missing.append((origin, destination))

    assert not missing, f"offered lanes with no distance behind them: {missing[:5]}"


@pytest.mark.parametrize(
    "origin_port_id,origin_country",
    [
        ("ID-TBN", "Indonesia"),
        ("ZA-RBY", "South Africa"),
        ("MZ-BEW", "Mozambique"),
        ("US-NOL", "United States"),
        ("BR-PDM", "Brazil"),
        ("AE-FJR", "United Arab Emirates"),
    ],
)
def test_widened_lanes_run_end_to_end_without_reference_errors(origin_port_id, origin_country):
    """A lane may legitimately come back NO_FEASIBLE_* — that is the engine
    doing its job. What it must never do is 500 on missing reference data."""
    cargo = _cargo() | {"origin_port_id": origin_port_id, "origin_country": origin_country}
    resp = client.post("/optimization/run", json={"cargo": cargo})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] in (
        "OPTIMAL", "TIME_LIMIT_REACHED",
        "NO_FEASIBLE_VESSEL", "NO_FEASIBLE_PORT", "NO_FEASIBLE_STRATEGY",
    )


# ---------------------------------------------------------------------------
# Fleet/port calibration — most widened-network lanes should actually clear
# ---------------------------------------------------------------------------

# Every lane below is expected to return a real recommendation for an
# 80,000t standard demo cargo, given the fleet in tests/fixtures/mock_vessels.json
# plus config/fleet_extension.json. This is a calibration guard: it exists
# because the network initially widened to 33 loading ports while the fleet
# extension positioned only one undersized vessel (77,000t, 3,000t short of
# an 80,000t Panamax cargo) anywhere near the US Gulf/Atlantic or Colombia,
# and New Orleans' draft figure was set below that vessel's laden draft on
# top of that -- so every US Atlantic/Gulf and Colombian lane failed not on
# a genuine feasibility limit but on two narrow calibration numbers. If this
# regresses, the likely cause is the same shape of bug: a fixture value
# quietly no longer matching the fleet that's supposed to service it.
EXPECTED_SERVICEABLE_LANES = [
    ("AU-HAY", "Australia"), ("AU-NEW", "Australia"),
    ("ID-TBN", "Indonesia"), ("ID-BPN", "Indonesia"),
    ("ZA-RBY", "South Africa"), ("ZA-DUR", "South Africa"),
    ("MZ-NAC", "Mozambique"),
    ("US-NOR", "United States"), ("US-BAL", "United States"), ("US-NOL", "United States"),
    ("CA-VAN", "Canada"), ("RU-VNY", "Russia"), ("BR-PDM", "Brazil"),
    ("CO-PBO", "Colombia"), ("CO-SMR", "Colombia"),
    ("OM-SOH", "Oman"), ("AE-FJR", "United Arab Emirates"),
]


@pytest.mark.parametrize("origin_port_id,origin_country", EXPECTED_SERVICEABLE_LANES)
def test_widened_lanes_return_a_real_recommendation(origin_port_id, origin_country):
    cargo = _cargo() | {"origin_port_id": origin_port_id, "origin_country": origin_country}
    resp = client.post("/optimization/run", json={"cargo": cargo})
    body = resp.json()
    assert body["status"] in ("OPTIMAL", "TIME_LIMIT_REACHED"), (
        f"{origin_country} / {origin_port_id} unexpectedly failed to clear: "
        f"{body.get('optimization_result', {}).get('notes')}"
    )


def test_beira_is_correctly_draft_limited_not_a_bug():
    """Beira's ~12m draft genuinely excludes every vessel large enough to
    carry an 80,000t parcel — this should keep failing, and failing for the
    stated reason, not silently start passing because someone loosened the
    draft figure to make the lane count go up."""
    cargo = _cargo() | {"origin_port_id": "MZ-BEW", "origin_country": "Mozambique"}
    resp = client.post("/optimization/run", json={"cargo": cargo})
    body = resp.json()
    assert body["status"] == "NO_FEASIBLE_STRATEGY"
    notes = body["optimization_result"]["notes"]
    assert any("INSUFFICIENT_COMBINED_CAPACITY" in n for n in notes)


# ---------------------------------------------------------------------------
# Optional scenario bank
# ---------------------------------------------------------------------------

def test_omitting_the_scenario_bank_uses_the_servers_own_and_gives_the_same_answer():
    """The frontend no longer ships an 800 KB scenario bank. Omitting it must
    be exactly equivalent to posting the bundled one, or the change would have
    silently altered every recommendation."""
    cargo = _cargo()
    with open(FIXTURES_DIR / "mock_forecast_scenario.json") as f:
        bank = json.load(f)

    without = client.post("/optimization/run", json={"cargo": cargo}).json()
    with_bank = client.post("/optimization/run", json={"cargo": cargo, "scenario_set": bank}).json()

    assert without["status"] == with_bank["status"]
    assert without["optimization_result"]["expected_cost"] == pytest.approx(
        with_bank["optimization_result"]["expected_cost"]
    )


def test_what_if_also_works_without_an_explicit_scenario_bank():
    resp = client.post(
        "/optimization/what-if",
        json={"cargo": _cargo(), "changes": {"freight_shock_pct": 15.0}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["baseline"]["status"] == "OPTIMAL"
    assert body["delta"]["summary"]


# ---------------------------------------------------------------------------
# Routing graph
# ---------------------------------------------------------------------------

def test_curated_distances_are_never_overwritten_by_derived_ones():
    """The generator fills gaps; it must not silently redefine a number
    somebody entered on purpose — several test expectations depend on the
    curated Hay Point to Paradip figure."""
    reference_data = load_demo_reference_data()
    assert rules.lookup_distance(reference_data.distances, "AU-HAY", "IN-PARADIP") == 4700


def test_derived_routes_go_round_land_not_through_it():
    """A straight great circle from New Orleans to Paradip runs across Africa.
    The waypoint graph must return something materially longer, and must say
    which way it went."""
    reference_data = load_demo_reference_data()
    graph = RouteGraph(reference_data.ports_by_id.values())

    straight = great_circle_nm((29.95, -90.07), (20.27, 86.68))
    routed, via = graph.shortest("US-NOL", "IN-PARADIP")

    assert routed > straight * 1.3
    assert via and via != "direct"


def test_neighbouring_terminals_are_not_routed_out_to_an_ocean_waypoint():
    reference_data = load_demo_reference_data()
    assert rules.lookup_distance(reference_data.distances, "IN-PARADIP", "IN-DHAMRA") < 300
    assert rules.lookup_distance(reference_data.distances, "AE-FJR", "AE-KHA") < 300


def test_a_port_without_coordinates_yields_no_derived_distance():
    """IN-SANDHEADS is carried deliberately unmodelled. It must produce a
    clean REFERENCE_DATA_INCOMPLETE rather than a plausible-looking guess."""
    reference_data = load_demo_reference_data()
    with pytest.raises(ValueError):
        rules.lookup_distance(reference_data.distances, "IN-SANDHEADS", "AU-HAY")
