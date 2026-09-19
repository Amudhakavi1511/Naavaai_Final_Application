"""
Read-only reference endpoints.

The frontend used to carry its own hardcoded copy of the loading-port network
and post an 800 KB scenario bank back to the server on every request. Both were
duplicated truth: a port could exist in the picker with no distance behind it,
and the only way to find out was a 500. These endpoints make the backend the
single source of that truth — the form is built from whatever the engine can
actually service, so an unservable option can't be offered in the first place.

Everything here is a projection of `ReferenceData`. No business logic lives in
this module, and nothing here can mutate state.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.reference_data import ReferenceData

router = APIRouter(prefix="/reference", tags=["reference"])


# ---------------------------------------------------------------------------
# Response contracts
# ---------------------------------------------------------------------------

class OriginPortOut(BaseModel):
    port_id: str
    name: str
    commodities: Optional[str] = None


class OriginCountryOut(BaseModel):
    country: str
    note: Optional[str] = None
    ports: list[OriginPortOut]


class DischargePortOut(BaseModel):
    port_id: str
    name: str
    state: str
    max_draft_m: float
    berth_count: int
    cargo_handling_rate_tonnes_per_day: float
    base_turnaround_days: float
    current_congestion_days: float


class CommodityOut(BaseModel):
    id: str
    label: str


class VesselOut(BaseModel):
    vessel_id: str
    name: str
    vessel_class: str
    dwt_tonnes: float
    draft_laden_m: float
    service_speed_knots: float
    open_date: Optional[str] = None
    open_port_id: Optional[str] = None
    reliability_score: Optional[float] = None


class ScenarioBankOut(BaseModel):
    scenario_run_id: str
    forecast_run_id: str
    scenario_count: int
    headline_scenarios: list[str]
    horizon_start: str
    horizon_end: str


class DefaultCargoOut(BaseModel):
    """A ready-to-run requirement the frontend seeds its form with.

    The dates matter: a cargo whose voyage falls outside the scenario bank's
    forecast horizon fails with INSUFFICIENT_FORECAST_HORIZON, and the client
    has no way to know where that horizon sits. Deriving the default here —
    from the bank the engine will actually solve against — means the form
    opens on a requirement that is guaranteed to run.
    """
    commodity: str
    quantity_tonnes: float
    origin_country: str
    origin_port_id: str
    destination_port_id: str
    earliest_departure: str
    delivery_deadline: str
    risk_preference: str


class BootstrapOut(BaseModel):
    """One round trip for everything the procurement form needs to render."""
    origins: list[OriginCountryOut]
    discharge_ports: list[DischargePortOut]
    commodities: list[CommodityOut]
    fleet_size: int
    scenario_bank: ScenarioBankOut
    default_cargo: DefaultCargoOut


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------

def _origins(reference_data: ReferenceData) -> list[OriginCountryOut]:
    grouped: dict[str, list[OriginPortOut]] = {}
    for port in reference_data.origin_ports():
        grouped.setdefault(port.country, []).append(
            OriginPortOut(port_id=port.port_id, name=port.name, commodities=port.commodities)
        )
    return [
        OriginCountryOut(country=country, note=reference_data.origin_metadata.get(country), ports=ports)
        for country, ports in sorted(grouped.items())
    ]


def _discharge_ports(reference_data: ReferenceData) -> list[DischargePortOut]:
    congestion = {c.port_id: c.current_congestion_days for c in reference_data.congestion_observations}
    return [
        DischargePortOut(
            port_id=port.port_id,
            name=port.name,
            state=state,
            max_draft_m=port.max_draft_m,
            berth_count=port.berth_count,
            cargo_handling_rate_tonnes_per_day=port.cargo_handling_rate_tonnes_per_day,
            base_turnaround_days=port.base_turnaround_days,
            current_congestion_days=congestion.get(port.port_id, 0.0),
        )
        for port, state in reference_data.discharge_ports()
    ]


def _horizon(reference_data: ReferenceData) -> tuple[str, str]:
    """Earliest and latest date the whole bank has a freight rate for. Taking
    the intersection across scenarios rather than the union: a date only one
    scenario covers is not a date the engine can price."""
    starts, ends = [], []
    for scenario in reference_data.default_scenario_set.scenarios:
        path = scenario.voyage_freight_path_usd_per_tonne
        if path:
            starts.append(path[0].date)
            ends.append(path[-1].date)
    if not starts:
        return "", ""
    return max(starts).isoformat(), min(ends).isoformat()


def _scenario_bank(reference_data: ReferenceData) -> ScenarioBankOut:
    bank = reference_data.default_scenario_set
    start, end = _horizon(reference_data)
    return ScenarioBankOut(
        scenario_run_id=bank.scenario_run_id,
        forecast_run_id=bank.forecast_run_id,
        scenario_count=bank.scenario_count,
        headline_scenarios=bank.headline_scenarios,
        horizon_start=start,
        horizon_end=end,
    )


def _default_cargo(reference_data: ReferenceData) -> DefaultCargoOut:
    start, end = _horizon(reference_data)
    origins = _origins(reference_data)
    # Prefer a lane with a curated distance behind it, so the form opens on the
    # best-evidenced route rather than a derived one.
    preferred = next(
        (p for c in origins for p in c.ports if p.port_id == "AU-HAY"),
        origins[0].ports[0] if origins and origins[0].ports else None,
    )
    country = next((c.country for c in origins if any(p.port_id == preferred.port_id for p in c.ports)), "")
    discharge = reference_data.discharge_ports()
    return DefaultCargoOut(
        commodity=reference_data.commodities[0]["id"] if reference_data.commodities else "coking_coal",
        quantity_tonnes=80000,
        origin_country=country,
        origin_port_id=preferred.port_id if preferred else "",
        destination_port_id=discharge[0][0].port_id if discharge else "",
        earliest_departure=start,
        delivery_deadline=end,
        risk_preference="BALANCED",
    )


# ---------------------------------------------------------------------------
# Routes — registered against the app's single ReferenceData instance
# ---------------------------------------------------------------------------

def register(app, reference_data: ReferenceData) -> None:

    @router.get("/bootstrap", response_model=BootstrapOut)
    def bootstrap() -> BootstrapOut:
        return BootstrapOut(
            origins=_origins(reference_data),
            discharge_ports=_discharge_ports(reference_data),
            commodities=[CommodityOut(**c) for c in reference_data.commodities],
            fleet_size=len(reference_data.vessels),
            scenario_bank=_scenario_bank(reference_data),
            default_cargo=_default_cargo(reference_data),
        )

    @router.get("/origins", response_model=list[OriginCountryOut])
    def origins() -> list[OriginCountryOut]:
        return _origins(reference_data)

    @router.get("/discharge-ports", response_model=list[DischargePortOut])
    def discharge_ports() -> list[DischargePortOut]:
        return _discharge_ports(reference_data)

    @router.get("/commodities", response_model=list[CommodityOut])
    def commodities() -> list[CommodityOut]:
        return [CommodityOut(**c) for c in reference_data.commodities]

    @router.get("/vessels", response_model=list[VesselOut])
    def vessels() -> list[VesselOut]:
        availability = {a.vessel_id: a for a in reference_data.availabilities}
        out = []
        for vessel in reference_data.vessels:
            avail = availability.get(vessel.vessel_id)
            out.append(
                VesselOut(
                    vessel_id=vessel.vessel_id,
                    name=vessel.name,
                    vessel_class=vessel.vessel_class.value,
                    dwt_tonnes=vessel.dwt_tonnes,
                    draft_laden_m=vessel.draft_laden_m,
                    service_speed_knots=vessel.service_speed_knots,
                    open_date=avail.open_date.isoformat() if avail else None,
                    open_port_id=avail.open_port_id if avail else None,
                    reliability_score=vessel.reliability_score,
                )
            )
        return out

    app.include_router(router)
