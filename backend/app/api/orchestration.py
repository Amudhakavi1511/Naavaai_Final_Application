"""
Orchestration service — implements the Decision Engine spec's Section 8
sequencing exactly:

    Validate ForecastOutput/ScenarioSet contract  --fail--> FORECAST_INPUT_INVALID
    3.1 Vessel Feasibility   --all infeasible-->  NO_FEASIBLE_VESSEL
    3.2 Port Feasibility     --both infeasible-->  NO_FEASIBLE_PORT
    3.3 Strategy Generator   --empty (null only)--> NO_FEASIBLE_STRATEGY
    3.4 Delivered Cost Engine  (pure computation; CONFIG_MISSING on missing params)
    3.5 Optimization (Pass 1 <-> 3.6 Risk <-> Pass 2 internally)
    -> DecisionEngineResponse

Every failure path returns a TYPED status, never a silent empty/default
result (spec Section 40) — the API layer's job is purely to sequence calls
and translate internal statuses into the response contract; no new business
logic lives here.
"""
from __future__ import annotations

import uuid

from app.api.reference_data import ReferenceData
from app.api.schemas import CostMatrixSummary, DecisionEngineResponse, OptimizationRunRequest
from app.cost.delivered_cost import compute_cost_matrix
from app.cost.params_loader import CostParametersMissingError
from app.explanation.engine import build_explanation
from app.feasibility.port_engine import run_port_feasibility
from app.feasibility.vessel_engine import run_vessel_feasibility
from app.optimization.solver_runner import run_optimization
from app.optimization.strategy_generator import generate_candidates


class ConfigMissingError(RuntimeError):
    """Raised (and caught at the API route layer as a 500) when cost
    parameters can't be loaded — a genuine service configuration problem,
    not a client input problem."""


def run_decision_engine(request: OptimizationRunRequest, reference_data: ReferenceData) -> DecisionEngineResponse:
    request_id = str(uuid.uuid4())
    cargo = request.cargo
    # A request may omit the scenario bank; the server then uses its own. See
    # OptimizationRunRequest.scenario_set for why this is optional.
    scenario_set = request.scenario_set or reference_data.default_scenario_set

    # --- 3.1 Vessel Feasibility ---
    vessel_feasibility = run_vessel_feasibility(
        feasibility_run_id=request_id,
        cargo=cargo,
        vessels=reference_data.vessels,
        availabilities=reference_data.availabilities,
        ports_by_id=reference_data.ports_by_id,
        distances=reference_data.distances,
    )
    if vessel_feasibility.status != "OK":
        return DecisionEngineResponse(
            request_id=request_id, status="NO_FEASIBLE_VESSEL", stage_reached="3.1",
            vessel_feasibility=vessel_feasibility,
        )

    # --- 3.2 Port Feasibility ---
    port_feasibility = run_port_feasibility(
        feasibility_run_id=request_id,
        cargo=cargo,
        ports_by_id=reference_data.ports_by_id,
        candidate_vessels=reference_data.vessels,
        congestion_observations=reference_data.congestion_observations,
    )
    if port_feasibility.status != "OK":
        return DecisionEngineResponse(
            request_id=request_id, status="NO_FEASIBLE_PORT", stage_reached="3.2",
            vessel_feasibility=vessel_feasibility, port_feasibility=port_feasibility,
        )

    # --- 3.3 Charter Strategy Generator ---
    candidate_set = generate_candidates(
        candidate_run_id=request_id, cargo=cargo,
        vessels=reference_data.vessels, availabilities=reference_data.availabilities,
        vessel_feasibility=vessel_feasibility, port_feasibility=port_feasibility,
        distances=reference_data.distances, scenario_set=scenario_set,
    )
    if candidate_set.status != "OK":
        return DecisionEngineResponse(
            request_id=request_id, status="NO_FEASIBLE_STRATEGY", stage_reached="3.3",
            vessel_feasibility=vessel_feasibility, port_feasibility=port_feasibility,
            candidate_set=candidate_set,
        )

    # --- 3.4 Delivered Cost Engine ---
    try:
        cost_matrix = compute_cost_matrix(
            cost_run_id=request_id, cargo=cargo, candidate_set=candidate_set, scenario_set=scenario_set,
            vessels=reference_data.vessels, availabilities=reference_data.availabilities,
            port_feasibility=port_feasibility, distances=reference_data.distances,
            params=reference_data.cost_params,
        )
    except CostParametersMissingError as e:
        raise ConfigMissingError(str(e)) from e

    # --- 3.5 Optimization Engine (calls 3.6 Risk Engine internally) ---
    optimization_result = run_optimization(
        optimization_run_id=request_id, cargo=cargo, candidate_set=candidate_set,
        cost_matrix=cost_matrix, scenario_set=scenario_set, port_feasibility=port_feasibility,
        distances=reference_data.distances, vessels=reference_data.vessels,
    )

    # --- 4.1 Explanation Engine — only when there's a decision to explain ---
    explanation = None
    if optimization_result.status in ("OPTIMAL", "TIME_LIMIT_REACHED"):
        explanation = build_explanation(
            cargo=cargo, vessel_feasibility=vessel_feasibility, port_feasibility=port_feasibility,
            candidate_set=candidate_set, cost_matrix=cost_matrix, scenario_set=scenario_set,
            optimization_result=optimization_result,
        )

    return DecisionEngineResponse(
        request_id=request_id,
        status=optimization_result.status,
        stage_reached="3.5",
        vessel_feasibility=vessel_feasibility,
        port_feasibility=port_feasibility,
        candidate_set=candidate_set,
        cost_matrix_summary=CostMatrixSummary(row_count=len(cost_matrix.rows), cost_param_version=cost_matrix.cost_param_version),
        optimization_result=optimization_result,
        explanation=explanation,
    )
