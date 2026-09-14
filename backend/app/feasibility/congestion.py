"""
Module 3.2 support — turnaround/congestion estimation.

Deliberately isolated from port_engine.py's hard-constraint checks (per the
Decision Engine spec, Section 3.5 deliverables) so this estimator can later
be swapped for a learned model without touching the deterministic feasibility
rules. Returns base handling time and current observed congestion SEPARATELY
(this is the fix for issue #9 in the v2 spec revision — a scenario's future
congestion shock must be composed with these downstream in 3.4, not baked in
here, or the shock ends up incorrectly scaling the vessel's inherent handling
time too).
"""
from __future__ import annotations

from app.schemas.common import CongestionObservation, Port


def estimate_turnaround(
    port: Port, congestion_observations: list[CongestionObservation]
) -> tuple[float, float]:
    """
    Returns (base_turnaround_days, current_congestion_days) for a port.

    base_turnaround_days: the port's inherent handling/berthing time,
        independent of today's queue — sourced from Port.base_turnaround_days.
    current_congestion_days: additional days from the most recent observed
        congestion at this port — 0.0 if no observation is on file (not an
        error; simply means "no extra queue currently observed").
    """
    base = port.base_turnaround_days
    matching = [o for o in congestion_observations if o.port_id == port.port_id]
    if not matching:
        return base, 0.0
    latest = max(matching, key=lambda o: o.observation_timestamp)
    return base, latest.current_congestion_days
