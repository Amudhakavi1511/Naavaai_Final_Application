"""
Module 3.6 — Risk Engine.

Converts the scenario-indexed cost distribution for each candidate into risk
metrics: expected cost, variance, worst-case, CVaR (sample-size-gated), and
downside probability. Feeds 3.5's risk-adjusted objective and the dashboard's
risk display — never fed back into itself, and never presented with more
precision than the underlying scenario sample actually supports.
"""
from __future__ import annotations

from typing import Optional

from app import config
from app.schemas.candidates import CostMatrix
from app.schemas.common import CargoRequirement, ScenarioSet
from app.schemas.risk import CandidateRiskMetrics, RiskResult

# Display-only bucket thresholds on (CVaR - expected) / expected. NOT fed back
# into the optimizer's objective (spec-review issue #3) — purely for the
# dashboard's LOW/MEDIUM/HIGH badge.
_RISK_LABEL_LOW_THRESHOLD = 0.03
_RISK_LABEL_MEDIUM_THRESHOLD = 0.08


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total_weight = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def _weighted_variance(values: list[float], weights: list[float], mean: float) -> float:
    total_weight = sum(weights)
    return sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_weight


def weighted_cvar(costs: list[float], weights: list[float], alpha: float) -> float:
    """
    Weighted Conditional Value at Risk at confidence alpha: the probability-
    weighted average cost over the worst (1-alpha) probability mass.

    Handles the general (non-uniform-weight) case correctly, including a
    scenario that straddles the tail boundary (only part of its probability
    mass counts toward the tail average) — not just a simple "average of the
    N worst rows," which would be wrong whenever weights aren't exactly uniform.
    """
    if not costs:
        raise ValueError("weighted_cvar: empty cost list")
    order = sorted(range(len(costs)), key=lambda i: -costs[i])  # worst (highest cost) first
    tail_mass_needed = 1.0 - alpha
    accumulated = 0.0
    weighted_sum = 0.0
    for i in order:
        if accumulated >= tail_mass_needed:
            break
        take = min(weights[i], tail_mass_needed - accumulated)
        weighted_sum += costs[i] * take
        accumulated += take
    if accumulated <= 0:
        return costs[order[0]]
    return weighted_sum / accumulated


def _risk_label(downside_ratio: float) -> str:
    if downside_ratio < _RISK_LABEL_LOW_THRESHOLD:
        return "LOW"
    if downside_ratio < _RISK_LABEL_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "HIGH"


def compute_candidate_risk(
    candidate_id: str,
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
    tonnage: float,
    alpha: float = config.CVAR_ALPHA,
    min_scenarios_for_cvar: int = config.MIN_SCENARIOS_FOR_CVAR,
    reliability_score: Optional[float] = None,
) -> CandidateRiskMetrics:
    """
    Module 3.6 core computation for a single candidate, at a specific
    tonnage allocation (full cargo for a single-vessel candidate; a partial
    share for a split-cargo leg — the caller, 3.5, decides which).

    reliability_score: [Backlog item — competitive-landscape review Section
    5.2] optional, passed through from the candidate's vessel. Reported
    alongside the cost-based risk metrics purely for the explanation layer's
    benefit — deliberately NOT combined into `cvar`/`expected_cost`/the
    dollar-denominated objective. Counterparty/performance risk and cost
    variance are different units and different risk dimensions; folding a
    0-1 reliability score into a USD figure would require an arbitrary
    dollar-per-reliability-point conversion this prototype has no basis for.
    Left as a stated future-work item (Phase-0 Section 41), not silently
    forced into the existing objective.
    """
    rows = cost_matrix.rows_for(candidate_id)
    if not rows:
        raise ValueError(f"No cost rows found for candidate {candidate_id}")

    prob_by_scenario = {s.scenario_id: s.probability for s in scenario_set.scenarios}
    costs = [row.total_cost_for_tonnage(tonnage) for row in rows]
    weights = [prob_by_scenario[row.scenario_id] for row in rows]

    expected = _weighted_mean(costs, weights)
    variance = _weighted_variance(costs, weights, expected)
    worst_case = max(costs)
    downside_prob = sum(w for c, w in zip(costs, weights) if c > expected * 1.05) / sum(weights)

    # [Spec-review issue #4 fix] CVaR is only trusted with enough scenarios;
    # below the threshold it degenerates to (and is honestly labeled as)
    # worst-case, never presented as a precise number it isn't.
    if len(costs) >= min_scenarios_for_cvar:
        cvar = weighted_cvar(costs, weights, alpha)
        cvar_status = "COMPUTED"
    else:
        cvar = worst_case
        cvar_status = "NOT_MEANINGFUL_SAMPLE_SIZE"

    downside_ratio = (cvar - expected) / expected if expected != 0 else 0.0

    reliability_flag = None
    if reliability_score is not None and reliability_score < config.VESSEL_RELIABILITY_FLAG_THRESHOLD:
        reliability_flag = "LOW_RELIABILITY_RISK"

    return CandidateRiskMetrics(
        candidate_id=candidate_id,
        expected_cost=expected,
        variance=variance,
        worst_case_cost=worst_case,
        cvar=cvar,
        cvar_status=cvar_status,
        downside_probability=downside_prob,
        risk_label=_risk_label(downside_ratio),
        vessel_reliability_score=reliability_score,
        reliability_flag=reliability_flag,
    )


def risk_adjusted_objective(expected_cost: float, cvar: float, risk_lambda: float) -> float:
    """
    [Spec-review issue #3] The absolute, dollar-scale objective term used by
    3.5: expected_cost + lambda * (cvar - expected_cost). Both terms are in
    the same USD units as the cost objective itself, unlike v1's per-run-
    normalized risk score. lambda=0 must reduce EXACTLY to expected-cost-only
    ranking (a risk-neutral sanity check, tested explicitly).
    """
    return expected_cost + risk_lambda * (cvar - expected_cost)


def compute_combined_risk(
    combo_label: str,
    selected: list[tuple[str, float]],
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
    alpha: float = config.CVAR_ALPHA,
    min_scenarios_for_cvar: int = config.MIN_SCENARIOS_FOR_CVAR,
    reliability_scores: Optional[dict[str, Optional[float]]] = None,
) -> CandidateRiskMetrics:
    """
    Computes risk metrics for a MULTI-candidate combination (a split-cargo
    solution: two or more (candidate_id, tonnage) legs used together) by
    summing each leg's per-scenario cost before computing the same weighted
    statistics used for a single candidate.

    Used for POST-HOC reporting only on the split-cargo MIP path — the MIP
    itself selects the combination by expected cost alone (a stated
    simplification, see mip_model.py), but the actual realized risk of
    whatever combination it lands on is still worth surfacing to the user,
    not hidden just because the search didn't optimize on it directly.

    reliability_scores: [Backlog item, Section 5.2] optional {candidate_id:
    reliability_score} for the selected legs. Combined as a TONNAGE-WEIGHTED
    average across legs — e.g. an 82,000t leg at 0.9 and a 58,000t leg at 0.5
    yields a blended figure reflecting each vessel's share of the cargo, not
    a naive average of the two scores. None entries are excluded from the
    weighting (an unknown score doesn't drag the average toward 0).
    """
    prob_by_scenario = {s.scenario_id: s.probability for s in scenario_set.scenarios}
    scenario_ids = [s.scenario_id for s in scenario_set.scenarios]

    combined_costs = []
    for scenario_id in scenario_ids:
        total = 0.0
        for candidate_id, tonnage in selected:
            row = cost_matrix.row(candidate_id, scenario_id)
            total += row.total_cost_for_tonnage(tonnage)
        combined_costs.append(total)
    weights = [prob_by_scenario[sid] for sid in scenario_ids]

    expected = _weighted_mean(combined_costs, weights)
    variance = _weighted_variance(combined_costs, weights, expected)
    worst_case = max(combined_costs)
    downside_prob = sum(w for c, w in zip(combined_costs, weights) if c > expected * 1.05) / sum(weights)

    if len(combined_costs) >= min_scenarios_for_cvar:
        cvar = weighted_cvar(combined_costs, weights, alpha)
        cvar_status = "COMPUTED"
    else:
        cvar = worst_case
        cvar_status = "NOT_MEANINGFUL_SAMPLE_SIZE"

    downside_ratio = (cvar - expected) / expected if expected != 0 else 0.0

    combined_reliability = None
    if reliability_scores:
        known = [(rid, t) for rid, t in selected if reliability_scores.get(rid) is not None]
        total_known_tonnage = sum(t for _, t in known)
        if total_known_tonnage > 0:
            combined_reliability = sum(reliability_scores[rid] * t for rid, t in known) / total_known_tonnage

    reliability_flag = None
    if combined_reliability is not None and combined_reliability < config.VESSEL_RELIABILITY_FLAG_THRESHOLD:
        reliability_flag = "LOW_RELIABILITY_RISK"

    return CandidateRiskMetrics(
        candidate_id=combo_label,
        expected_cost=expected,
        variance=variance,
        worst_case_cost=worst_case,
        cvar=cvar,
        cvar_status=cvar_status,
        downside_probability=downside_prob,
        risk_label=_risk_label(downside_ratio),
        vessel_reliability_score=combined_reliability,
        reliability_flag=reliability_flag,
    )


def compute_risk_result(
    risk_run_id: str,
    cargo: CargoRequirement,
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
    candidate_tonnages: dict[str, float],
    risk_lambda: float,
) -> RiskResult:
    """
    Module 3.6 entry point. Computes risk metrics for every candidate present
    in candidate_tonnages (the caller — 3.5 — decides which candidates to
    price and at what tonnage; this module makes no allocation decisions
    itself).
    """
    candidates = [
        compute_candidate_risk(candidate_id, cost_matrix, scenario_set, tonnage)
        for candidate_id, tonnage in candidate_tonnages.items()
    ]
    return RiskResult(
        risk_run_id=risk_run_id,
        cargo_requirement_id=cargo.cargo_requirement_id,
        risk_preference=cargo.risk_preference.value,
        risk_lambda=risk_lambda,
        candidates=candidates,
    )
