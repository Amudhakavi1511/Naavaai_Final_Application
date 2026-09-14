"""
Module 3.4 support — despatch/demurrage calculation, isolated from the main
cost function per the Decision Engine spec Section 5.5 deliverables, since
this is the piece most likely to need tuning against a real charter party.

demurrage: charterer pays the owner for turnaround exceeding the laytime
    allowance.
despatch: owner pays the charterer back (a credit, i.e. negative cost) for
    beating the laytime allowance — the demurrage rate's upside mirror,
    added per spec-review issue #10 (v1 silently omitted this).
"""
from __future__ import annotations

from app.cost.params_loader import CostParameters


def compute_demurrage_and_despatch(
    turnaround_days: float, params: CostParameters
) -> tuple[float, float]:
    """Returns (demurrage_cost, despatch_credit). Exactly one of the two is
    non-zero for any given turnaround (they're mutually exclusive by
    definition — you can't simultaneously beat and miss the same laytime
    allowance), except the degenerate case of turnaround exactly equal to
    the allowance, where both are zero."""
    laytime_delta = turnaround_days - params.laytime_allowance_days
    demurrage = max(0.0, laytime_delta) * params.demurrage_rate_per_day
    despatch = max(0.0, -laytime_delta) * params.despatch_rate_per_day
    return demurrage, despatch
