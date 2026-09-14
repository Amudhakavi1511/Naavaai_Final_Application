"""
Module 3.5 — enumeration path (single-vessel case).

NOT an MILP. Full closed-form enumeration over the (already small, already
feasibility-gated) candidate set from 3.3. Trivially globally optimal,
O(|C|) evaluations, and directly explainable to a judge as "we computed the
objective for every valid option and picked the min" — more credible than
"we called a solver" for a problem this size. Reserved for candidates whose
capacity alone covers the full cargo requirement; see solver_runner.py for
the routing decision between this and the split-cargo MIP.
"""
from __future__ import annotations

from app import config
from app.risk.metrics import compute_candidate_risk, risk_adjusted_objective
from app.schemas.candidates import CandidateOption, CostMatrix
from app.schemas.common import CargoRequirement, ScenarioSet, Vessel


class EnumerationCandidateScore:
    def __init__(self, candidate: CandidateOption, expected_cost: float, cvar: float, cvar_status: str, objective_value: float,
                 reliability_score: float | None = None, reliability_flag: str | None = None):
        self.candidate = candidate
        self.expected_cost = expected_cost
        self.cvar = cvar
        self.cvar_status = cvar_status
        self.objective_value = objective_value
        self.reliability_score = reliability_score
        self.reliability_flag = reliability_flag


def enumerate_single_vessel_candidates(
    full_capacity_candidates: list[CandidateOption],
    cargo: CargoRequirement,
    cost_matrix: CostMatrix,
    scenario_set: ScenarioSet,
    risk_lambda: float,
    vessels: list[Vessel] | None = None,
) -> list[EnumerationCandidateScore]:
    """
    Scores every full-capacity candidate by its risk-adjusted objective,
    sorted ascending (best first). The caller picks scores[0] as the winner
    and scores[1:RANKED_ALTERNATIVES_TOP_N+1] as ranked alternatives.

    vessels: [Backlog item, Section 5.2] optional — when provided, each
    candidate's vessel.reliability_score is looked up and passed through to
    3.6 for informational reporting only (never affects objective_value's
    ranking, per compute_candidate_risk's own docstring).
    """
    vessel_by_id = {v.vessel_id: v for v in vessels} if vessels else {}
    scores = []
    for candidate in full_capacity_candidates:
        reliability_score = None
        if candidate.vessel_id in vessel_by_id:
            reliability_score = vessel_by_id[candidate.vessel_id].reliability_score
        risk = compute_candidate_risk(
            candidate.candidate_id, cost_matrix, scenario_set, tonnage=cargo.quantity_tonnes,
            reliability_score=reliability_score,
        )
        objective = risk_adjusted_objective(risk.expected_cost, risk.cvar, risk_lambda)
        scores.append(
            EnumerationCandidateScore(
                candidate=candidate, expected_cost=risk.expected_cost,
                cvar=risk.cvar, cvar_status=risk.cvar_status, objective_value=objective,
                reliability_score=risk.vessel_reliability_score, reliability_flag=risk.reliability_flag,
            )
        )
    scores.sort(key=lambda s: s.objective_value)
    return scores
