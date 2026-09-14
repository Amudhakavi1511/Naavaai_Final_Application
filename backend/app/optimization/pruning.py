"""
Module 3.3 support — pruning rules, each a named, independently-toggleable
filter (per Decision Engine spec Section 4.4 deliverables: needed so the
ablation study can test "optimization without pruning" vs "with pruning").

Each function is a pure filter: takes a candidate vessel pool, returns a
(possibly smaller) pool, with the discarded set available for logging.
"""
from __future__ import annotations

from datetime import date, timedelta

from app import config
from app.feasibility import rules
from app.schemas.candidates import CharterStrategy
from app.schemas.common import CargoRequirement, RouteDistance, ScenarioSet, Vessel


def rank_vessels_by_cost_today(
    vessels: list[Vessel],
    scenario_set: ScenarioSet,
    cargo: CargoRequirement,
) -> list[tuple[Vessel, float]]:
    """
    Ranks vessels by their unit freight cost using the S2_BASE headline
    scenario's rate on the first day of the horizon ("today"). Used only for
    ranking/capping candidate vessels BEFORE full epoch enumeration — the
    actual cost used in optimization comes from 3.4, computed per (candidate,
    scenario), not from this proxy.
    """
    base_scenario = next(
        (s for s in scenario_set.scenarios if s.headline_label == "S2_BASE"),
        scenario_set.scenarios[0],  # fallback: first scenario if no headline is tagged
    )
    today_rate = base_scenario.voyage_freight_path_usd_per_tonne[0].rate
    # Same voyage rate proxy for all vessels at this stage (a real per-class
    # rate differential would come from route_id-specific forecasts in a
    # fuller Intelligence Layer) — ranking here is really just a placeholder
    # for "cheapest-to-run first," documented as a prototype simplification.
    return sorted(((v, today_rate) for v in vessels), key=lambda t: t[1])


def filter_top_n_per_class(vessels: list[Vessel], top_n: int = config.TOP_N_VESSELS_PER_CLASS) -> list[Vessel]:
    """Pruning rule 3: cap candidate vessels to the top N per class."""
    by_class: dict[str, list[Vessel]] = {}
    for v in vessels:
        by_class.setdefault(v.vessel_class, []).append(v)
    kept = []
    for vessel_class, group in by_class.items():
        kept.extend(group[:top_n])
    return kept


def filter_min_economic_lot(vessels: list[Vessel], cargo: CargoRequirement, min_lot: float = config.MIN_ECONOMIC_LOT_TONNES) -> list[Vessel]:
    """
    Pruning rule 5 (spec-review issue #11): a split-eligible vessel (capacity
    below cargo_qty) is only worth considering if its OWN capacity is still
    >= the minimum economic lot size — a vessel too small to ever carry a
    commercially sensible share is excluded at generation time, not left for
    3.5's MIP to (possibly) discourage via cost alone.

    Vessels with enough capacity to carry the FULL cargo alone are always
    kept regardless of this filter (they're never a "tiny lot" concern).
    """
    return [v for v in vessels if v.dwt_tonnes >= cargo.quantity_tonnes or v.dwt_tonnes >= min_lot]


def strategy_types_for_cargo(cargo: CargoRequirement) -> list[CharterStrategy]:
    """Pruning rule 2: MEDIUM_TERM/COA only if quantity implies a plausible
    multi-voyage need."""
    base = [CharterStrategy.SPOT_NOW, CharterStrategy.WAIT_THEN_CHARTER, CharterStrategy.SHORT_TERM]
    if cargo.quantity_tonnes >= config.MULTI_VOYAGE_THRESHOLD_TONNES:
        base += [CharterStrategy.MEDIUM_TERM, CharterStrategy.COA]
    return base


def valid_epochs_for_vessel(
    vessel: Vessel,
    availability,
    cargo: CargoRequirement,
    distances: list[RouteDistance],
    step_days: int = config.WAIT_EPOCH_STEP_DAYS,
) -> tuple[date, date, list[date]]:
    """
    Returns (earliest_possible_departure, latest_useful_departure, stepped_epochs).

    earliest_possible_departure: max(cargo.earliest_departure, vessel's earliest
        possible arrival at the origin port).
    latest_useful_departure: cargo.delivery_deadline minus the vessel's laden
        voyage duration — matches the timing arithmetic already validated by
        3.1's avail_ok/origin_ok, so any vessel reaching 3.3 is guaranteed to
        have at least one valid epoch here (barring a data inconsistency,
        guarded below).
    stepped_epochs: dates strictly AFTER earliest_possible_departure, stepped
        by step_days, up to and including latest_useful_departure — used for
        WAIT_THEN_CHARTER / SHORT_TERM. SPOT_NOW uses earliest_possible_departure
        directly and does not consume this list.
    """
    dist_open_to_origin = rules.lookup_distance(distances, availability.open_port_id, cargo.origin_port_id)
    dist_origin_to_dest = rules.lookup_distance(distances, cargo.origin_port_id, cargo.destination_port_id)

    reposition_days = dist_open_to_origin / vessel.service_speed_knots / 24.0
    earliest_arrival_at_origin = availability.open_date + timedelta(days=reposition_days)
    earliest_possible_departure = max(cargo.earliest_departure, earliest_arrival_at_origin)

    laden_days = dist_origin_to_dest / vessel.service_speed_knots / 24.0
    latest_useful_departure = cargo.delivery_deadline - timedelta(days=laden_days)

    if earliest_possible_departure > latest_useful_departure:
        # Data inconsistency guard: 3.1 should have already excluded this
        # vessel via avail_ok/origin_ok. Return an empty window rather than
        # raising, so 3.3 degrades gracefully (fewer candidates) instead of
        # crashing the whole run over one vessel's edge case.
        return earliest_possible_departure, latest_useful_departure, []

    epochs = []
    cursor = earliest_possible_departure + timedelta(days=step_days)
    while cursor <= latest_useful_departure:
        epochs.append(cursor)
        cursor += timedelta(days=step_days)
    # Always include the latest useful departure itself, even if the step
    # doesn't land exactly on it — it's a meaningfully distinct, tightest
    # option that shouldn't be missed by rounding.
    if not epochs or epochs[-1] != latest_useful_departure:
        if latest_useful_departure > earliest_possible_departure:
            epochs.append(latest_useful_departure)

    return earliest_possible_departure, latest_useful_departure, epochs
