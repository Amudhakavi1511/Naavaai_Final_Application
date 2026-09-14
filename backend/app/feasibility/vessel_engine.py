"""
Module 3.1 — Vessel Feasibility Engine.

Deterministic rule chain (no ML, no optimization) that prunes the vessel
universe to the subset physically and operationally capable of performing
a specific voyage. Runs BEFORE any cost/optimization logic — infeasible
vessels must never reach the optimizer, per the Decision Engine spec
Section 2.7 ("why this module is not eliminable").

Pure function: takes data in, returns a result, no I/O.
"""
from __future__ import annotations

from app import config
from app.feasibility import rules
from app.schemas.common import (
    CargoRequirement,
    Port,
    RouteDistance,
    Vessel,
    VesselAvailability,
    VesselCheckResult,
    VesselFeasibilityResult,
)

_REASON_TEMPLATES = {
    "capacity_ok": "DWT {vessel.dwt_tonnes:,.0f}t is less than required cargo {cargo.quantity_tonnes:,.0f}t",
    "draft_ok": "Draft {vessel.draft_laden_m:.1f}m exceeds the limiting port draft of {limit:.1f}m",
    "loa_ok": "LOA {vessel.loa_m:.1f}m exceeds the limiting port LOA of {limit:.1f}m",
    "beam_ok": "Beam {vessel.beam_m:.1f}m exceeds the limiting port beam of {limit:.1f}m",
    "avail_ok": "Vessel cannot reposition and complete the laden leg before the delivery deadline",
    "origin_ok": "Vessel cannot reach the origin port in time to still meet the delivery deadline",
}


def _build_reason_text(failed: list[str], vessel: Vessel, cargo: CargoRequirement, origin: Port, destination: Port) -> str:
    if not failed:
        return ""
    parts = []
    for rule_name in failed:
        template = _REASON_TEMPLATES[rule_name]
        if rule_name == "draft_ok":
            parts.append(template.format(vessel=vessel, limit=min(origin.max_draft_m, destination.max_draft_m)))
        elif rule_name == "loa_ok":
            parts.append(template.format(vessel=vessel, limit=min(origin.max_loa_m, destination.max_loa_m)))
        elif rule_name == "beam_ok":
            parts.append(template.format(vessel=vessel, limit=min(origin.max_beam_m, destination.max_beam_m)))
        else:
            parts.append(template.format(vessel=vessel, cargo=cargo))
    return "; ".join(parts)


def evaluate_vessel(
    vessel: Vessel,
    availability: VesselAvailability,
    cargo: CargoRequirement,
    origin_port: Port,
    destination_port: Port,
    distances: list[RouteDistance],
) -> VesselCheckResult:
    """Run the full 3.1 rule chain for a single vessel."""
    dist_open_to_origin = rules.lookup_distance(distances, availability.open_port_id, origin_port.port_id)
    dist_origin_to_dest = rules.lookup_distance(distances, origin_port.port_id, destination_port.port_id)

    checks = {
        "capacity_ok": rules.capacity_ok(vessel, cargo),
        "draft_ok": rules.draft_ok(vessel, origin_port, destination_port),
        "loa_ok": rules.loa_ok(vessel, origin_port, destination_port),
        "beam_ok": rules.beam_ok(vessel, origin_port, destination_port),
        "avail_ok": rules.avail_ok(vessel, availability, cargo, dist_open_to_origin, dist_origin_to_dest),
        "origin_ok": rules.origin_ok(availability, cargo, dist_open_to_origin, dist_origin_to_dest, vessel.service_speed_knots),
    }
    failed = [name for name, ok in checks.items() if not ok]
    feasible = len(failed) == 0

    # split_candidate: fails ONLY on capacity, otherwise fine — 3.3 may still
    # use this vessel as one leg of a multi-vessel split-cargo strategy.
    split_candidate = (not checks["capacity_ok"]) and all(
        v for k, v in checks.items() if k != "capacity_ok"
    )

    # [Backlog item — competitive-landscape review Section 5.2] non-blocking
    # reliability flag, passed through purely for informational/explanation
    # purposes. Deliberately NOT folded into `checks`/`failed`/`feasible` —
    # a low-reliability vessel is still a physically feasible one; mixing a
    # commercial risk signal into a hard physical-constraint gate would
    # violate 3.1's own design principle (deterministic physical constraints
    # only, spec Section 11).
    reliability_flag = None
    if vessel.reliability_score is not None and vessel.reliability_score < config.VESSEL_RELIABILITY_FLAG_THRESHOLD:
        reliability_flag = "LOW_RELIABILITY_RISK"

    return VesselCheckResult(
        vessel_id=vessel.vessel_id,
        vessel_class=vessel.vessel_class,
        feasible=feasible,
        capacity_ok=checks["capacity_ok"],
        draft_ok=checks["draft_ok"],
        loa_ok=checks["loa_ok"],
        beam_ok=checks["beam_ok"],
        avail_ok=checks["avail_ok"],
        origin_ok=checks["origin_ok"],
        split_candidate=split_candidate,
        failed=failed,
        reason_text=_build_reason_text(failed, vessel, cargo, origin_port, destination_port) or None,
        reliability_score=vessel.reliability_score,
        reliability_flag=reliability_flag,
    )


def run_vessel_feasibility(
    feasibility_run_id: str,
    cargo: CargoRequirement,
    vessels: list[Vessel],
    availabilities: list[VesselAvailability],
    ports_by_id: dict[str, Port],
    distances: list[RouteDistance],
) -> VesselFeasibilityResult:
    """
    Module 3.1 entry point. Evaluates every vessel in the fleet against
    this cargo requirement and returns the full VesselFeasibilityResult
    (feasible AND infeasible vessels, each with reasons) — the caller
    (orchestration layer / 3.3) decides what to do with a NO_FEASIBLE_VESSEL
    status; this module never raises on that condition, it reports it.
    """
    origin_port = ports_by_id[cargo.origin_port_id]
    destination_port = ports_by_id[cargo.destination_port_id]
    availability_by_vessel = {a.vessel_id: a for a in availabilities}

    results: list[VesselCheckResult] = []
    for vessel in vessels:
        availability = availability_by_vessel.get(vessel.vessel_id)
        if availability is None:
            # No availability record at all — treat as not open in time.
            results.append(
                VesselCheckResult(
                    vessel_id=vessel.vessel_id,
                    vessel_class=vessel.vessel_class,
                    feasible=False,
                    capacity_ok=rules.capacity_ok(vessel, cargo),
                    draft_ok=rules.draft_ok(vessel, origin_port, destination_port),
                    loa_ok=rules.loa_ok(vessel, origin_port, destination_port),
                    beam_ok=rules.beam_ok(vessel, origin_port, destination_port),
                    avail_ok=False,
                    origin_ok=False,
                    failed=["avail_ok", "origin_ok"],
                    reason_text="No availability record for this vessel",
                )
            )
            continue
        results.append(
            evaluate_vessel(vessel, availability, cargo, origin_port, destination_port, distances)
        )

    return VesselFeasibilityResult(
        feasibility_run_id=feasibility_run_id,
        cargo_requirement_id=cargo.cargo_requirement_id,
        vessels=results,
    )
