"""
Route distance generator.

The curated distance table (tests/fixtures/mock_distances.json) covers only the
handful of port pairs the original demo scenario needed. Once the loading-port
network was widened to the countries India actually imports dry bulk from, the
number of pairs needed became (ports x ports) — far too many to hand-maintain,
and hand-maintaining them would have been fake precision anyway.

So this module derives the missing ones. It does NOT use a straight great-circle
distance between the two ports: a great circle from New Orleans to Paradip runs
across Africa, and one from Hay Point to Paradip runs across Australia. Instead
it builds a small graph of ocean waypoints (Cape of Good Hope, Bab el Mandeb,
Suez, Gibraltar, Malacca, Sunda, Lombok, Torres, Panama, and so on), connects
each port to the waypoints it can actually reach on open water, and runs
Dijkstra over great-circle leg lengths. The resulting figure is a plausible
sailing distance along a plausible route, and the route itself is reported back
in `route_via` so it can be inspected rather than trusted blindly.

Provenance, stated plainly:
  - Curated entries stay MOCK and always win. Nothing generated here can
    overwrite them, which is what keeps the existing test expectations intact.
  - Generated entries are tagged DERIVED. They are illustrative, not
    navigational data: no traffic separation schemes, no seasonal ice limits,
    no draft restrictions in canals or straits, no weather routing, and a flat
    ROUTE_FACTOR standing in for coastal deviation. A production system would
    replace this module with a real distance table (AtoBviaC, Netpas or
    equivalent) — the rest of the engine is unaffected, because everything
    downstream only ever asks for a number in nautical miles.
"""
from __future__ import annotations

import heapq
import math
from typing import Iterable, Optional

from app.schemas.common import DataSourceType, Port, RouteDistance

# Coastal deviation, pilotage and traffic-scheme allowance applied on top of the
# summed great-circle legs. Flat, deliberately modest, and stated rather than
# tuned to make any particular route look good.
ROUTE_FACTOR = 1.05

# Two ports closer than this are treated as directly connected, so neighbouring
# terminals (Paradip/Dhamra, Hay Point/Dalrymple Bay, Fujairah/Khor Fakkan)
# don't get routed out to an ocean waypoint and back.
NEIGHBOUR_THRESHOLD_NM = 300.0

EARTH_RADIUS_NM = 3440.065


# ---------------------------------------------------------------------------
# Waypoints
# ---------------------------------------------------------------------------

WAYPOINTS: dict[str, tuple[float, float]] = {
    "WP-DONDRA": (5.5, 80.6),            # south of Sri Lanka — the gate to the Bay of Bengal
    "WP-MALACCA-E": (1.3, 104.0),        # Singapore Strait
    "WP-MALACCA-W": (5.9, 95.2),         # Great Channel, north of Sumatra
    "WP-SUNDA": (-6.0, 105.9),
    "WP-LOMBOK": (-8.7, 115.8),
    "WP-JAVA": (-5.5, 112.5),
    "WP-MAKASSAR": (-3.5, 118.5),
    "WP-ARAFURA": (-9.5, 130.0),
    "WP-TORRES": (-10.6, 142.0),
    "WP-AU-BASS": (-39.6, 146.5),        # Bass Strait
    "WP-AU-LEEUWIN": (-35.0, 115.0),     # Cape Leeuwin
    "WP-SCS": (10.5, 112.5),             # South China Sea
    "WP-LUZON": (18.5, 120.5),           # Luzon Strait
    "WP-NPAC": (45.0, 170.0),            # North Pacific great-circle waypoint
    "WP-CAPE": (-35.0, 20.0),            # Cape of Good Hope
    "WP-BAB": (12.6, 43.4),              # Bab el Mandeb
    "WP-SUEZ": (31.3, 32.3),             # Port Said
    "WP-GIB": (35.9, -5.6),              # Strait of Gibraltar
    "WP-FINISTERRE": (42.9, -9.5),
    "WP-USHANT": (48.4, -5.1),
    "WP-DOVER": (50.9, 1.4),
    "WP-SKAGEN": (57.8, 10.5),
    "WP-RECIFE": (-8.0, -34.5),          # Brazilian corner, South Atlantic turn
    "WP-FLORIDA": (25.0, -79.8),         # Florida Straits
    "WP-PANAMA-A": (9.4, -79.9),         # Colón, Atlantic side
    "WP-PANAMA-P": (8.9, -79.6),         # Balboa, Pacific side
}

# Waypoint-to-waypoint legs. Distance is great-circle unless overridden.
WAYPOINT_LEGS: list[tuple[str, str]] = [
    ("WP-DONDRA", "WP-MALACCA-W"),
    ("WP-MALACCA-W", "WP-MALACCA-E"),
    ("WP-MALACCA-E", "WP-SCS"),
    ("WP-MALACCA-E", "WP-JAVA"),
    ("WP-SCS", "WP-LUZON"),
    ("WP-SCS", "WP-MAKASSAR"),
    ("WP-LUZON", "WP-NPAC"),
    ("WP-JAVA", "WP-SUNDA"),
    ("WP-JAVA", "WP-LOMBOK"),
    ("WP-JAVA", "WP-MAKASSAR"),
    ("WP-SUNDA", "WP-DONDRA"),
    ("WP-LOMBOK", "WP-DONDRA"),
    ("WP-LOMBOK", "WP-ARAFURA"),
    ("WP-ARAFURA", "WP-TORRES"),
    ("WP-TORRES", "WP-AU-BASS"),
    ("WP-AU-BASS", "WP-AU-LEEUWIN"),
    ("WP-AU-LEEUWIN", "WP-DONDRA"),
    ("WP-AU-LEEUWIN", "WP-SUNDA"),
    ("WP-AU-LEEUWIN", "WP-CAPE"),
    ("WP-DONDRA", "WP-BAB"),
    ("WP-DONDRA", "WP-CAPE"),
    ("WP-BAB", "WP-SUEZ"),
    ("WP-SUEZ", "WP-GIB"),
    ("WP-GIB", "WP-FINISTERRE"),
    ("WP-GIB", "WP-FLORIDA"),
    ("WP-GIB", "WP-RECIFE"),
    ("WP-FINISTERRE", "WP-USHANT"),
    ("WP-USHANT", "WP-DOVER"),
    ("WP-DOVER", "WP-SKAGEN"),
    ("WP-CAPE", "WP-RECIFE"),
    ("WP-RECIFE", "WP-FLORIDA"),
    ("WP-FLORIDA", "WP-PANAMA-A"),
    ("WP-PANAMA-A", "WP-PANAMA-P"),
    ("WP-PANAMA-P", "WP-LUZON"),
    ("WP-PANAMA-P", "WP-NPAC"),
]

# Legs whose length is not a great circle: canal and strait transits.
LEG_OVERRIDES: dict[frozenset[str], float] = {
    frozenset({"WP-PANAMA-A", "WP-PANAMA-P"}): 44.0,   # Panama Canal transit
    frozenset({"WP-BAB", "WP-SUEZ"}): 1300.0,          # Red Sea + Suez Canal
}

# Which waypoints each port can reach directly on open water. A port missing
# from this map falls back to its nearest three waypoints, which is fine for
# the ports that only ever appear as vessel open positions.
PORT_GATEWAYS: dict[str, list[str]] = {
    # East Coast India
    "IN-PARADIP": ["WP-DONDRA"],
    "IN-DHAMRA": ["WP-DONDRA"],
    "IN-GOPALPUR": ["WP-DONDRA"],
    "IN-VIZAG": ["WP-DONDRA"],
    "IN-GANGAVARAM": ["WP-DONDRA"],
    "IN-HALDIA": ["WP-DONDRA"],
    # Australia
    "AU-HAY": ["WP-TORRES", "WP-AU-BASS"],
    "AU-DBC": ["WP-TORRES", "WP-AU-BASS"],
    "AU-GLD": ["WP-TORRES", "WP-AU-BASS"],
    "AU-NEW": ["WP-AU-BASS", "WP-TORRES"],
    "AU-PHE": ["WP-SUNDA", "WP-LOMBOK", "WP-AU-LEEUWIN"],
    "AU-FRE": ["WP-AU-LEEUWIN"],
    # Indonesia
    "ID-TBN": ["WP-JAVA", "WP-MAKASSAR"],
    "ID-BJM": ["WP-JAVA", "WP-MAKASSAR"],
    "ID-SMR": ["WP-MAKASSAR"],
    "ID-BPN": ["WP-MAKASSAR"],
    # Singapore
    "SG-SIN": ["WP-MALACCA-E"],
    # United States
    "US-BAL": ["WP-FLORIDA", "WP-GIB"],
    "US-NOR": ["WP-FLORIDA", "WP-GIB"],
    "US-NOL": ["WP-FLORIDA"],
    "US-MOB": ["WP-FLORIDA"],
    # Colombia
    "CO-PBO": ["WP-FLORIDA", "WP-PANAMA-A"],
    "CO-SMR": ["WP-FLORIDA", "WP-PANAMA-A"],
    # Brazil
    "BR-PDM": ["WP-RECIFE"],
    "BR-TUB": ["WP-RECIFE", "WP-CAPE"],
    "BR-SEP": ["WP-RECIFE", "WP-CAPE"],
    # Mozambique / South Africa
    "MZ-BEW": ["WP-CAPE", "WP-DONDRA"],
    "MZ-NAC": ["WP-CAPE", "WP-DONDRA"],
    "MZ-MPM": ["WP-CAPE", "WP-DONDRA"],
    "ZA-RBY": ["WP-CAPE", "WP-DONDRA"],
    "ZA-DUR": ["WP-CAPE", "WP-DONDRA"],
    "ZA-SDB": ["WP-CAPE"],
    # Canada
    "CA-VAN": ["WP-NPAC", "WP-PANAMA-P"],
    "CA-PRR": ["WP-NPAC", "WP-PANAMA-P"],
    # Russia
    "RU-VNY": ["WP-LUZON", "WP-NPAC"],
    "RU-NAK": ["WP-LUZON", "WP-NPAC"],
    "RU-UST": ["WP-SKAGEN"],
    # Arabian Gulf / Gulf of Oman
    "OM-SOH": ["WP-DONDRA", "WP-BAB"],
    "OM-SLL": ["WP-DONDRA", "WP-BAB"],
    "AE-FJR": ["WP-DONDRA", "WP-BAB"],
    "AE-KHA": ["WP-DONDRA", "WP-BAB"],
}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def great_circle_nm(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(h)))


# ---------------------------------------------------------------------------
# Graph construction and shortest path
# ---------------------------------------------------------------------------

class RouteGraph:
    def __init__(self, ports: Iterable[Port]):
        self._coords: dict[str, tuple[float, float]] = dict(WAYPOINTS)
        self._adj: dict[str, dict[str, float]] = {name: {} for name in WAYPOINTS}

        self.located_port_ids: list[str] = []
        for port in ports:
            if port.latitude is None or port.longitude is None:
                continue
            self._coords[port.port_id] = (port.latitude, port.longitude)
            self._adj.setdefault(port.port_id, {})
            self.located_port_ids.append(port.port_id)

        for a, b in WAYPOINT_LEGS:
            self._link(a, b, LEG_OVERRIDES.get(frozenset({a, b})))

        for port_id in self.located_port_ids:
            for wp in self._gateways_for(port_id):
                self._link(port_id, wp)

        # Neighbouring terminals connect directly rather than via open ocean.
        for i, a in enumerate(self.located_port_ids):
            for b in self.located_port_ids[i + 1:]:
                d = great_circle_nm(self._coords[a], self._coords[b])
                if d <= NEIGHBOUR_THRESHOLD_NM:
                    self._link(a, b)

    def _link(self, a: str, b: str, fixed_nm: Optional[float] = None) -> None:
        d = fixed_nm if fixed_nm is not None else great_circle_nm(self._coords[a], self._coords[b])
        self._adj[a][b] = d
        self._adj[b][a] = d

    def _gateways_for(self, port_id: str) -> list[str]:
        declared = PORT_GATEWAYS.get(port_id)
        if declared:
            return [wp for wp in declared if wp in WAYPOINTS]
        # Undeclared port: attach to its three nearest waypoints so it is at
        # least reachable. Reported distances for such ports are rougher.
        here = self._coords[port_id]
        ranked = sorted(WAYPOINTS, key=lambda wp: great_circle_nm(here, WAYPOINTS[wp]))
        return ranked[:3]

    def shortest(self, origin: str, destination: str) -> Optional[tuple[float, str]]:
        """Returns (distance_nm, route description) or None if unreachable."""
        if origin == destination:
            return 0.0, "same port"
        if origin not in self._adj or destination not in self._adj:
            return None

        dist = {origin: 0.0}
        prev: dict[str, str] = {}
        seen: set[str] = set()
        queue: list[tuple[float, str]] = [(0.0, origin)]

        while queue:
            d, node = heapq.heappop(queue)
            if node in seen:
                continue
            seen.add(node)
            if node == destination:
                break
            for neighbour, leg in self._adj[node].items():
                nd = d + leg
                if nd < dist.get(neighbour, math.inf):
                    dist[neighbour] = nd
                    prev[neighbour] = node
                    heapq.heappush(queue, (nd, neighbour))

        if destination not in dist:
            return None

        chain, node = [], destination
        while node in prev:
            node = prev[node]
            chain.append(node)
        waypoints = [n for n in reversed(chain) if n.startswith("WP-")]
        route = " > ".join(waypoints) if waypoints else "direct"
        return round(dist[destination] * ROUTE_FACTOR), route


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_distance_table(
    ports: Iterable[Port],
    curated: list[RouteDistance],
) -> list[RouteDistance]:
    """
    Returns the curated distances unchanged, plus a DERIVED entry for every
    remaining pair of located ports. Curated entries always win: the generator
    never overwrites a number somebody put there on purpose.
    """
    ports = list(ports)
    table = list(curated)
    known: set[frozenset[str]] = {frozenset({d.from_port_id, d.to_port_id}) for d in curated}

    graph = RouteGraph(ports)
    ids = graph.located_port_ids

    for i, a in enumerate(ids):
        for b in ids[i:]:
            pair = frozenset({a, b})
            if pair in known:
                continue
            known.add(pair)
            result = graph.shortest(a, b)
            if result is None:
                continue
            distance_nm, route = result
            table.append(
                RouteDistance(
                    from_port_id=a,
                    to_port_id=b,
                    distance_nm=distance_nm,
                    data_source_type=DataSourceType.DERIVED,
                    route_via=route,
                )
            )

    return table
