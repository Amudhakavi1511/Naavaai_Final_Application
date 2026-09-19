"""
Reference data loader — STAND-IN for the database layer (PostgreSQL schema
from Phase-0 Section 7), which hasn't been built yet.

Vessel/port/distance/congestion master data belongs in a database in the
real architecture (see Level-1 DFD: "VesselMaster"/"PortMaster" feed 3.1/3.2
directly, not the per-request API payload). Until that DB layer exists, this
module assembles the same demo fixtures the test suite uses, functioning as a
temporary "database" for the API to query. This is a STATED simplification,
not a hidden one — swapping this module for a real repository backed by
PostgreSQL is the only change needed when the DB layer is built; nothing
downstream (3.1-3.6, the API routes) needs to change.

What gets assembled, in layers:

  1. tests/fixtures/*.json — the original nine-vessel fleet, ten-port network
     and hand-curated distance table. Untouched. The test suite asserts
     against specific vessels here, several of which are deliberately built to
     fail a named feasibility check, so this layer is treated as frozen.

  2. config/port_network.json — the wider loading-port network for the
     countries India actually imports dry bulk from, plus coordinates
     backfilled onto the layer-1 ports so they can participate in routing.

  3. config/fleet_extension.json — additional vessels with open positions
     spread across the basins those loading ports sit in. Without these,
     almost every non-Australian lane would fail on repositioning time, which
     would be an artefact of a thin fixture fleet rather than a real finding.

  4. app/api/route_distances.py — derives a sailing distance for every port
     pair layer 1 doesn't already cover, via a waypoint routing graph.
     Curated distances always win; derived ones are tagged DERIVED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.api.route_distances import build_distance_table
from app.cost.params_loader import CostParameters, load_cost_parameters
from app.schemas.common import (
    CongestionObservation,
    Port,
    RouteDistance,
    ScenarioSet,
    Vessel,
    VesselAvailability,
)

BACKEND_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = BACKEND_ROOT / "tests" / "fixtures"
CONFIG_DIR = BACKEND_ROOT / "config"


class OriginPort:
    """A loading port offered in the procurement form, with the country it is
    grouped under. Discharge ports and ports that only ever appear as vessel
    open positions are excluded."""

    def __init__(self, port_id: str, name: str, country: str, commodities: Optional[str]):
        self.port_id = port_id
        self.name = name
        self.country = country
        self.commodities = commodities


class ReferenceData:
    def __init__(
        self,
        vessels: list[Vessel],
        availabilities: list[VesselAvailability],
        ports_by_id: dict[str, Port],
        congestion_observations: list[CongestionObservation],
        distances: list[RouteDistance],
        cost_params: CostParameters,
        discharge_ports: Optional[list[dict]] = None,
        origin_metadata: Optional[dict[str, str]] = None,
        commodities: Optional[list[dict]] = None,
        default_scenario_set: Optional[ScenarioSet] = None,
    ):
        self.vessels = vessels
        self.availabilities = availabilities
        self.ports_by_id = ports_by_id
        self.congestion_observations = congestion_observations
        self.distances = distances
        self.cost_params = cost_params
        self._discharge_ports = discharge_ports or []
        self.origin_metadata = origin_metadata or {}
        self.commodities = commodities or []
        self.default_scenario_set = default_scenario_set

    # -- derived views the reference endpoints serve ------------------------

    def origin_ports(self) -> list[OriginPort]:
        out = [
            OriginPort(p.port_id, p.name, p.origin_country, p.commodities)
            for p in self.ports_by_id.values()
            if p.origin_country
        ]
        out.sort(key=lambda o: (o.country, o.name))
        return out

    def discharge_ports(self) -> list[tuple[Port, str]]:
        """(port, state) pairs, in the order the network file lists them."""
        out = []
        for entry in self._discharge_ports:
            port = self.ports_by_id.get(entry["port_id"])
            if port:
                out.append((port, entry.get("state", "")))
        return out


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _strip_notes(record: dict) -> dict:
    return {k: v for k, v in record.items() if not k.startswith("_")}


def load_demo_reference_data() -> ReferenceData:
    """Assembles the demo dataset described in the spec's Section M —
    deterministic and fully offline-capable."""

    # --- layer 1: frozen fixtures -----------------------------------------
    vdata = _load_json(FIXTURES_DIR / "mock_vessels.json")
    vessels = [Vessel(**_strip_notes(v)) for v in vdata["vessels"]]
    availabilities = [VesselAvailability(**_strip_notes(a)) for a in vdata["vessel_availability"]]

    pdata = _load_json(FIXTURES_DIR / "mock_ports.json")
    port_records = {p["port_id"]: _strip_notes(p) for p in pdata["ports"]}
    congestion_observations = [CongestionObservation(**_strip_notes(c)) for c in pdata["congestion_observations"]]

    ddata = _load_json(FIXTURES_DIR / "mock_distances.json")
    curated_distances = [RouteDistance(**_strip_notes(d)) for d in ddata["distances"]]

    # --- layer 2: wider loading-port network -------------------------------
    network = _load_json(CONFIG_DIR / "port_network.json")

    for port_id, coords in network["coordinates"].items():
        if port_id in port_records:
            port_records[port_id]["latitude"] = coords[0]
            port_records[port_id]["longitude"] = coords[1]

    for port_id, overlay in network.get("origin_overlay", {}).items():
        if port_id in port_records:
            port_records[port_id].update(overlay)

    for record in network["ports"]:
        record = _strip_notes(record)
        # Fixtures win on conflict: never silently redefine a port the tests
        # are asserting against.
        port_records.setdefault(record["port_id"], record)

    seen_congestion = {c.port_id for c in congestion_observations}
    for entry in network["congestion_observations"]:
        record = _strip_notes(entry)
        if record["port_id"] not in seen_congestion:
            congestion_observations.append(CongestionObservation(**record))

    ports_by_id = {pid: Port(**rec) for pid, rec in port_records.items()}

    # --- layer 3: fleet extension ------------------------------------------
    fleet = _load_json(CONFIG_DIR / "fleet_extension.json")
    existing_vessel_ids = {v.vessel_id for v in vessels}
    for record in fleet["vessels"]:
        record = _strip_notes(record)
        if record["vessel_id"] not in existing_vessel_ids:
            vessels.append(Vessel(**record))

    existing_avail_ids = {a.vessel_id for a in availabilities}
    for record in fleet["vessel_availability"]:
        record = _strip_notes(record)
        if record["vessel_id"] not in existing_avail_ids:
            availabilities.append(VesselAvailability(**record))

    # --- layer 4: derived distances ----------------------------------------
    distances = build_distance_table(ports_by_id.values(), curated_distances)

    return ReferenceData(
        vessels=vessels,
        availabilities=availabilities,
        ports_by_id=ports_by_id,
        congestion_observations=congestion_observations,
        distances=distances,
        cost_params=load_cost_parameters(),
        discharge_ports=network.get("discharge_ports", []),
        origin_metadata=network.get("origin_metadata", {}),
        commodities=network.get("commodities", []),
        default_scenario_set=load_demo_scenario_set(),
    )


def load_demo_scenario_set() -> ScenarioSet:
    """The bundled 40-scenario demo bank.

    This used to be shipped inside the frontend bundle and posted back on
    every request — about 800 KB of JSON travelling in the wrong direction,
    for data the client neither produced nor could validate. It lives here
    now, and `scenario_set` on the request became optional. Once the
    Intelligence Layer (2.x) exists, this function is the single place that
    changes: it starts calling the scenario generator instead of reading a
    fixture, and no caller has to move.
    """
    return ScenarioSet(**_load_json(FIXTURES_DIR / "mock_forecast_scenario.json"))
