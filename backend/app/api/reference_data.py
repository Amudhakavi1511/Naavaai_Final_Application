"""
Reference data loader — STAND-IN for the database layer (PostgreSQL schema
from Phase-0 Section 7), which hasn't been built yet.

Vessel/port/distance/congestion master data belongs in a database in the
real architecture (see Level-1 DFD: "VesselMaster"/"PortMaster" feed 3.1/3.2
directly, not the per-request API payload). Until that DB layer exists, this
module loads the same demo fixtures the test suite uses, functioning as a
temporary "database" for the API to query. This is a STATED simplification,
not a hidden one — swapping this module for a real repository backed by
PostgreSQL is the only change needed when the DB layer is built; nothing
downstream (3.1-3.6, the API routes) needs to change.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.cost.params_loader import CostParameters, load_cost_parameters
from app.schemas.common import CongestionObservation, Port, RouteDistance, Vessel, VesselAvailability

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


class ReferenceData:
    def __init__(
        self,
        vessels: list[Vessel],
        availabilities: list[VesselAvailability],
        ports_by_id: dict[str, Port],
        congestion_observations: list[CongestionObservation],
        distances: list[RouteDistance],
        cost_params: CostParameters,
    ):
        self.vessels = vessels
        self.availabilities = availabilities
        self.ports_by_id = ports_by_id
        self.congestion_observations = congestion_observations
        self.distances = distances
        self.cost_params = cost_params


def _load_json(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def load_demo_reference_data() -> ReferenceData:
    """Loads the same fixture fleet/port-network/distance-table used by the
    test suite — the SIH demo dataset described in the spec's Section M
    (fully deterministic, offline-capable)."""
    vdata = _load_json("mock_vessels.json")
    vessels = [Vessel(**v) for v in vdata["vessels"]]
    availabilities = [
        VesselAvailability(**{k: v for k, v in a.items() if not k.startswith("_")})
        for a in vdata["vessel_availability"]
    ]

    pdata = _load_json("mock_ports.json")
    ports_by_id = {p["port_id"]: Port(**p) for p in pdata["ports"]}
    congestion_observations = [CongestionObservation(**c) for c in pdata["congestion_observations"]]

    ddata = _load_json("mock_distances.json")
    distances = [RouteDistance(**d) for d in ddata["distances"]]

    cost_params = load_cost_parameters()

    return ReferenceData(
        vessels=vessels,
        availabilities=availabilities,
        ports_by_id=ports_by_id,
        congestion_observations=congestion_observations,
        distances=distances,
        cost_params=cost_params,
    )
