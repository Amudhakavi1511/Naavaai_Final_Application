"""
Module 4.2 — What-If Simulator.

Per the design established in the Decision Engine spec (Section 9.4): the
what-if simulator has NO separate code path. It transforms the base
CargoRequirement/ScenarioSet/reference-data according to the requested
changes, then calls the exact same `run_decision_engine()` used by
`POST /optimization/run` — twice (once unmodified as the baseline, once
modified) — so any correctness fix to the core pipeline automatically
applies here too, and there is only one pipeline to keep tested and honest.
"""
from __future__ import annotations

from datetime import timedelta

from app.api.orchestration import run_decision_engine
from app.api.reference_data import ReferenceData
from app.api.schemas import DecisionEngineResponse, OptimizationRunRequest
from app.api.whatif_schemas import WhatIfChanges, WhatIfDelta, WhatIfRequest, WhatIfResponse
from app.schemas.common import CargoRequirement, DailyRate, Scenario, ScenarioSet, VesselAvailability


class WhatIfValidationError(ValueError):
    """Raised when applying the requested changes produces an invalid
    CargoRequirement (e.g. a deadline shift that moves the deadline before
    earliest_departure) — a client input problem, not a server error."""


def _apply_freight_shock(scenario_set: ScenarioSet, pct: float) -> ScenarioSet:
    if pct == 0.0:
        return scenario_set
    factor = 1.0 + pct / 100.0
    new_scenarios = []
    for s in scenario_set.scenarios:
        new_voyage = [DailyRate(date=r.date, rate=r.rate * factor) for r in s.voyage_freight_path_usd_per_tonne]
        new_tc = {
            vessel_class: [DailyRate(date=r.date, rate=r.rate * factor) for r in path]
            for vessel_class, path in s.tc_hire_path_usd_per_day.items()
        }
        new_scenarios.append(s.model_copy(update={
            "voyage_freight_path_usd_per_tonne": new_voyage,
            "tc_hire_path_usd_per_day": new_tc,
        }))
    return scenario_set.model_copy(update={"scenarios": new_scenarios})


def _apply_congestion_shock(scenario_set: ScenarioSet, extra_days: float) -> ScenarioSet:
    if extra_days == 0.0:
        return scenario_set
    new_scenarios = [
        s.model_copy(update={"base_congestion_shock_days": s.base_congestion_shock_days + extra_days})
        for s in scenario_set.scenarios
    ]
    return scenario_set.model_copy(update={"scenarios": new_scenarios})


def _apply_deadline_shift(cargo: CargoRequirement, shift_days: int) -> CargoRequirement:
    if shift_days == 0:
        return cargo
    new_deadline = cargo.delivery_deadline + timedelta(days=shift_days)
    # pydantic v2's model_copy does NOT re-run validators, so the
    # deadline->earliest_departure ordering check (normally enforced at
    # construction) must be re-checked explicitly here.
    if new_deadline < cargo.earliest_departure:
        raise WhatIfValidationError(
            f"deadline_shift_days={shift_days} moves delivery_deadline to {new_deadline}, "
            f"which is before earliest_departure ({cargo.earliest_departure})"
        )
    return cargo.model_copy(update={"delivery_deadline": new_deadline})


def _apply_risk_preference(cargo: CargoRequirement, risk_preference) -> CargoRequirement:
    if risk_preference is None:
        return cargo
    return cargo.model_copy(update={"risk_preference": risk_preference})


def _apply_vessel_availability_shock(availabilities: list[VesselAvailability], shock_days: float) -> list[VesselAvailability]:
    if shock_days == 0.0:
        return availabilities
    return [a.model_copy(update={"open_date": a.open_date + timedelta(days=shock_days)}) for a in availabilities]


def apply_changes(
    cargo: CargoRequirement, scenario_set: ScenarioSet, reference_data: ReferenceData, changes: WhatIfChanges
) -> tuple[CargoRequirement, ScenarioSet, ReferenceData]:
    """Returns a NEW (cargo, scenario_set, reference_data) tuple — the
    originals are never mutated, so the baseline run is unaffected."""
    new_cargo = _apply_deadline_shift(cargo, changes.deadline_shift_days)
    new_cargo = _apply_risk_preference(new_cargo, changes.risk_preference)

    new_scenario_set = _apply_freight_shock(scenario_set, changes.freight_shock_pct)
    new_scenario_set = _apply_congestion_shock(new_scenario_set, changes.congestion_shock_days)

    new_availabilities = _apply_vessel_availability_shock(reference_data.availabilities, changes.vessel_availability_shock_days)
    new_reference_data = ReferenceData(
        vessels=reference_data.vessels, availabilities=new_availabilities,
        ports_by_id=reference_data.ports_by_id, congestion_observations=reference_data.congestion_observations,
        distances=reference_data.distances, cost_params=reference_data.cost_params,
    )

    return new_cargo, new_scenario_set, new_reference_data


def _winning_vessel_ids(response: DecisionEngineResponse) -> list[str]:
    if response.optimization_result is None or response.candidate_set is None:
        return []
    candidate_by_id = {c.candidate_id: c for c in response.candidate_set.candidates}
    return [
        candidate_by_id[leg.candidate_id].vessel_id
        for leg in response.optimization_result.selected
        if leg.candidate_id in candidate_by_id and candidate_by_id[leg.candidate_id].vessel_id
    ]


def build_delta(baseline: DecisionEngineResponse, modified: DecisionEngineResponse) -> WhatIfDelta:
    baseline_vessels = _winning_vessel_ids(baseline)
    modified_vessels = _winning_vessel_ids(modified)
    decision_changed = (baseline.status != modified.status) or (set(baseline_vessels) != set(modified_vessels))

    cost_change_usd = None
    cost_change_pct = None
    summary_parts = []

    def vessel_list(ids: list[str]) -> str:
        return ", ".join(ids) if ids else "no vessel"

    if baseline.status != modified.status:
        summary_parts.append(f"Status changed from {baseline.status} to {modified.status}.")
    elif baseline.optimization_result and modified.optimization_result:
        base_cost = baseline.optimization_result.expected_cost
        mod_cost = modified.optimization_result.expected_cost
        cost_change_usd = mod_cost - base_cost
        cost_change_pct = (cost_change_usd / base_cost * 100) if base_cost else 0.0
        if decision_changed:
            summary_parts.append(
                f"The recommended vessel(s) changed from {vessel_list(baseline_vessels)} to "
                f"{vessel_list(modified_vessels)}; expected cost moved from ${base_cost:,.0f} to "
                f"${mod_cost:,.0f} ({'+' if cost_change_usd >= 0 else ''}{cost_change_pct:.1f}%)."
            )
        else:
            summary_parts.append(
                f"The same decision ({vessel_list(modified_vessels)}) remains optimal; expected cost "
                f"moved from ${base_cost:,.0f} to ${mod_cost:,.0f} "
                f"({'+' if cost_change_usd >= 0 else ''}{cost_change_pct:.1f}%)."
            )
    else:
        summary_parts.append("No optimization result available for one or both runs to compare costs.")

    return WhatIfDelta(
        decision_changed=decision_changed,
        baseline_status=baseline.status, modified_status=modified.status,
        baseline_winning_vessel_ids=baseline_vessels, modified_winning_vessel_ids=modified_vessels,
        expected_cost_change_usd=cost_change_usd, expected_cost_change_pct=cost_change_pct,
        summary=" ".join(summary_parts),
    )


def run_what_if(request: WhatIfRequest, base_reference_data: ReferenceData) -> WhatIfResponse:
    """Module 4.2 entry point. Runs the pipeline twice: baseline (unmodified
    inputs) and modified (per `request.changes`) — both through the exact
    same `run_decision_engine()`."""
    # Resolve the bank once, here, so the baseline and the modified run are
    # provably shocking the SAME scenarios. Resolving it separately in each
    # branch would be the kind of subtle mismatch that makes a what-if delta
    # meaningless without ever throwing an error.
    scenario_set = request.scenario_set or base_reference_data.default_scenario_set

    baseline_request = OptimizationRunRequest(cargo=request.cargo, scenario_set=scenario_set)
    baseline = run_decision_engine(baseline_request, base_reference_data)

    new_cargo, new_scenario_set, new_reference_data = apply_changes(
        request.cargo, scenario_set, base_reference_data, request.changes
    )
    modified_request = OptimizationRunRequest(cargo=new_cargo, scenario_set=new_scenario_set)
    modified = run_decision_engine(modified_request, new_reference_data)

    delta = build_delta(baseline, modified)
    return WhatIfResponse(baseline=baseline, modified=modified, delta=delta)
