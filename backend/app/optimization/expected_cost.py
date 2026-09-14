"""
Module 3.5 support — expected-cost coefficient extraction.

The split-cargo MIP's objective must be linear in y[c]/q[c], so it uses
scenario-weighted EXPECTED cost only (not the full risk-adjusted objective —
see mip_model.py's module docstring for why). This is the single place that
computes those two linear coefficients per candidate.
"""
from __future__ import annotations

from app.schemas.candidates import CostMatrix
from app.schemas.common import ScenarioSet


def expected_cost_components(candidate_id: str, cost_matrix: CostMatrix, scenario_set: ScenarioSet) -> tuple[float, float]:
    """Returns (expected_freight_per_tonne, expected_fixed_cost) for one candidate,
    scenario-probability-weighted. These are exactly the two MIP objective
    coefficients for q[c] and y[c] respectively."""
    rows = cost_matrix.rows_for(candidate_id)
    prob_by_scenario = {s.scenario_id: s.probability for s in scenario_set.scenarios}
    exp_freight = sum(row.freight_cost_per_tonne * prob_by_scenario[row.scenario_id] for row in rows)
    exp_fixed = sum(row.fixed_cost * prob_by_scenario[row.scenario_id] for row in rows)
    return exp_freight, exp_fixed
