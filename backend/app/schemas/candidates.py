from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import VesselClass


class CharterStrategy(str, Enum):
    SPOT_NOW = "SPOT_NOW"
    WAIT_THEN_CHARTER = "WAIT_THEN_CHARTER"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    COA = "COA"


class PricingBasis(str, Enum):
    """Which market a candidate's freight is priced in — drives 3.4's cost-basis branch."""
    VOYAGE_PER_TONNE = "VOYAGE_PER_TONNE"
    TIME_CHARTER_PER_DAY = "TIME_CHARTER_PER_DAY"


class CandidateOption(BaseModel):
    candidate_id: str
    is_null: bool = False
    vessel_id: Optional[str] = None
    vessel_class: Optional[VesselClass] = None
    strategy: Optional[CharterStrategy] = None
    pricing_basis: Optional[PricingBasis] = None
    charter_epoch: Optional[date] = None
    origin_port_id: Optional[str] = None
    destination_port_id: Optional[str] = None
    capacity_tonnes: Optional[float] = Field(
        default=None, description="Vessel's DWT — the cap[c] used by 3.5's q[c] <= cap[c]*y[c] constraint"
    )
    split_eligible: bool = Field(
        default=False, description="True if this candidate's vessel has capacity < cargo_qty but >= MIN_ECONOMIC_LOT_TONNES"
    )
    excluded_strategies: list[str] = Field(
        default_factory=list, description="Strategy types considered but not generated for this vessel, with reason (e.g. TC_RATES_UNAVAILABLE)"
    )


class CostBreakdown(BaseModel):
    port_cost: float
    waiting_cost: float
    idle_cost: float
    deadhead_cost: float
    demurrage: float
    despatch_credit: float
    tc_hire_cost: float = Field(default=0.0, description="Non-zero only for TIME_CHARTER_PER_DAY candidates")
    carbon_cost: float = Field(
        default=0.0,
        description="EU ETS/FuelEU-style carbon cost. Zero unless CostParameters.carbon_cost_enabled=True "
        "(disabled by default — MOCK price, stated simplification, see cost_parameters.yaml)",
    )


class CostRow(BaseModel):
    candidate_id: str
    scenario_id: str
    # [Spec-review issue #1 fix] cost basis split: freight_cost_per_tonne scales
    # with the tonnage a candidate actually carries (q[c] in 3.5's MIP);
    # fixed_cost does NOT scale with tonnage — it's owed simply because the
    # candidate is used at all (y[c]=1), regardless of how much cargo it carries.
    freight_cost_per_tonne: float = Field(description="USD/tonne, 0.0 for TIME_CHARTER_PER_DAY candidates")
    fixed_cost: float = Field(description="USD, includes tc_hire_cost for TC-priced candidates")
    breakdown: CostBreakdown

    def total_cost_for_tonnage(self, tonnage: float) -> float:
        """total_delivered_cost for a SPECIFIC tonnage allocation — computed
        on demand, never stored pre-scaled (that pre-scaling was the v1 bug)."""
        return tonnage * self.freight_cost_per_tonne + self.fixed_cost


class CostMatrix(BaseModel):
    cost_run_id: str
    cargo_requirement_id: str
    cost_param_version: str
    rows: list[CostRow]

    def rows_for(self, candidate_id: str) -> list[CostRow]:
        return [r for r in self.rows if r.candidate_id == candidate_id]

    def row(self, candidate_id: str, scenario_id: str) -> CostRow:
        return next(r for r in self.rows if r.candidate_id == candidate_id and r.scenario_id == scenario_id)


class CandidateSet(BaseModel):
    candidate_run_id: str
    cargo_requirement_id: str
    candidates: list[CandidateOption]
    generation_notes: list[str] = Field(default_factory=list)

    @property
    def non_null_candidates(self) -> list[CandidateOption]:
        return [c for c in self.candidates if not c.is_null]

    @property
    def status(self) -> str:
        return "OK" if self.non_null_candidates else "NO_FEASIBLE_STRATEGY"

