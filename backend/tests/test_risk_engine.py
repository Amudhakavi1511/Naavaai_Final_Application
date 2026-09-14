from __future__ import annotations

import pytest

from app import config
from app.risk.metrics import compute_candidate_risk, risk_adjusted_objective, weighted_cvar
from app.risk.preference_mapping import get_risk_lambda
from app.schemas.candidates import CostBreakdown, CostMatrix, CostRow
from app.schemas.common import CargoRequirement, RiskPreference, Scenario, ScenarioSet, DailyRate
from datetime import date


def _make_scenario_set(probs: list[float]) -> ScenarioSet:
    n = len(probs)
    scenarios = []
    for i, p in enumerate(probs):
        d = date(2026, 9, 1)
        scenarios.append(
            Scenario(
                scenario_id=f"S{i}", probability=p,
                voyage_freight_path_usd_per_tonne=[DailyRate(date=d, rate=15.0)],
            )
        )
    return ScenarioSet(scenario_run_id="SR", forecast_run_id="FR", scenario_count=n, scenarios=scenarios)


def _make_cost_matrix(candidate_id: str, costs: list[float]) -> CostMatrix:
    rows = []
    for i, c in enumerate(costs):
        # encode the desired TOTAL cost directly via fixed_cost, freight_cost_per_tonne=0,
        # so total_cost_for_tonnage(any tonnage) == c regardless of tonnage passed.
        rows.append(
            CostRow(
                candidate_id=candidate_id, scenario_id=f"S{i}",
                freight_cost_per_tonne=0.0, fixed_cost=c,
                breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0),
            )
        )
    return CostMatrix(cost_run_id="CR", cargo_requirement_id="C1", cost_param_version="v1", rows=rows)


# ---------------------------------------------------------------------------
# weighted_cvar — hand-computed reference values
# ---------------------------------------------------------------------------

def test_cvar_uniform_weights_hand_computed():
    """10 equally-likely costs [100..1000 step 100]. alpha=0.8 -> worst 20%
    tail = worst 2 scenarios = [1000, 900] -> CVaR = 950."""
    costs = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    weights = [0.1] * 10
    result = weighted_cvar(costs, weights, alpha=0.8)
    assert result == pytest.approx(950.0)


def test_cvar_handles_tail_boundary_scenario_partial_weight():
    """3 scenarios with weights [0.5, 0.3, 0.2], costs [100, 200, 300].
    alpha=0.8 -> tail mass needed = 0.2 -> exactly the worst scenario (300,
    weight 0.2) is fully consumed -> CVaR = 300."""
    costs = [100, 200, 300]
    weights = [0.5, 0.3, 0.2]
    result = weighted_cvar(costs, weights, alpha=0.8)
    assert result == pytest.approx(300.0)


def test_cvar_partial_boundary_scenario_averaged_correctly():
    """2 scenarios, weights [0.7, 0.3], costs [100, 200]. alpha=0.8 -> tail
    mass needed=0.2, but worst scenario only has weight 0.3 > 0.2, so only
    0.2/0.3 of it counts -> CVaR = 200 (still just the worst scenario's cost,
    since we only need PART of its mass, at its own cost value)."""
    costs = [100, 200]
    weights = [0.7, 0.3]
    result = weighted_cvar(costs, weights, alpha=0.8)
    assert result == pytest.approx(200.0)


def test_cvar_single_scenario_degenerate_case():
    result = weighted_cvar([500.0], [1.0], alpha=0.8)
    assert result == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# compute_candidate_risk — sample-size gating (spec-review issue #4)
# ---------------------------------------------------------------------------

def test_cvar_computed_when_scenario_count_at_or_above_threshold():
    assert config.MIN_SCENARIOS_FOR_CVAR == 20
    probs = [1.0 / 20] * 20
    scenario_set = _make_scenario_set(probs)
    costs = [1000 + i * 10 for i in range(20)]  # spread of costs
    cost_matrix = _make_cost_matrix("C1", costs)
    metrics = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000)
    assert metrics.cvar_status == "COMPUTED"
    assert metrics.cvar != metrics.worst_case_cost  # a real tail average, not just the max


def test_cvar_falls_back_to_worst_case_below_threshold():
    """Below MIN_SCENARIOS_FOR_CVAR, cvar_status must be NOT_MEANINGFUL_SAMPLE_SIZE
    and cvar must equal worst_case_cost exactly — never a number that LOOKS
    precise but isn't (spec-review issue #4)."""
    probs = [0.25, 0.25, 0.25, 0.25]  # only 4 scenarios
    scenario_set = _make_scenario_set(probs)
    costs = [1000, 1100, 1200, 1300]
    cost_matrix = _make_cost_matrix("C1", costs)
    metrics = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000)
    assert metrics.cvar_status == "NOT_MEANINGFUL_SAMPLE_SIZE"
    assert metrics.cvar == metrics.worst_case_cost == 1300.0


def test_single_scenario_degenerate_variance_is_zero():
    scenario_set = _make_scenario_set([1.0])
    cost_matrix = _make_cost_matrix("C1", [5000.0])
    metrics = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000)
    assert metrics.variance == 0.0
    assert metrics.expected_cost == 5000.0
    assert metrics.worst_case_cost == 5000.0


def test_expected_cost_is_probability_weighted_mean():
    scenario_set = _make_scenario_set([0.5, 0.3, 0.2])
    cost_matrix = _make_cost_matrix("C1", [1000, 2000, 3000])
    metrics = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000)
    expected = 0.5 * 1000 + 0.3 * 2000 + 0.2 * 3000
    assert metrics.expected_cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# risk_adjusted_objective — absolute USD term, portable lambda (issue #3)
# ---------------------------------------------------------------------------

def test_lambda_zero_reduces_exactly_to_expected_cost():
    """Risk-neutral sanity check: lambda=0 must give EXACTLY expected_cost,
    regardless of how extreme the CVaR is."""
    result = risk_adjusted_objective(expected_cost=1_000_000, cvar=5_000_000, risk_lambda=0.0)
    assert result == 1_000_000


def test_lambda_one_weights_fully_toward_cvar():
    result = risk_adjusted_objective(expected_cost=1_000_000, cvar=1_500_000, risk_lambda=1.0)
    assert result == 1_500_000


def test_lambda_intermediate_is_linear_interpolation():
    result = risk_adjusted_objective(expected_cost=1_000_000, cvar=1_500_000, risk_lambda=0.35)
    assert result == pytest.approx(1_000_000 + 0.35 * 500_000)


def test_risk_lambda_is_portable_same_preference_same_lambda_regardless_of_candidate_set():
    """[Spec-review issue #3] The whole point of the fix: risk_preference ->
    lambda must NOT depend on which candidates/costs are in play."""
    lam_a = get_risk_lambda(RiskPreference.BALANCED)
    lam_b = get_risk_lambda(RiskPreference.BALANCED)
    assert lam_a == lam_b == config.RISK_LAMBDA_BY_PREFERENCE["BALANCED"]


def test_risk_preference_boundary_values_ordered_correctly():
    """LOW risk tolerance -> most risk-averse -> HIGHEST lambda.
    HIGH risk tolerance -> least risk-averse -> LOWEST lambda."""
    lam_low = get_risk_lambda(RiskPreference.LOW)
    lam_balanced = get_risk_lambda(RiskPreference.BALANCED)
    lam_high = get_risk_lambda(RiskPreference.HIGH)
    assert lam_low > lam_balanced > lam_high
    assert 0.0 <= lam_high < lam_balanced < lam_low <= 1.0


# ---------------------------------------------------------------------------
# Vessel reliability score — informational, never mixed into cost/CVaR (backlog item, Section 5.2)
# ---------------------------------------------------------------------------

def test_reliability_score_reported_but_not_mixed_into_cost_metrics():
    scenario_set = _make_scenario_set([0.5, 0.5])
    cost_matrix = _make_cost_matrix("C1", [1000, 1000])  # identical costs regardless of reliability
    with_high_reliability = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000, reliability_score=0.95)
    with_low_reliability = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000, reliability_score=0.2)
    # cost-based metrics must be IDENTICAL regardless of reliability score —
    # it's reported alongside, never folded into expected_cost/cvar/variance.
    assert with_high_reliability.expected_cost == with_low_reliability.expected_cost
    assert with_high_reliability.cvar == with_low_reliability.cvar
    assert with_high_reliability.vessel_reliability_score == 0.95
    assert with_low_reliability.vessel_reliability_score == 0.2


def test_low_reliability_score_flagged_in_risk_metrics():
    scenario_set = _make_scenario_set([1.0])
    cost_matrix = _make_cost_matrix("C1", [1000])
    low = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000, reliability_score=0.3)
    high = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000, reliability_score=0.9)
    assert low.reliability_flag == "LOW_RELIABILITY_RISK"
    assert high.reliability_flag is None


def test_none_reliability_score_produces_no_flag():
    scenario_set = _make_scenario_set([1.0])
    cost_matrix = _make_cost_matrix("C1", [1000])
    metrics = compute_candidate_risk("C1", cost_matrix, scenario_set, tonnage=80000, reliability_score=None)
    assert metrics.vessel_reliability_score is None
    assert metrics.reliability_flag is None


def test_combined_risk_reliability_is_tonnage_weighted_average():
    """[Backlog item — tonnage-weighted combination] An 82,000t leg at 0.9
    and a 58,000t leg at 0.5 must blend toward the LARGER leg's score, not a
    naive 50/50 average of the two numbers."""
    from app.risk.metrics import compute_combined_risk
    scenario_set = _make_scenario_set([0.5, 0.5])
    cost_matrix = CostMatrix(
        cost_run_id="CR", cargo_requirement_id="C1", cost_param_version="v1",
        rows=[
            CostRow(candidate_id="CA", scenario_id="S0", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
            CostRow(candidate_id="CA", scenario_id="S1", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
            CostRow(candidate_id="CB", scenario_id="S0", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
            CostRow(candidate_id="CB", scenario_id="S1", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
        ],
    )
    selected = [("CA", 82000.0), ("CB", 58000.0)]
    reliability_scores = {"CA": 0.9, "CB": 0.5}
    combined = compute_combined_risk("COMBO", selected, cost_matrix, scenario_set, reliability_scores=reliability_scores)
    expected = (0.9 * 82000 + 0.5 * 58000) / (82000 + 58000)
    assert combined.vessel_reliability_score == pytest.approx(expected)
    naive_average = (0.9 + 0.5) / 2
    assert combined.vessel_reliability_score != pytest.approx(naive_average)


def test_combined_risk_excludes_unknown_scores_from_weighting():
    from app.risk.metrics import compute_combined_risk
    scenario_set = _make_scenario_set([1.0])
    cost_matrix = CostMatrix(
        cost_run_id="CR", cargo_requirement_id="C1", cost_param_version="v1",
        rows=[
            CostRow(candidate_id="CA", scenario_id="S0", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
            CostRow(candidate_id="CB", scenario_id="S0", freight_cost_per_tonne=0, fixed_cost=1000,
                    breakdown=CostBreakdown(port_cost=0, waiting_cost=0, idle_cost=0, deadhead_cost=0, demurrage=0, despatch_credit=0)),
        ],
    )
    selected = [("CA", 82000.0), ("CB", 58000.0)]
    reliability_scores = {"CA": 0.9, "CB": None}
    combined = compute_combined_risk("COMBO", selected, cost_matrix, scenario_set, reliability_scores=reliability_scores)
    assert combined.vessel_reliability_score == pytest.approx(0.9)  # only CA's score counted
