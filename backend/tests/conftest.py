from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.common import (
    CargoRequirement,
    CongestionObservation,
    Port,
    RouteDistance,
    ScenarioSet,
    Vessel,
    VesselAvailability,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def cargo() -> CargoRequirement:
    return CargoRequirement(**_load("cargo_requirement.json"))


@pytest.fixture
def vessels() -> list[Vessel]:
    data = _load("mock_vessels.json")
    return [Vessel(**v) for v in data["vessels"]]


@pytest.fixture
def availabilities() -> list[VesselAvailability]:
    data = _load("mock_vessels.json")
    return [VesselAvailability(**{k: v for k, v in a.items() if not k.startswith("_")}) for a in data["vessel_availability"]]


@pytest.fixture
def ports_by_id() -> dict[str, Port]:
    data = _load("mock_ports.json")
    return {p["port_id"]: Port(**p) for p in data["ports"]}


@pytest.fixture
def congestion_observations() -> list[CongestionObservation]:
    data = _load("mock_ports.json")
    return [CongestionObservation(**c) for c in data["congestion_observations"]]


@pytest.fixture
def distances() -> list[RouteDistance]:
    data = _load("mock_distances.json")
    return [RouteDistance(**d) for d in data["distances"]]


@pytest.fixture
def scenario_set() -> ScenarioSet:
    return ScenarioSet(**_load("mock_forecast_scenario.json"))
