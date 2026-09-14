"""
Module 3.4 — Delivered Cost Engine.

For every (candidate, scenario) pair, computes a fully itemized delivered
cost. Pure function — no optimization decisions live here, only arithmetic
— so it can be unit-tested exhaustively and reused unchanged by both the
optimizer (3.5) and a future backtester.

Cost basis is fully per-unit/rate-based (spec-review issue #1 fix): never a
full-cargo number scaled after the fact. Freight cost branches by pricing
basis (voyage $/tonne vs. TC $/day, issue #7). Deadhead is duration-based
(issue #8). Turnaround composes base + current congestion + scenario shock
correctly, without double-counting (issue #9). Despatch is included as
demurrage's mirror (issue #10).
"""
from __future__ import annotations

from datetime import timedelta

from app.cost.despatch_demurrage import compute_demurrage_and_despatch
from app.cost.params_loader import CostParameters
from app.feasibility import rules
from app.schemas.candidates import CandidateOption, CandidateSet, CostBreakdown, CostMatrix, CostRow, PricingBasis
from app.schemas.common import CargoRequirement, PortFeasibilityResult, RouteDistance, ScenarioSet, Vessel, VesselAvailability


def _laden_voyage_days(vessel: Vessel, distances: list[RouteDistance], origin_port_id: str, destination_port_id: str) -> float:
    dist = rules.lookup_distance(distances, origin_port_id, destination_port_id)
    return dist / vessel.service_speed_knots / 24.0


def _ballast_days(vessel: Vessel, availability: VesselAvailability, distances: list[RouteDistance], origin_port_id: str) -> float:
    dist = rules.lookup_distance(distances, availability.open_port_id, origin_port_id)
    return dist / vessel.service_speed_knots / 24.0


def compute_cost_row(
    candidate: CandidateOption,
    scenario_id: str,
    scenario_set: ScenarioSet,
    vessel: Vessel,
    availability: VesselAvailability,
    cargo: CargoRequirement,
    port_feasibility: PortFeasibilityResult,
    distances: list[RouteDistance],
    params: CostParameters,
) -> CostRow:
    """Computes one row of the cost matrix — a single (candidate, scenario) pair."""
    scenario = next(s for s in scenario_set.scenarios if s.scenario_id == scenario_id)

    # --- Freight cost: branches by pricing basis, per-unit basis throughout (issue #1, #7) ---
    if candidate.pricing_basis == PricingBasis.VOYAGE_PER_TONNE:
        freight_cost_per_tonne = scenario_set.voyage_rate_on(scenario_id, candidate.charter_epoch)
        tc_hire_cost = 0.0
    else:  # TIME_CHARTER_PER_DAY
        hire_rate = scenario_set.tc_rate_on(scenario_id, candidate.vessel_class.value, candidate.charter_epoch)
        if hire_rate is None:
            raise ValueError(
                f"TC_RATES_UNAVAILABLE: candidate {candidate.candidate_id} is TC-priced but scenario "
                f"{scenario_id} has no tc_hire_path for {candidate.vessel_class.value} on {candidate.charter_epoch} "
                "— this should have been excluded at 3.3 generation time"
            )
        # [Fix — found during sanity-check review] TC hire is owed from delivery
        # (when the vessel comes on-hire, which for a trip/single-voyage TC
        # includes the ballast leg to the load port) through redelivery at
        # discharge — NOT just the laden leg. Using laden-only systematically
        # underpriced TC candidates relative to the equivalent voyage charter
        # for the identical vessel and route (verified: laden-only gave a TC
        # total less than half the voyage-charter total for the same voyage,
        # which is not economically plausible). The mock scenario generator's
        # $/day rate is itself calibrated off a round-trip reference period,
        # so charging it over ballast+laden (the outbound on-hire duration we
        # actually model) is the closer approximation available without also
        # modeling a redelivery ballast leg back off-hire.
        ballast_days = _ballast_days(vessel, availability, distances, candidate.origin_port_id)
        laden_days = _laden_voyage_days(vessel, distances, candidate.origin_port_id, candidate.destination_port_id)
        on_hire_days = ballast_days + laden_days
        tc_hire_cost = hire_rate * on_hire_days
        freight_cost_per_tonne = 0.0  # this strategy's cost lives entirely in the fixed term

    # --- Waiting cost: days between earliest_departure and the chosen charter epoch ---
    waiting_days = max(0, (candidate.charter_epoch - cargo.earliest_departure).days)
    waiting_cost = waiting_days * params.wait_cost_per_day

    # --- Idle cost: vessel arrives at origin before the charter epoch and sits idle ---
    ballast_days = _ballast_days(vessel, availability, distances, candidate.origin_port_id)
    arrival_at_origin = availability.open_date + timedelta(days=ballast_days)
    idle_days = max(0.0, (candidate.charter_epoch - arrival_at_origin).total_seconds() / 86400.0)
    idle_cost = idle_days * params.idle_cost_per_day

    # --- Turnaround & demurrage/despatch (issue #9: correct, non-double-counted composition) ---
    dest_port_result = port_feasibility.get(candidate.destination_port_id)
    turnaround_days = (
        dest_port_result.base_turnaround_days
        + dest_port_result.current_congestion_days
        + scenario.base_congestion_shock_days
    )
    demurrage, despatch = compute_demurrage_and_despatch(turnaround_days, params)

    # --- Deadhead cost: duration-based, not distance-flat-rate (issue #8) ---
    deadhead_cost = ballast_days * (
        params.daily_opex_ballast[vessel.vessel_class.value]
        + params.bunker_consumption_tonnes_per_day[vessel.vessel_class.value] * params.bunker_price_usd_per_tonne
    )

    # --- Carbon cost [Backlog item — competitive-landscape review Section 5.4,
    # borrowed from Seven Oceans SOPF's EU ETS/FuelEU calculation]. Disabled by
    # default (params.carbon_cost_enabled=False -> always 0.0), so this never
    # changes existing behavior unless explicitly turned on in config. When
    # enabled, computed off TOTAL bunker consumption for the voyage (ballast +
    # laden leg, same per-day rate for both — a stated simplification; a real
    # implementation would differentiate laden vs. ballast consumption and
    # which specific legs fall under ETS scope). Independent of pricing basis
    # (voyage vs. TC) since carbon cost is an environmental fact of the
    # voyage, not a function of who commercially bears it.
    if params.carbon_cost_enabled:
        laden_days_for_carbon = _laden_voyage_days(vessel, distances, candidate.origin_port_id, candidate.destination_port_id)
        total_bunker_days = ballast_days + laden_days_for_carbon
        total_bunker_tonnes = total_bunker_days * params.bunker_consumption_tonnes_per_day[vessel.vessel_class.value]
        total_co2_tonnes = total_bunker_tonnes * params.co2_emission_factor_tonnes_per_tonne_bunker
        carbon_cost = total_co2_tonnes * params.carbon_price_usd_per_tonne_co2
    else:
        carbon_cost = 0.0

    # --- Port cost (fixed) ---
    port_cost = params.port_cost_flat.get(candidate.destination_port_id, 0.0) + params.port_cost_flat.get(candidate.origin_port_id, 0.0)

    fixed_cost = waiting_cost + demurrage - despatch + idle_cost + deadhead_cost + port_cost + tc_hire_cost + carbon_cost

    return CostRow(
        candidate_id=candidate.candidate_id,
        scenario_id=scenario_id,
        freight_cost_per_tonne=freight_cost_per_tonne,
        fixed_cost=fixed_cost,
        breakdown=CostBreakdown(
            port_cost=port_cost,
            waiting_cost=waiting_cost,
            idle_cost=idle_cost,
            deadhead_cost=deadhead_cost,
            demurrage=demurrage,
            despatch_credit=despatch,
            tc_hire_cost=tc_hire_cost,
            carbon_cost=carbon_cost,
        ),
    )


def compute_cost_matrix(
    cost_run_id: str,
    cargo: CargoRequirement,
    candidate_set: CandidateSet,
    scenario_set: ScenarioSet,
    vessels: list[Vessel],
    availabilities: list[VesselAvailability],
    port_feasibility: PortFeasibilityResult,
    distances: list[RouteDistance],
    params: CostParameters,
) -> CostMatrix:
    """
    Module 3.4 entry point. Computes the full (candidate x scenario) cost
    matrix for every non-null candidate. The null candidate carries no cost
    rows — 3.5 handles it as a distinct, always-available zero-freight
    fallback with its own (non-cost) semantics.
    """
    vessel_by_id = {v.vessel_id: v for v in vessels}
    availability_by_id = {a.vessel_id: a for a in availabilities}

    rows: list[CostRow] = []
    for candidate in candidate_set.non_null_candidates:
        vessel = vessel_by_id[candidate.vessel_id]
        availability = availability_by_id[candidate.vessel_id]
        for scenario in scenario_set.scenarios:
            rows.append(
                compute_cost_row(
                    candidate, scenario.scenario_id, scenario_set, vessel, availability,
                    cargo, port_feasibility, distances, params,
                )
            )

    return CostMatrix(
        cost_run_id=cost_run_id,
        cargo_requirement_id=cargo.cargo_requirement_id,
        cost_param_version=params.version,
        rows=rows,
    )
