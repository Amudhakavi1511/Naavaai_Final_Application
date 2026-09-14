from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CandidateRiskMetrics(BaseModel):
    candidate_id: str
    expected_cost: float
    variance: float
    worst_case_cost: float
    cvar: float
    cvar_status: str  # "COMPUTED" | "NOT_MEANINGFUL_SAMPLE_SIZE"
    downside_probability: float
    risk_label: str  # "LOW" | "MEDIUM" | "HIGH" — display-only, never fed back into the objective
    vessel_reliability_score: Optional[float] = None
    reliability_flag: Optional[str] = None


class RiskResult(BaseModel):
    risk_run_id: str
    cargo_requirement_id: str
    risk_preference: str
    risk_lambda: float
    candidates: list[CandidateRiskMetrics]

    def get(self, candidate_id: str) -> CandidateRiskMetrics:
        return next(c for c in self.candidates if c.candidate_id == candidate_id)
