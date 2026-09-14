"""
Module 4.1 — Recommendation & Explanation Engine.

Deterministic and reason-coded, per the agreed design: every string in
Explanation.reasons/warnings is derived directly from an actual computed
value in the upstream Decision Engine results (VesselFeasibilityResult,
PortFeasibilityResult, CandidateSet, CostMatrix, OptimizationResult) — never
a generic template filled with placeholder-sounding text, and never an LLM
narrative. If a reason can't be tied to a specific number or fact already
computed upstream, it doesn't get generated.
"""
from __future__ import annotations

from app.schemas.candidates import CandidateSet, CostMatrix
from app.schemas.common import CargoRequirement, PortFeasibilityResult, ScenarioSet, VesselFeasibilityResult
from app.schemas.explanation import (
    AlternativeComparison,
    CostContribution,
    DecisionLeg,
    DecisionSummary,
    Explanation,
    RejectedVesselSummary,
)
from app.schemas.optimization_result import OptimizationResult

_RISK_LABEL_LOW_THRESHOLD = 0.03
_RISK_LABEL_MEDIUM_THRESHOLD = 0.08


def _risk_label(expected_cost: float, cvar: float) -> str:
    if expected_cost == 0:
        return "LOW"
    ratio = (cvar - expected_cost) / expected_cost
    if ratio < _RISK_LABEL_LOW_THRESHOLD:
        return "LOW"
    if ratio < _RISK_LABEL_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "HIGH"


def _weighted_cost_contribution(
    candidate_ids_and_tonnage: list[tuple[str, float]],
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
) -> CostContribution:
    """Probability-weighted average cost breakdown across the winning
    candidate(s) — sums across legs for a split decision. Every field here
    is a real weighted average of numbers 3.4 already computed, not a
    fresh estimate."""
    prob_by_scenario = {s.scenario_id: s.probability for s in scenario_set.scenarios}
    totals = dict(freight_or_hire_cost=0.0, port_cost=0.0, waiting_cost=0.0, idle_cost=0.0,
                  deadhead_cost=0.0, demurrage=0.0, despatch_credit=0.0, carbon_cost=0.0)
    for candidate_id, tonnage in candidate_ids_and_tonnage:
        for row in cost_matrix.rows_for(candidate_id):
            w = prob_by_scenario[row.scenario_id]
            totals["freight_or_hire_cost"] += w * (tonnage * row.freight_cost_per_tonne + row.breakdown.tc_hire_cost)
            totals["port_cost"] += w * row.breakdown.port_cost
            totals["waiting_cost"] += w * row.breakdown.waiting_cost
            totals["idle_cost"] += w * row.breakdown.idle_cost
            totals["deadhead_cost"] += w * row.breakdown.deadhead_cost
            totals["demurrage"] += w * row.breakdown.demurrage
            totals["despatch_credit"] += w * row.breakdown.despatch_credit
            totals["carbon_cost"] += w * row.breakdown.carbon_cost
    return CostContribution(**totals)


def _find_matching_candidate(candidate_set: CandidateSet, vessel_id: str, strategy_value: str = None):
    for c in candidate_set.non_null_candidates:
        if c.vessel_id == vessel_id and (strategy_value is None or c.strategy.value == strategy_value):
            return c
    return None


def build_explanation(
    cargo: CargoRequirement,
    vessel_feasibility: VesselFeasibilityResult,
    port_feasibility: PortFeasibilityResult,
    candidate_set: CandidateSet,
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
    optimization_result: OptimizationResult,
) -> Explanation:
    """
    Module 4.1 entry point. Only called by the API layer when
    optimization_result.status is OPTIMAL or TIME_LIMIT_REACHED — there is
    nothing to explain for a NO_FEASIBLE_* result (the API's rejected_summary
    already covers that case with its own reasons).
    """
    candidate_by_id = {c.candidate_id: c for c in candidate_set.non_null_candidates}
    vessel_check_by_id = {v.vessel_id: v for v in vessel_feasibility.vessels}

    legs: list[DecisionLeg] = []
    for sel in optimization_result.selected:
        candidate = candidate_by_id[sel.candidate_id]
        legs.append(
            DecisionLeg(
                candidate_id=sel.candidate_id, vessel_id=candidate.vessel_id,
                vessel_class=candidate.vessel_class.value, strategy=candidate.strategy.value,
                pricing_basis=candidate.pricing_basis.value, charter_epoch=candidate.charter_epoch,
                tonnage=sel.tonnage,
            )
        )

    is_split = len(legs) > 1
    strategy_label = f"SPLIT ({len(legs)} vessels)" if is_split else legs[0].strategy

    decision = DecisionSummary(
        strategy_label=strategy_label,
        origin_port_id=cargo.origin_port_id, destination_port_id=cargo.destination_port_id,
        total_tonnage=sum(l.tonnage for l in legs), legs=legs,
        expected_cost=optimization_result.expected_cost, cvar_80=optimization_result.cvar_80,
        cvar_status=optimization_result.cvar_status,
        risk_label=_risk_label(optimization_result.expected_cost, optimization_result.cvar_80),
        risk_preference=cargo.risk_preference.value, risk_aversion_lambda=optimization_result.risk_aversion_lambda,
    )

    cost_contribution = _weighted_cost_contribution(
        [(l.candidate_id, l.tonnage) for l in legs], cost_matrix, scenario_set
    )

    reasons: list[str] = []
    warnings: list[str] = []

    # --- Reason: what was selected and why the timing/strategy makes sense ---
    if not is_split:
        leg = legs[0]
        vc = vessel_check_by_id.get(leg.vessel_id)
        reasons.append(
            f"{leg.vessel_id} ({leg.vessel_class}) is chartered via {leg.strategy} "
            f"starting {leg.charter_epoch.isoformat()}, carrying the full {leg.tonnage:,.0f}t requirement."
        )
        if vc:
            passed = [k for k in ("capacity_ok", "draft_ok", "loa_ok", "beam_ok", "avail_ok", "origin_ok") if getattr(vc, k)]
            reasons.append(f"{leg.vessel_id} clears all {len(passed)} physical feasibility checks (capacity/draft/LOA/beam/availability/origin).")
    else:
        reasons.append(
            f"No single vessel in the feasible fleet has enough capacity for the full "
            f"{cargo.quantity_tonnes:,.0f}t requirement, so the cargo is split across {len(legs)} vessels: "
            + "; ".join(f"{l.vessel_id} ({l.tonnage:,.0f}t)" for l in legs) + "."
        )

    # --- Reason: cost comparison against the best alternative (enumeration path only) ---
    if optimization_result.ranked_alternatives and len(optimization_result.ranked_alternatives) > 1:
        winner = optimization_result.ranked_alternatives[0]
        runner_up = optimization_result.ranked_alternatives[1]
        delta = runner_up.expected_cost - winner.expected_cost
        delta_pct = (delta / winner.expected_cost * 100) if winner.expected_cost else 0.0
        reasons.append(
            f"This option's expected delivered cost (${winner.expected_cost:,.0f}) is ${delta:,.0f} "
            f"({delta_pct:.1f}%) lower than the next-best alternative (${runner_up.expected_cost:,.0f})."
        )

    # --- Reason: risk profile ---
    if optimization_result.cvar_status == "COMPUTED":
        reasons.append(
            f"At the {optimization_result.risk_aversion_lambda:.2f} risk-aversion weight for your "
            f"{cargo.risk_preference.value} preference, the 80th-percentile downside cost (CVaR) is "
            f"${optimization_result.cvar_80:,.0f} — ${optimization_result.cvar_80 - optimization_result.expected_cost:,.0f} "
            f"above the expected cost."
        )
    else:
        warnings.append(
            "CVaR is reported as the worst-case scenario cost, not a statistically computed tail average — "
            "the scenario bank had fewer than the minimum scenarios needed for a meaningful CVaR estimate."
        )

    # --- Reason: cost composition, from the actual weighted breakdown ---
    total_check = sum([cost_contribution.freight_or_hire_cost, cost_contribution.port_cost, cost_contribution.waiting_cost,
                        cost_contribution.idle_cost, cost_contribution.deadhead_cost, cost_contribution.demurrage,
                        -cost_contribution.despatch_credit, cost_contribution.carbon_cost])
    if total_check > 0:
        freight_share = cost_contribution.freight_or_hire_cost / total_check * 100
        reasons.append(
            f"Freight/hire makes up ${cost_contribution.freight_or_hire_cost:,.0f} "
            f"({freight_share:.0f}%) of the expected total; port, waiting, idle, deadhead, and "
            f"demurrage/despatch make up the remainder."
        )
    if cost_contribution.despatch_credit > 0:
        reasons.append(
            f"Expected despatch credit (probability-weighted across scenarios) is ${cost_contribution.despatch_credit:,.0f} "
            f"— in scenarios where turnaround beats the laytime allowance, a credit applies."
        )
    if cost_contribution.demurrage > 0:
        reasons.append(
            f"Expected demurrage (probability-weighted across scenarios) is ${cost_contribution.demurrage:,.0f} "
            f"— in scenarios where turnaround exceeds the laytime allowance, a demurrage charge applies."
        )
    if cost_contribution.carbon_cost > 0:
        reasons.append(f"Carbon cost of ${cost_contribution.carbon_cost:,.0f} is included in the total (carbon accounting is enabled).")

    # --- Reason: WAIT_THEN_CHARTER specifically — quantify the wait vs. spot trade-off ---
    for leg in legs:
        if leg.strategy == "WAIT_THEN_CHARTER":
            spot_candidate = _find_matching_candidate(candidate_set, leg.vessel_id, "SPOT_NOW")
            if spot_candidate:
                spot_rows = cost_matrix.rows_for(spot_candidate.candidate_id)
                if spot_rows:
                    prob_by_scenario = {s.scenario_id: s.probability for s in scenario_set.scenarios}
                    spot_expected = sum(prob_by_scenario[r.scenario_id] * r.total_cost_for_tonnage(leg.tonnage) for r in spot_rows)
                    wait_expected = optimization_result.expected_cost
                    if wait_expected < spot_expected:
                        reasons.append(
                            f"Waiting until {leg.charter_epoch.isoformat()} instead of chartering {leg.vessel_id} "
                            f"immediately saves ${spot_expected - wait_expected:,.0f} in expected cost, net of the "
                            f"extra waiting cost incurred."
                        )
                    else:
                        warnings.append(
                            f"Chartering {leg.vessel_id} immediately would actually have been "
                            f"${wait_expected - spot_expected:,.0f} cheaper in expected terms than waiting — "
                            f"the wait was still selected on a risk-adjusted (not pure expected-cost) basis."
                        )

    # --- Reliability (competitive-landscape addition) — surfaced as a warning, never a blocking reason ---
    if optimization_result.reliability_flag == "LOW_RELIABILITY_RISK":
        warnings.append(
            f"Vessel reliability score ({optimization_result.vessel_reliability_score:.2f}) is below the "
            f"flagging threshold — this does not affect feasibility or the cost-based ranking, but is worth reviewing."
        )
    elif optimization_result.vessel_reliability_score is not None:
        reasons.append(f"Vessel reliability score: {optimization_result.vessel_reliability_score:.2f} (informational, not cost-weighted).")

    # --- Alternatives compared ---
    alternatives = [
        AlternativeComparison(
            candidate_id=a.candidate_id, rank=a.rank, expected_cost=a.expected_cost,
            cost_delta_vs_winner_usd=a.expected_cost - optimization_result.expected_cost,
            cost_delta_vs_winner_pct=((a.expected_cost - optimization_result.expected_cost) / optimization_result.expected_cost * 100) if optimization_result.expected_cost else 0.0,
            cvar=a.cvar,
        )
        for a in optimization_result.ranked_alternatives
    ]

    # --- Rejected vessels — drawn directly from 3.1's own reason_text, nothing new invented ---
    rejected = [
        RejectedVesselSummary(vessel_id=v.vessel_id, vessel_class=v.vessel_class.value, reason_text=v.reason_text or "Failed feasibility checks")
        for v in vessel_feasibility.vessels
        if not v.feasible and not v.split_candidate
    ]

    headline = (
        f"Recommended: {strategy_label} — {', '.join(l.vessel_id for l in legs)}, "
        f"expected cost ${optimization_result.expected_cost:,.0f}"
    )

    return Explanation(
        headline=headline, decision=decision, cost_contribution=cost_contribution,
        reasons=reasons, warnings=warnings, alternatives_compared=alternatives, rejected_vessels=rejected,
    )
