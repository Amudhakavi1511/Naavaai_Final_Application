from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.candidates import CandidateSet
from app.schemas.common import CargoRequirement, PortFeasibilityResult, ScenarioSet, VesselFeasibilityResult
from app.schemas.explanation import Explanation
from app.schemas.optimization_result import OptimizationResult


class OptimizationRunRequest(BaseModel):
    cargo: CargoRequirement
    scenario_set: Optional[ScenarioSet] = Field(
        default=None,
        description="Optional. Omit it and the server uses its own bundled demo scenario bank, "
        "which is what the frontend does — a client has no way to produce or validate a "
        "scenario set, so making it mandatory only meant shipping ~800 KB of JSON back to the "
        "server that the server already had. Supply one to drive the engine from an "
        "externally generated bank (what the Intelligence Layer will do once it exists, and "
        "what the test suite does today).",
    )


class CostMatrixSummary(BaseModel):
    """The full CostMatrix (candidates x scenarios, thousands of rows) is
    deliberately NOT included in the API response — it's an internal
    intermediate artifact, not something the frontend needs row-by-row. A
    `?detail=full` query param exposing it is documented as future work."""
    row_count: int
    cost_param_version: str


class DecisionEngineResponse(BaseModel):
    """
    Unified response for POST /optimization/run. Every stage's result is
    included (not just the final one) so the frontend's "engine room"
    transparency panel (spec Section 9) can render each module's output
    without a separate round trip, and so a NO_FEASIBLE_* status still
    carries the full reasoning that led to it.
    """
    request_id: str
    status: str  # "OPTIMAL" | "NO_FEASIBLE_VESSEL" | "NO_FEASIBLE_PORT" | "NO_FEASIBLE_STRATEGY" | "TIME_LIMIT_REACHED"
    stage_reached: str  # "3.1" | "3.2" | "3.3" | "3.4" | "3.5"
    vessel_feasibility: Optional[VesselFeasibilityResult] = None
    port_feasibility: Optional[PortFeasibilityResult] = None
    candidate_set: Optional[CandidateSet] = None
    cost_matrix_summary: Optional[CostMatrixSummary] = None
    optimization_result: Optional[OptimizationResult] = None
    explanation: Optional[Explanation] = None
