from __future__ import annotations

from pydantic import BaseModel, Field


class SelectedLeg(BaseModel):
    candidate_id: str
    tonnage: float


class RankedAlternative(BaseModel):
    candidate_id: str
    expected_cost: float
    cvar: float
    rank: int


class RejectedSummaryItem(BaseModel):
    reason: str


class OptimizationResult(BaseModel):
    optimization_run_id: str
    cargo_requirement_id: str
    solve_method: str  # "ENUMERATION" | "MIP" | "NONE"
    status: str  # "OPTIMAL" | "NO_FEASIBLE_STRATEGY" | "TIME_LIMIT_REACHED"
    selected: list[SelectedLeg] = Field(default_factory=list)
    expected_cost: float = 0.0
    cvar_80: float = 0.0
    cvar_status: str = "NOT_COMPUTED"
    objective_value: float = 0.0
    risk_aversion_lambda: float = 0.0
    vessel_reliability_score: float | None = None
    reliability_flag: str | None = None
    ranked_alternatives: list[RankedAlternative] = Field(default_factory=list)
    rejected_summary: list[RejectedSummaryItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
