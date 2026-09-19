from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.api.schemas import DecisionEngineResponse
from app.schemas.common import CargoRequirement, RiskPreference, ScenarioSet


class WhatIfChanges(BaseModel):
    """
    Every field is a delta/override applied to the BASE request, never a
    replacement of the whole request — this mirrors the spec's what-if
    framing ("what if freight rises 10%?", "what if congestion increases by
    3 days?") and keeps the API surface small and self-explanatory.
    """
    freight_shock_pct: float = Field(default=0.0, description="e.g. 10.0 = freight rates up 10% (applies to voyage AND TC rates, every scenario)")
    congestion_shock_days: float = Field(default=0.0, ge=0.0, description="Added to every scenario's base_congestion_shock_days")
    deadline_shift_days: int = Field(default=0, description="Added to cargo.delivery_deadline (negative = earlier deadline)")
    risk_preference: Optional[RiskPreference] = Field(default=None, description="Override cargo.risk_preference; None = unchanged")
    vessel_availability_shock_days: float = Field(default=0.0, ge=0.0, description="Added to every vessel's open_date (simulates a fleet-wide availability delay)")


class WhatIfRequest(BaseModel):
    cargo: CargoRequirement
    scenario_set: Optional[ScenarioSet] = Field(
        default=None, description="Optional — see OptimizationRunRequest.scenario_set."
    )
    changes: WhatIfChanges


class WhatIfDelta(BaseModel):
    decision_changed: bool
    baseline_status: str
    modified_status: str
    baseline_winning_vessel_ids: list[str]
    modified_winning_vessel_ids: list[str]
    expected_cost_change_usd: Optional[float] = None
    expected_cost_change_pct: Optional[float] = None
    summary: str


class WhatIfResponse(BaseModel):
    baseline: DecisionEngineResponse
    modified: DecisionEngineResponse
    delta: WhatIfDelta
