from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class DecisionLeg(BaseModel):
    """One vessel's part of the decision — a single entry for a single-vessel
    decision, or one entry per leg for a split-cargo decision."""
    candidate_id: str
    vessel_id: str
    vessel_class: str
    strategy: str
    pricing_basis: str
    charter_epoch: date
    tonnage: float


class DecisionSummary(BaseModel):
    strategy_label: str          # "SPOT_NOW" | "WAIT_THEN_CHARTER" | ... | "SPLIT (2 vessels)"
    origin_port_id: str
    destination_port_id: str
    total_tonnage: float
    legs: list[DecisionLeg]
    expected_cost: float
    cvar_80: float
    cvar_status: str
    risk_label: str               # "LOW" | "MEDIUM" | "HIGH" — same bucketing as 3.6's risk_label
    risk_preference: str
    risk_aversion_lambda: float


class AlternativeComparison(BaseModel):
    candidate_id: str
    rank: int
    expected_cost: float
    cost_delta_vs_winner_usd: float
    cost_delta_vs_winner_pct: float
    cvar: float


class RejectedVesselSummary(BaseModel):
    vessel_id: str
    vessel_class: str
    reason_text: str


class CostContribution(BaseModel):
    """Probability-weighted average cost breakdown for the winning decision —
    used to ground the 'why' reasons in actual numbers, not generic claims."""
    freight_or_hire_cost: float
    port_cost: float
    waiting_cost: float
    idle_cost: float
    deadhead_cost: float
    demurrage: float
    despatch_credit: float
    carbon_cost: float


class Explanation(BaseModel):
    """
    Module 4.1 output — deterministic, reason-coded. Every string in
    `reasons` is generated from an actual computed value found elsewhere in
    this object or in the upstream Decision Engine results; nothing here is
    template filler unconnected to real numbers.
    """
    headline: str
    decision: DecisionSummary
    cost_contribution: CostContribution
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    alternatives_compared: list[AlternativeComparison] = Field(default_factory=list)
    rejected_vessels: list[RejectedVesselSummary] = Field(default_factory=list)
