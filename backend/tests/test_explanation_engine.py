from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cost.delivered_cost import compute_cost_matrix
from app.cost.params_loader import load_cost_parameters
from app.explanation.engine import build_explanation
from app.feasibility.port_engine import run_port_feasibility
from app.feasibility.vessel_engine import run_vessel_feasibility
from app.optimization.solver_runner import run_optimization
from app.optimization.strategy_generator import generate_candidates
from app.schemas.common import CargoRequirement, CongestionObservation, Port, RouteDistance, ScenarioSet, Vessel, VesselAvailability

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PARAMS = load_cost_parameters()


def _load(name):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _run_full_pipeline(cargo):
    vdata = _load("mock_vessels.json")
    vessels = [Vessel(**v) for v in vdata["vessels"]]
    avail = [VesselAvailability(**{k: v for k, v in a.items() if not k.startswith("_")}) for a in vdata["vessel_availability"]]
    pdata = _load("mock_ports.json")
    ports_by_id = {p["port_id"]: Port(**p) for p in pdata["ports"]}
    congestion = [CongestionObservation(**c) for c in pdata["congestion_observations"]]
    ddata = _load("mock_distances.json")
    distances = [RouteDistance(**d) for d in ddata["distances"]]
    scenario_set = ScenarioSet(**_load("mock_forecast_scenario.json"))

    vresult = run_vessel_feasibility("R1", cargo, vessels, avail, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion)
    cset = generate_candidates("CAND-1", cargo, vessels, avail, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, avail, presult, distances, PARAMS)
    opt = run_optimization("OPT-1", cargo, cset, matrix, scenario_set, presult, distances, vessels)
    return vresult, presult, cset, matrix, scenario_set, opt


def test_explanation_headline_matches_winner(cargo):
    vresult, presult, cset, matrix, scenario_set, opt = _run_full_pipeline(cargo)
    exp = build_explanation(cargo, vresult, presult, cset, matrix, scenario_set, opt)
    assert opt.selected[0].candidate_id in [l.candidate_id for l in exp.decision.legs]
    assert f"${opt.expected_cost:,.0f}" in exp.headline


def test_every_reason_traces_to_a_real_number(cargo):
    """Sanity check: reasons must reference actual figures present elsewhere
    in the explanation/optimization result, not generic filler."""
    vresult, presult, cset, matrix, scenario_set, opt = _run_full_pipeline(cargo)
    exp = build_explanation(cargo, vresult, presult, cset, matrix, scenario_set, opt)
    assert len(exp.reasons) > 0
    # the vessel feasibility reason must name the actual winning vessel
    assert any(exp.decision.legs[0].vessel_id in r for r in exp.reasons)
    # the cost-comparison reason (if present) must match the actual alternative delta
    if len(exp.alternatives_compared) > 1:
        expected_delta = exp.alternatives_compared[1].expected_cost - exp.alternatives_compared[0].expected_cost
        assert any(f"{expected_delta:,.0f}" in r for r in exp.reasons)


def test_rejected_vessels_use_3_1_reason_text_verbatim(cargo):
    vresult, presult, cset, matrix, scenario_set, opt = _run_full_pipeline(cargo)
    exp = build_explanation(cargo, vresult, presult, cset, matrix, scenario_set, opt)
    hard_rejects = [v for v in vresult.vessels if not v.feasible and not v.split_candidate]
    assert len(exp.rejected_vessels) == len(hard_rejects)
    for rv in exp.rejected_vessels:
        original = next(v for v in hard_rejects if v.vessel_id == rv.vessel_id)
        assert rv.reason_text == original.reason_text


def test_split_cargo_explanation_names_every_leg(cargo):
    big_cargo = cargo.model_copy(update={"cargo_requirement_id": "BIG", "quantity_tonnes": 140000})
    vresult, presult, cset, matrix, scenario_set, opt = _run_full_pipeline(big_cargo)
    exp = build_explanation(big_cargo, vresult, presult, cset, matrix, scenario_set, opt)
    assert "SPLIT" in exp.decision.strategy_label
    assert len(exp.decision.legs) == len(opt.selected)
    assert sum(l.tonnage for l in exp.decision.legs) == pytest.approx(big_cargo.quantity_tonnes)
    # the split reason must name every vessel used
    split_reason = next(r for r in exp.reasons if "split across" in r)
    for leg in exp.decision.legs:
        assert leg.vessel_id in split_reason


def test_despatch_and_demurrage_reasons_are_not_contradictory_in_wording():
    """[Found during manual review of real output] both despatch and demurrage
    can be simultaneously nonzero (probability-weighted averages across
    scenarios where some beat and some miss the laytime allowance) -- the
    wording must reflect that it's an average across scenarios, not a single
    deterministic claim that would read as self-contradictory."""
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=80000,
        origin_country="X", origin_port_id="AU-HAY", destination_port_id="IN-PARADIP",
        delivery_deadline="2026-10-15", earliest_departure="2026-09-01",
    )
    vresult, presult, cset, matrix, scenario_set, opt = _run_full_pipeline(cargo)
    exp = build_explanation(cargo, vresult, presult, cset, matrix, scenario_set, opt)
    if exp.cost_contribution.despatch_credit > 0 and exp.cost_contribution.demurrage > 0:
        despatch_reason = next(r for r in exp.reasons if "despatch credit" in r.lower())
        demurrage_reason = next(r for r in exp.reasons if "demurrage" in r.lower() and "despatch" not in r.lower())
        assert "scenario" in despatch_reason.lower()
        assert "scenario" in demurrage_reason.lower()


def test_reliability_flag_produces_warning_not_reason():
    """A LOW_RELIABILITY_RISK flag must land in warnings, never presented as
    a positive justification for the decision."""
    cargo = CargoRequirement(
        cargo_requirement_id="C1", commodity="coal", quantity_tonnes=58000,
        origin_country="X", origin_port_id="AU-HAY", destination_port_id="IN-PARADIP",
        delivery_deadline="2026-10-15", earliest_departure="2026-09-01",
    )
    vdata = _load("mock_vessels.json")
    vessels = [Vessel(**v) for v in vdata["vessels"] if v["vessel_id"] == "V-SPX-101"]  # reliability_score 0.4, below threshold
    avail = [VesselAvailability(**{k: v for k, v in a.items() if not k.startswith("_")}) for a in vdata["vessel_availability"] if a["vessel_id"] == "V-SPX-101"]
    pdata = _load("mock_ports.json")
    ports_by_id = {p["port_id"]: Port(**p) for p in pdata["ports"]}
    congestion = [CongestionObservation(**c) for c in pdata["congestion_observations"]]
    ddata = _load("mock_distances.json")
    distances = [RouteDistance(**d) for d in ddata["distances"]]
    scenario_set = ScenarioSet(**_load("mock_forecast_scenario.json"))

    vresult = run_vessel_feasibility("R1", cargo, vessels, avail, ports_by_id, distances)
    presult = run_port_feasibility("R1", cargo, ports_by_id, vessels, congestion)
    cset = generate_candidates("CAND-1", cargo, vessels, avail, vresult, presult, distances, scenario_set)
    matrix = compute_cost_matrix("COST-1", cargo, cset, scenario_set, vessels, avail, presult, distances, PARAMS)
    opt = run_optimization("OPT-1", cargo, cset, matrix, scenario_set, presult, distances, vessels)

    exp = build_explanation(cargo, vresult, presult, cset, matrix, scenario_set, opt)
    assert opt.reliability_flag == "LOW_RELIABILITY_RISK"
    assert any("reliability" in w.lower() for w in exp.warnings)
    assert not any("reliability" in r.lower() and "0.4" in r for r in exp.reasons)
