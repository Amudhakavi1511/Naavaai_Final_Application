"""
Prototype configuration constants, centralized so every tunable cap is named
once and documented — per the Decision Engine spec's repeated instruction
that prototype simplifications be stated explicitly, not hidden in code.

None of these are domain laws; all are safe to change without a redesign.
"""

# 3.1 — [Backlog item, competitive-landscape review Section 5.2] a vessel's
# reliability_score below this is flagged (non-blocking — informational,
# never gates feasibility) via VesselCheckResult.reliability_flag.
VESSEL_RELIABILITY_FLAG_THRESHOLD = 0.6

# 3.3 — WAIT_THEN_CHARTER / SHORT_TERM timing epochs are sampled every N days,
# not daily (spec-review pruning rule 1: waiting decisions this granular
# don't change materially day-to-day for a prototype).
WAIT_EPOCH_STEP_DAYS = 2

# 3.3 — MEDIUM_TERM / COA strategies are only generated if the cargo quantity
# plausibly implies a multi-voyage need (pruning rule 2).
MULTI_VOYAGE_THRESHOLD_TONNES = 150_000

# 3.3 — vessels ranked by unit freight cost at epoch=today are capped to the
# top N per class before full epoch enumeration (pruning rule 3).
TOP_N_VESSELS_PER_CLASS = 8

# 3.3 / 3.5 — split-cargo candidates only exist if each vessel's assigned
# share would be >= this floor (spec-review issue #11: prevents commercially
# absurd tiny lots like 79,000t + 1,000t).
MIN_ECONOMIC_LOT_TONNES = 15_000

# 3.5 — split-cargo cap: at most this many vessels combine to cover one
# cargo requirement (prototype simplification, stated not hidden).
MAX_VESSELS_PER_CARGO = 2

# 3.6 — CVaR at alpha=0.8 is only trusted with at least this many scenarios
# (spec-review issue #4: below this, CVaR collapses onto worst-case and is
# reported as such via cvar_status=NOT_MEANINGFUL_SAMPLE_SIZE).
MIN_SCENARIOS_FOR_CVAR = 20
CVAR_ALPHA = 0.8

# 3.5 — risk-aversion coefficient by user-selected risk preference. Absolute,
# dollar-scale objective term: expected_cost + RISK_LAMBDA[pref] * (cvar - expected_cost).
RISK_LAMBDA_BY_PREFERENCE = {
    "LOW": 0.7,
    "BALANCED": 0.35,
    "HIGH": 0.1,
}

# 3.5 — before building the split-cargo MIP, cap the number of epochs
# considered per vessel (by expected cost) so the MIP's berth-overlap
# constraints (O(n^2) binary order variables) stay small and fast for a
# prototype. A genuine MIP is still solved over the surviving candidates —
# this just keeps it tractable, and is a stated cap, not hidden.
MIP_MAX_EPOCHS_PER_VESSEL = 5

# 3.5 — MIP solver wall-clock budget before returning TIME_LIMIT_REACHED
# instead of hanging the demo.
MIP_SOLVER_TIME_LIMIT_SECONDS = 10

# 3.5 — how many ranked alternatives to report alongside the winner.
RANKED_ALTERNATIVES_TOP_N = 5
