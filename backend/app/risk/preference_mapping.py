"""
Module 3.6 support — risk_preference -> lambda mapping.

Isolated in its own module (not inlined in metrics.py) so the mapping table
is the single place to look, and so it's trivially swappable without
touching the metric computation logic itself.
"""
from __future__ import annotations

from app import config
from app.schemas.common import RiskPreference


def get_risk_lambda(risk_preference: RiskPreference) -> float:
    """
    Returns the dollar-scale risk-aversion coefficient for a given user
    preference. lambda=0 is risk-neutral (pure expected-cost minimization);
    lambda=1 weights the objective fully toward the CVaR tail.

    [Spec-review issue #3 fix] This is a FIXED, portable mapping — the same
    risk_preference always yields the same lambda regardless of which cargo
    requirement or candidate set it's applied to. This is what makes the
    ablation/backtesting study's results comparable across runs; a per-run
    normalized risk score (the v1 approach) would not have this property.
    """
    return config.RISK_LAMBDA_BY_PREFERENCE[risk_preference.value]
