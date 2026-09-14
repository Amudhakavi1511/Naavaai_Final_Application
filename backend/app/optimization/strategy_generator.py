"""
Module 3.3 — Charter Strategy Generator.

Produces the finite candidate set that 3.5 optimizes over. Per the Decision
Engine spec Section 4.2, the main engineering job here is disciplined
enumeration + pruning, not creativity — an unpruned cartesian product of
vessels x strategies x epochs would explode combinatorially.
"""
from __future__ import annotations

from app import config
from app.optimization import pruning
from app.schemas.candidates import CandidateOption, CandidateSet, CharterStrategy, PricingBasis
from app.schemas.common import (
    CargoRequirement,
    PortFeasibilityResult,
    RouteDistance,
    ScenarioSet,
    Vessel,
    VesselAvailability,
    VesselFeasibilityResult,
)

NULL_CANDIDATE_ID = "C-NULL"


def _make_null_candidate() -> CandidateOption:
    return CandidateOption(candidate_id=NULL_CANDIDATE_ID, is_null=True)


def _generate_for_vessel(
    vessel: Vessel,
    availability: VesselAvailability,
    cargo: CargoRequirement,
    distances: list[RouteDistance],
    scenario_set: ScenarioSet,
    counter: list[int],
) -> tuple[list[CandidateOption], list[str]]:
    """Generates every (strategy, epoch) candidate for a single vessel, applying
    the epoch and strategy-type pruning rules. Returns (candidates, notes)."""
    out: list[CandidateOption] = []
    notes: list[str] = []

    earliest_dep, latest_dep, stepped_epochs = pruning.valid_epochs_for_vessel(
        vessel, availability, cargo, distances
    )
    if earliest_dep > latest_dep:
        notes.append(f"{vessel.vessel_id}: no valid departure window (data inconsistency with 3.1's clearance) — skipped")
        return out, notes

    strategies = pruning.strategy_types_for_cargo(cargo)
    split_eligible = vessel.dwt_tonnes < cargo.quantity_tonnes

    def next_id() -> str:
        counter[0] += 1
        return f"C-{counter[0]:04d}"

    def tc_rates_available() -> bool:
        return any(vessel.vessel_class.value in s.tc_hire_path_usd_per_day for s in scenario_set.scenarios)

    for strategy in strategies:
        if strategy == CharterStrategy.SPOT_NOW:
            out.append(
                CandidateOption(
                    candidate_id=next_id(), vessel_id=vessel.vessel_id, vessel_class=vessel.vessel_class,
                    strategy=strategy, pricing_basis=PricingBasis.VOYAGE_PER_TONNE, charter_epoch=earliest_dep,
                    origin_port_id=cargo.origin_port_id, destination_port_id=cargo.destination_port_id,
                    capacity_tonnes=vessel.dwt_tonnes, split_eligible=split_eligible,
                )
            )

        elif strategy == CharterStrategy.WAIT_THEN_CHARTER:
            for epoch in stepped_epochs:
                out.append(
                    CandidateOption(
                        candidate_id=next_id(), vessel_id=vessel.vessel_id, vessel_class=vessel.vessel_class,
                        strategy=strategy, pricing_basis=PricingBasis.VOYAGE_PER_TONNE, charter_epoch=epoch,
                        origin_port_id=cargo.origin_port_id, destination_port_id=cargo.destination_port_id,
                        capacity_tonnes=vessel.dwt_tonnes, split_eligible=split_eligible,
                    )
                )

        elif strategy in (CharterStrategy.SHORT_TERM, CharterStrategy.MEDIUM_TERM, CharterStrategy.COA):
            # Contract rule: TC hire path must exist for this vessel class,
            # or this strategy type is excluded and logged, never silently
            # priced as if it were a voyage charter (spec-review issue #7).
            if not tc_rates_available():
                notes.append(f"{vessel.vessel_id}: {strategy.value} excluded — TC_RATES_UNAVAILABLE for {vessel.vessel_class.value}")
                continue
            for epoch in [earliest_dep] + stepped_epochs:
                out.append(
                    CandidateOption(
                        candidate_id=next_id(), vessel_id=vessel.vessel_id, vessel_class=vessel.vessel_class,
                        strategy=strategy, pricing_basis=PricingBasis.TIME_CHARTER_PER_DAY, charter_epoch=epoch,
                        origin_port_id=cargo.origin_port_id, destination_port_id=cargo.destination_port_id,
                        capacity_tonnes=vessel.dwt_tonnes, split_eligible=split_eligible,
                    )
                )

    return out, notes


def generate_candidates(
    candidate_run_id: str,
    cargo: CargoRequirement,
    vessels: list[Vessel],
    availabilities: list[VesselAvailability],
    vessel_feasibility: VesselFeasibilityResult,
    port_feasibility: PortFeasibilityResult,
    distances: list[RouteDistance],
    scenario_set: ScenarioSet,
) -> CandidateSet:
    """
    Module 3.3 entry point.

    Consumes 3.1's VesselFeasibilityResult and 3.2's PortFeasibilityResult
    DIRECTLY, per the module dependency graph — if either upstream status is
    not OK, this returns a candidate set containing only the null candidate
    (status NO_FEASIBLE_STRATEGY), matching the Section 8 orchestration
    sequence: 3.3 never re-derives feasibility itself.
    """
    notes: list[str] = []
    candidates: list[CandidateOption] = [_make_null_candidate()]

    if port_feasibility.status != "OK":
        notes.append("NO_FEASIBLE_PORT upstream — no strategies generated beyond the null candidate")
        return CandidateSet(candidate_run_id=candidate_run_id, cargo_requirement_id=cargo.cargo_requirement_id, candidates=candidates, generation_notes=notes)

    eligible_checks = [v for v in vessel_feasibility.vessels if v.feasible or v.split_candidate]
    if not eligible_checks:
        notes.append("NO_FEASIBLE_VESSEL upstream — no strategies generated beyond the null candidate")
        return CandidateSet(candidate_run_id=candidate_run_id, cargo_requirement_id=cargo.cargo_requirement_id, candidates=candidates, generation_notes=notes)

    vessel_by_id = {v.vessel_id: v for v in vessels}
    availability_by_id = {a.vessel_id: a for a in availabilities}
    eligible_vessels = [vessel_by_id[c.vessel_id] for c in eligible_checks if c.vessel_id in vessel_by_id]

    # Pruning rule 5 (issue #11): drop split-eligible vessels too small to
    # ever meet the minimum economic lot. Vessels big enough to carry the
    # full cargo alone are unaffected by this filter.
    before_lot_filter = len(eligible_vessels)
    eligible_vessels = pruning.filter_min_economic_lot(eligible_vessels, cargo)
    if len(eligible_vessels) < before_lot_filter:
        notes.append(
            f"{before_lot_filter - len(eligible_vessels)} split-eligible vessel(s) excluded — "
            f"below MIN_ECONOMIC_LOT_TONNES={config.MIN_ECONOMIC_LOT_TONNES:,}"
        )

    # Pruning rule 3: cap to top-N per class by cost-today proxy.
    ranked = pruning.rank_vessels_by_cost_today(eligible_vessels, scenario_set, cargo)
    ranked_vessels = [v for v, _ in ranked]
    before_cap = len(ranked_vessels)
    capped_vessels = pruning.filter_top_n_per_class(ranked_vessels)
    if len(capped_vessels) < before_cap:
        notes.append(f"{before_cap - len(capped_vessels)} vessel(s) excluded by TOP_N_VESSELS_PER_CLASS={config.TOP_N_VESSELS_PER_CLASS}")

    counter = [0]
    for vessel in capped_vessels:
        availability = availability_by_id.get(vessel.vessel_id)
        if availability is None:
            continue
        vessel_candidates, vessel_notes = _generate_for_vessel(vessel, availability, cargo, distances, scenario_set, counter)
        candidates.extend(vessel_candidates)
        notes.extend(vessel_notes)

    return CandidateSet(
        candidate_run_id=candidate_run_id,
        cargo_requirement_id=cargo.cargo_requirement_id,
        candidates=candidates,
        generation_notes=notes,
    )
