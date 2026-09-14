"""
Module 3.4 support — cost parameter loading.

Cost parameters are never hard-coded in delivered_cost.py; they're loaded
from config/cost_parameters.yaml and versioned (the version string is
recorded on every optimization_run for reproducibility, per Phase-0 Section 30).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "cost_parameters.yaml"


class CostParameters(BaseModel):
    version: str
    wait_cost_per_day: float
    idle_cost_per_day: float
    demurrage_rate_per_day: float
    despatch_rate_per_day: float
    laytime_allowance_days: float
    port_cost_flat: dict[str, float]
    daily_opex_ballast: dict[str, float]
    bunker_price_usd_per_tonne: float
    bunker_consumption_tonnes_per_day: dict[str, float]
    carbon_cost_enabled: bool = False
    carbon_price_usd_per_tonne_co2: float = 0.0
    co2_emission_factor_tonnes_per_tonne_bunker: float = 3.114


class CostParametersMissingError(RuntimeError):
    """Raised when the cost parameter file cannot be found or parsed — the
    3.4 engine must fail loudly here (CONFIG_MISSING), never fall back to
    silent hard-coded defaults."""


def load_cost_parameters(path: Optional[Path] = None) -> CostParameters:
    target = path or DEFAULT_CONFIG_PATH
    if not target.exists():
        raise CostParametersMissingError(f"CONFIG_MISSING: cost parameter file not found at {target}")
    try:
        with open(target) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise CostParametersMissingError(f"CONFIG_MISSING: cost parameter file at {target} could not be parsed: {e}")
    try:
        return CostParameters(**raw)
    except Exception as e:
        raise CostParametersMissingError(f"CONFIG_MISSING: cost parameter file at {target} failed validation: {e}")
