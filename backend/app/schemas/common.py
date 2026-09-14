"""
Shared data contracts for the Decision Engine (SIH 26006).

These schemas are the frozen interface described in the Decision Engine
Module Specification, Section 0 and Sections 2-3 (vessel/port feasibility).
Every field here is deliberately typed and documented so 3.1/3.2 can be
built and unit-tested without the Intelligence Layer (2.x) existing yet.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RiskPreference(str, Enum):
    LOW = "LOW"
    BALANCED = "BALANCED"
    HIGH = "HIGH"


class VesselClass(str, Enum):
    HANDYSIZE = "HANDYSIZE"
    SUPRAMAX = "SUPRAMAX"
    PANAMAX = "PANAMAX"
    CAPESIZE = "CAPESIZE"


class DataSourceType(str, Enum):
    REAL = "REAL"
    MOCK = "MOCK"
    DERIVED = "DERIVED"


# ---------------------------------------------------------------------------
# Cargo requirement (user input, passed through unchanged)
# ---------------------------------------------------------------------------
class CargoRequirement(BaseModel):
    cargo_requirement_id: str
    commodity: str
    quantity_tonnes: float = Field(gt=0)
    origin_country: str
    origin_port_id: str
    destination_port_id: str
    delivery_deadline: date
    earliest_departure: date
    risk_preference: RiskPreference = RiskPreference.BALANCED

    @field_validator("delivery_deadline")
    @classmethod
    def deadline_after_departure(cls, v: date, info):
        earliest = info.data.get("earliest_departure")
        if earliest and v < earliest:
            raise ValueError("delivery_deadline must be on or after earliest_departure")
        return v


# ---------------------------------------------------------------------------
# Vessel master data
# ---------------------------------------------------------------------------
class Vessel(BaseModel):
    vessel_id: str
    name: str
    vessel_class: VesselClass
    dwt_tonnes: float = Field(gt=0)
    loa_m: float = Field(gt=0)
    beam_m: float = Field(gt=0)
    draft_laden_m: float = Field(gt=0)
    service_speed_knots: float = Field(gt=0)
    data_source_type: DataSourceType = DataSourceType.MOCK
    reliability_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="[Backlog item — competitive-landscape review Section 5.2, borrowed from "
        "Klaveness Digital's Pre-Vetting concept] 0.0-1.0, higher is better. MOCK/illustrative "
        "counterparty/performance signal (claims history, off-hire frequency, CII rating proxy) — "
        "NOT a physical feasibility fact, so it never gates 3.1's hard constraints. None if unknown.",
    )


class VesselAvailability(BaseModel):
    vessel_id: str
    open_date: date
    open_port_id: str
    data_source_type: DataSourceType = DataSourceType.MOCK


# ---------------------------------------------------------------------------
# Port master data
# ---------------------------------------------------------------------------
class Port(BaseModel):
    port_id: str
    name: str
    country: str
    max_draft_m: float = Field(gt=0)
    max_loa_m: float = Field(gt=0)
    max_beam_m: float = Field(gt=0)
    berth_count: int = Field(gt=0)
    cargo_handling_rate_tonnes_per_day: float = Field(gt=0)
    base_turnaround_days: float = Field(gt=0, description="Inherent handling/berthing time, EXCLUDING congestion")
    data_source_type: DataSourceType = DataSourceType.MOCK


class CongestionObservation(BaseModel):
    port_id: str
    observation_timestamp: date
    current_congestion_days: float = Field(ge=0)
    data_source_type: DataSourceType = DataSourceType.MOCK


# Distance reference table between two locodes (nautical miles) — used by 3.1
# origin-reachability check and by 3.4's deadhead cost. Kept here since both
# feasibility and cost modules need the same distance facts.
class RouteDistance(BaseModel):
    from_port_id: str
    to_port_id: str
    distance_nm: float = Field(ge=0, description="0 is valid — vessel already at this port")


# ---------------------------------------------------------------------------
# 2.2 Uncertainty/Scenario Engine — output contract (ASSUMED, per Decision
# Engine spec Section 0 — the Intelligence Layer isn't built yet, so the
# Decision Engine develops against a fixture conforming to this schema).
# ---------------------------------------------------------------------------
class DailyRate(BaseModel):
    date: date
    rate: float = Field(gt=0)


class Scenario(BaseModel):
    scenario_id: str
    headline_label: Optional[str] = Field(
        default=None, description="Nearest archetype label (S1_LOW/S2_BASE/S3_HIGH/S4_CONGESTION_SHOCK), for UI grouping only"
    )
    probability: float = Field(gt=0, le=1)
    voyage_freight_path_usd_per_tonne: list[DailyRate]
    tc_hire_path_usd_per_day: dict[str, list[DailyRate]] = Field(
        default_factory=dict, description="Keyed by VesselClass value; may be absent for classes without a TC forecast yet"
    )
    commodity_price_index: float = Field(default=1.0, gt=0)
    base_congestion_shock_days: float = Field(default=0.0, ge=0)
    vessel_availability_shock: float = Field(default=0.0, ge=0, le=1)
    assumptions: str = ""


class ScenarioSet(BaseModel):
    scenario_run_id: str
    forecast_run_id: str
    scenario_count: int
    headline_scenarios: list[str] = Field(default_factory=list)
    scenarios: list[Scenario]

    @field_validator("scenarios")
    @classmethod
    def probabilities_sum_to_one(cls, v: list[Scenario]):
        total = sum(s.probability for s in v)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"FORECAST_INPUT_INVALID: scenario probabilities sum to {total}, not 1.0")
        return v

    def voyage_rate_on(self, scenario_id: str, on_date: date) -> float:
        scenario = next(s for s in self.scenarios if s.scenario_id == scenario_id)
        row = next((r for r in scenario.voyage_freight_path_usd_per_tonne if r.date == on_date), None)
        if row is None:
            raise ValueError(f"INSUFFICIENT_FORECAST_HORIZON: no rate for {on_date} in scenario {scenario_id}")
        return row.rate

    def tc_rate_on(self, scenario_id: str, vessel_class: str, on_date: date) -> Optional[float]:
        scenario = next(s for s in self.scenarios if s.scenario_id == scenario_id)
        path = scenario.tc_hire_path_usd_per_day.get(vessel_class)
        if not path:
            return None
        row = next((r for r in path if r.date == on_date), None)
        return row.rate if row else None

    def has_meaningful_cvar_sample(self) -> bool:
        """Per spec-review issue #4: CVaR is only trustworthy at alpha=0.8 with >=20 scenarios."""
        return self.scenario_count >= 20


class ForecastPrediction(BaseModel):
    date: date
    p10: float
    p50: float
    p90: float
    unit: str = "USD/tonne"


class ForecastOutput(BaseModel):
    forecast_run_id: str
    route_id: str
    vessel_class: VesselClass
    generated_at: date
    horizon_days: int
    predictions: list[ForecastPrediction]
    model_id: str
    data_source_type: DataSourceType = DataSourceType.MOCK



class VesselCheckResult(BaseModel):
    vessel_id: str
    vessel_class: VesselClass
    feasible: bool
    capacity_ok: bool
    draft_ok: bool
    loa_ok: bool
    beam_ok: bool
    avail_ok: bool
    origin_ok: bool
    split_candidate: bool = Field(
        default=False,
        description="True if this vessel fails capacity_ok alone but is otherwise "
        "feasible, i.e. could still participate in a split-cargo strategy",
    )
    failed: list[str] = Field(default_factory=list)
    reason_text: Optional[str] = None
    reliability_score: Optional[float] = Field(
        default=None,
        description="[Backlog item, Section 5.2] Passed through from Vessel.reliability_score, "
        "purely informational — never affects `feasible`, which stays physical-constraints-only.",
    )
    reliability_flag: Optional[str] = Field(
        default=None,
        description="'LOW_RELIABILITY_RISK' if reliability_score is below "
        "config.VESSEL_RELIABILITY_FLAG_THRESHOLD, else None. Non-blocking — surfaced for the "
        "user/explanation layer and as an optional input to 3.6, never a feasibility gate.",
    )


class VesselFeasibilityResult(BaseModel):
    feasibility_run_id: str
    cargo_requirement_id: str
    vessels: list[VesselCheckResult]

    @property
    def feasible_vessels(self) -> list[VesselCheckResult]:
        return [v for v in self.vessels if v.feasible]

    @property
    def status(self) -> str:
        """
        [Fix — found via an API integration test] "usable" includes split-
        eligible vessels, not just strictly-feasible ones — the split-cargo
        MIP path (3.5) exists specifically to use vessels that fail
        capacity_ok alone. Returning NO_FEASIBLE_VESSEL whenever no SINGLE
        vessel covers the full cargo would incorrectly short-circuit the
        pipeline before 3.3 ever gets a chance to build split candidates.
        Whether a given split candidate clears the minimum economic lot
        size is 3.3's concern (MIN_ECONOMIC_LOT_TONNES), not 3.1's — this
        property only answers "is there anything here worth passing on."
        """
        return "OK" if (self.feasible_vessels or any(v.split_candidate for v in self.vessels)) else "NO_FEASIBLE_VESSEL"


# ---------------------------------------------------------------------------
# 3.2 Port Feasibility Engine — output contract
# ---------------------------------------------------------------------------
class PortCheckResult(BaseModel):
    port_id: str
    feasible: bool
    draft_ok: bool
    berth_ok: bool
    handling_ok: bool
    congestion_acceptable: bool
    base_turnaround_days: float
    current_congestion_days: float
    failed: list[str] = Field(default_factory=list)
    reason_text: Optional[str] = None


class PortFeasibilityResult(BaseModel):
    feasibility_run_id: str
    cargo_requirement_id: str
    ports: list[PortCheckResult]

    @property
    def feasible_ports(self) -> list[PortCheckResult]:
        return [p for p in self.ports if p.feasible]

    @property
    def status(self) -> str:
        """
        [Fix — found via an API integration test] Must require EVERY
        evaluated port (both origin and destination) to be feasible, not
        just at least one. The original `"OK" if feasible_ports else ...`
        check was satisfied as long as ANY port passed — meaning a fully
        infeasible destination with a fine origin silently reported "OK",
        since the origin alone made feasible_ports non-empty. A cargo
        requirement needs BOTH ends of the voyage to work.
        """
        return "OK" if (self.ports and all(p.feasible for p in self.ports)) else "NO_FEASIBLE_PORT"

    def get(self, port_id: str) -> Optional[PortCheckResult]:
        return next((p for p in self.ports if p.port_id == port_id), None)
