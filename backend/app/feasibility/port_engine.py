"""
Module 3.2 — Port Feasibility Engine.

Mirrors 3.1 at the port level, plus operational feasibility (berth/handling
capacity, congestion threshold). Deterministic — answers "is the port usable
at all," not "how much will waiting cost" (that's 3.4's job, using this
module's base_turnaround_days / current_congestion_days composed with a
scenario's congestion shock).
"""
from __future__ import annotations

from app.feasibility.congestion import estimate_turnaround
from app.schemas.common import (
    CargoRequirement,
    CongestionObservation,
    Port,
    PortCheckResult,
    PortFeasibilityResult,
    Vessel,
)

# Config constant — a prototype threshold, not a domain law. Ports observed
# with more than this many days of current queue are flagged infeasible
# rather than silently priced with an enormous demurrage number.
DEFAULT_CONGESTION_THRESHOLD_DAYS = 10.0


def evaluate_port(
    port: Port,
    cargo: CargoRequirement,
    window_days: float,
    required_draft_m: float,
    congestion_observations: list[CongestionObservation],
    congestion_threshold_days: float = DEFAULT_CONGESTION_THRESHOLD_DAYS,
) -> PortCheckResult:
    """Run the full 3.2 rule chain for a single port."""
    base_turnaround, current_congestion = estimate_turnaround(port, congestion_observations)

    handling_days_needed = cargo.quantity_tonnes / port.cargo_handling_rate_tonnes_per_day

    draft_check = port.max_draft_m >= required_draft_m
    berth_check = port.berth_count >= 1  # prototype simplification: a single available
    # berth slot is assumed available within the cargo window; a real berth-scheduling
    # system would check the actual booking calendar here (documented limitation).
    handling_check = handling_days_needed <= window_days
    congestion_check = current_congestion <= congestion_threshold_days

    checks = {
        "draft_ok": draft_check,
        "berth_ok": berth_check,
        "handling_ok": handling_check,
        "congestion_acceptable": congestion_check,
    }
    failed = [name for name, ok in checks.items() if not ok]
    feasible = len(failed) == 0

    reason_text = None
    if failed:
        reasons = []
        if not draft_check:
            reasons.append(f"Max draft {port.max_draft_m:.1f}m is less than required {required_draft_m:.1f}m")
        if not berth_check:
            reasons.append("No berth capacity on file for this port")
        if not handling_check:
            reasons.append(
                f"Required {cargo.quantity_tonnes:,.0f}t needs {handling_days_needed:.1f} days at "
                f"{port.cargo_handling_rate_tonnes_per_day:,.0f}t/day, exceeding the {window_days:.1f}-day window"
            )
        if not congestion_check:
            reasons.append(
                f"Current congestion {current_congestion:.1f} days exceeds threshold {congestion_threshold_days:.1f} days"
            )
        reason_text = "; ".join(reasons)

    return PortCheckResult(
        port_id=port.port_id,
        feasible=feasible,
        draft_ok=draft_check,
        berth_ok=berth_check,
        handling_ok=handling_check,
        congestion_acceptable=congestion_check,
        base_turnaround_days=base_turnaround,
        current_congestion_days=current_congestion,
        failed=failed,
        reason_text=reason_text,
    )


def run_port_feasibility(
    feasibility_run_id: str,
    cargo: CargoRequirement,
    ports_by_id: dict[str, Port],
    candidate_vessels: list[Vessel],
    congestion_observations: list[CongestionObservation],
    congestion_threshold_days: float = DEFAULT_CONGESTION_THRESHOLD_DAYS,
) -> PortFeasibilityResult:
    """
    Module 3.2 entry point. Evaluates origin and destination ports against
    this cargo requirement.

    [Fix — iteration 2, found via a split-cargo integration test] required_draft_m
    is now the minimum laden draft across the FULL candidate fleet, with no
    capacity filter at all. The earlier "only vessels big enough to carry the
    cargo alone" filter (iteration 1's fix for the tautology bug) broke split-
    cargo cases: for a cargo too large for any single vessel except a
    Capesize, that filter forced required_draft_m to the CAPESIZE's draft
    (18.0m) — failing a port that the ACTUAL plan (a Panamax split, 14.3m
    draft) would have used perfectly well. Draft is a per-vessel physical
    fact independent of whether that vessel ends up carrying the whole cargo
    alone or one leg of a split; 3.2 should ask "can the shallowest vessel
    under consideration dock here," not "can a vessel big enough to do this
    solo dock here." This is still independent of 3.1's own filtering
    (iteration 1's actual point), since candidate_vessels here is still the
    full fleet, not vessels 3.1 already approved.
    """
    window_days = (cargo.delivery_deadline - cargo.earliest_departure).days
    required_draft_m = min((v.draft_laden_m for v in candidate_vessels), default=0.0)

    origin = ports_by_id[cargo.origin_port_id]
    destination = ports_by_id[cargo.destination_port_id]

    results = [
        evaluate_port(origin, cargo, window_days, required_draft_m, congestion_observations, congestion_threshold_days),
        evaluate_port(destination, cargo, window_days, required_draft_m, congestion_observations, congestion_threshold_days),
    ]

    return PortFeasibilityResult(
        feasibility_run_id=feasibility_run_id,
        cargo_requirement_id=cargo.cargo_requirement_id,
        ports=results,
    )
