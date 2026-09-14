"""
Module 3.1 support — individual, independently-testable feasibility predicates.

Kept separate from vessel_engine.py's orchestration so each rule can be unit
tested in isolation (per the Decision Engine spec, Section 2.5 deliverables).
Every function is a pure predicate: no I/O, no side effects, deterministic.
"""
from __future__ import annotations

from datetime import date

from app.schemas.common import CargoRequirement, Port, RouteDistance, Vessel, VesselAvailability


def capacity_ok(vessel: Vessel, cargo: CargoRequirement) -> bool:
    """Vessel's effective deadweight covers the full cargo requirement."""
    return vessel.dwt_tonnes >= cargo.quantity_tonnes


def draft_ok(vessel: Vessel, origin_port: Port, destination_port: Port) -> bool:
    """Vessel's laden draft must clear the shallower of the two ports."""
    limiting_draft = min(origin_port.max_draft_m, destination_port.max_draft_m)
    return vessel.draft_laden_m <= limiting_draft


def loa_ok(vessel: Vessel, origin_port: Port, destination_port: Port) -> bool:
    limiting_loa = min(origin_port.max_loa_m, destination_port.max_loa_m)
    return vessel.loa_m <= limiting_loa


def beam_ok(vessel: Vessel, origin_port: Port, destination_port: Port) -> bool:
    limiting_beam = min(origin_port.max_beam_m, destination_port.max_beam_m)
    return vessel.beam_m <= limiting_beam


def min_voyage_days(
    vessel: Vessel,
    distance_open_to_origin_nm: float,
    distance_origin_to_destination_nm: float,
) -> float:
    """
    Minimum time (days) for this vessel to reposition to the origin port and
    then complete the laden leg to the destination, at service speed.
    Does not include loading/discharge time (that's a port-side turnaround
    concern, handled in 3.2) — this is purely steaming time, used only to
    test whether the vessel can physically be in place before the deadline.
    """
    total_nm = distance_open_to_origin_nm + distance_origin_to_destination_nm
    return total_nm / vessel.service_speed_knots / 24.0


def avail_ok(
    vessel: Vessel,
    availability: VesselAvailability,
    cargo: CargoRequirement,
    distance_open_to_origin_nm: float,
    distance_origin_to_destination_nm: float,
) -> bool:
    """Vessel must be able to open, reposition, and complete the laden leg
    before the delivery deadline."""
    voyage_days = min_voyage_days(vessel, distance_open_to_origin_nm, distance_origin_to_destination_nm)
    earliest_possible_arrival = availability.open_date.toordinal() + voyage_days
    return earliest_possible_arrival <= cargo.delivery_deadline.toordinal()


def origin_ok(
    availability: VesselAvailability,
    cargo: CargoRequirement,
    distance_open_to_origin_nm: float,
    distance_origin_to_destination_nm: float,
    service_speed_knots: float,
) -> bool:
    """
    Vessel must be able to reach the origin port before the LATEST departure
    that still allows completing the laden leg by the delivery deadline.

    NOTE: this is deliberately NOT "reach origin by cargo.earliest_departure" —
    earliest_departure is the earliest the cargo COULD move, not a hard
    requirement that every candidate vessel arrive that early. A vessel that
    reaches origin later than earliest_departure (but still in time to sail
    and arrive before the deadline) is legitimately usable; 3.3's charter
    epoch selection decides the actual departure timing within this window.
    This check and avail_ok are intentionally testing the same underlying
    voyage-timing fact from two angles (arrival-at-origin vs. arrival-at-
    destination) so a NO_FEASIBLE_VESSEL reason can point specifically at
    "can't reach origin in time" vs. a downstream leg issue.
    """
    reposition_days = distance_open_to_origin_nm / service_speed_knots / 24.0
    arrival_at_origin = availability.open_date.toordinal() + reposition_days
    laden_days = distance_origin_to_destination_nm / service_speed_knots / 24.0
    latest_useful_departure = cargo.delivery_deadline.toordinal() - laden_days
    return arrival_at_origin <= latest_useful_departure


def lookup_distance(distances: list[RouteDistance], from_port_id: str, to_port_id: str) -> float:
    """Symmetric distance lookup; raises if the pair isn't in the reference table."""
    for d in distances:
        if {d.from_port_id, d.to_port_id} == {from_port_id, to_port_id}:
            return d.distance_nm
    raise ValueError(f"No distance reference for {from_port_id} <-> {to_port_id}")
