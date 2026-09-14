"""
Generates tests/fixtures/mock_forecast_scenario.json — the mock fixture that
stands in for the Intelligence Layer (2.1/2.2), which isn't built yet.

Conforms to the ScenarioSet contract in app/schemas/common.py (Decision
Engine spec v2, Section 0): >=20-scenario Monte Carlo bank, dual voyage
($/tonne) and TC hire ($/day) rate paths, probabilities summing to 1.

Explicitly MOCK, per Phase-0 data provenance rules — calibrated to a
plausible freight-softening trend (declining P50 over the horizon) so the
downstream demo has a meaningful "wait vs charter now" decision to make,
not real market data.

TC hire rate conversion (voyage $/tonne -> TC $/day) is a documented,
simplified prototype approximation: TCE-style conversion using a reference
cargo size and round-trip duration per vessel class. This is NOT a real
freight-market TC forecast and is labeled as such in the output.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # reproducibility, per Phase-0 Section 30

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
HORIZON_START = date(2026, 9, 1)   # matches cargo.earliest_departure
HORIZON_DAYS = 46                  # covers up to and slightly past 2026-10-15 (cargo.delivery_deadline)
SCENARIO_COUNT = 40

# Illustrative reference cargo sizes/round-trip durations per class, used only
# to approximate a $/day TC hire rate from the $/tonne voyage rate. MOCK.
_TC_REFERENCE = {
    "PANAMAX": {"reference_cargo_tonnes": 75000, "round_trip_days": 30},
    "SUPRAMAX": {"reference_cargo_tonnes": 55000, "round_trip_days": 28},
    "CAPESIZE": {"reference_cargo_tonnes": 170000, "round_trip_days": 34},
    "HANDYSIZE": {"reference_cargo_tonnes": 32000, "round_trip_days": 26},
}


def _p50_trend(day_index: int) -> float:
    """Illustrative freight-softening trend: $16.0/t -> ~$14.3/t over the horizon."""
    return 16.0 - 0.037 * day_index


def _band_half_width(day_index: int) -> float:
    """Uncertainty widens further into the horizon (P90-P10 grows)."""
    return 1.2 + 0.05 * day_index


def _voyage_to_tc_rate(voyage_rate_usd_per_tonne: float, vessel_class: str) -> float:
    ref = _TC_REFERENCE[vessel_class]
    # Simplified TCE approximation: gross voyage revenue / round-trip duration,
    # net of an illustrative 35% non-hire voyage cost share (bunkers, port costs
    # the owner still bears net of hire). Documented as MOCK/approximate.
    gross_voyage_revenue = voyage_rate_usd_per_tonne * ref["reference_cargo_tonnes"]
    return round((gross_voyage_revenue * 0.65) / ref["round_trip_days"], 2)


def generate() -> dict:
    dates = [HORIZON_START + timedelta(days=i) for i in range(HORIZON_DAYS)]

    scenarios = []
    mc_costs_at_mid_horizon = []  # used to pick headline archetypes after generation

    for i in range(SCENARIO_COUNT):
        # Each scenario is a full correlated path: start from the P50 trend,
        # add a scenario-level persistent offset (drawn once) plus small daily
        # noise, both scaled by the day's band half-width -- this keeps paths
        # smooth (not day-to-day white noise) while still spanning the P10-P90
        # envelope across the bank as a whole.
        scenario_offset = random.gauss(0, 0.6)  # persistent bias for this scenario
        voyage_path = []
        for day_index, d in enumerate(dates):
            p50 = _p50_trend(day_index)
            half_width = _band_half_width(day_index)
            daily_noise = random.gauss(0, 0.15)
            rate = max(4.0, p50 + scenario_offset * half_width + daily_noise)
            voyage_path.append({"date": d.isoformat(), "rate": round(rate, 2)})

        tc_paths = {
            vessel_class: [
                {"date": row["date"], "rate": _voyage_to_tc_rate(row["rate"], vessel_class)}
                for row in voyage_path
            ]
            for vessel_class in _TC_REFERENCE
        }

        # One deliberately tagged congestion-shock scenario for the UI headline set.
        is_congestion_shock = i == SCENARIO_COUNT - 1
        congestion_shock_days = 4.5 if is_congestion_shock else 0.0

        mid_idx = HORIZON_DAYS // 2
        mc_costs_at_mid_horizon.append((i, voyage_path[mid_idx]["rate"]))

        scenarios.append(
            {
                "scenario_id": f"MC_{i:03d}",
                "headline_label": None,  # assigned below
                "probability": round(1.0 / SCENARIO_COUNT, 10),
                "voyage_freight_path_usd_per_tonne": voyage_path,
                "tc_hire_path_usd_per_day": tc_paths,
                "commodity_price_index": round(1.0 + scenario_offset * 0.05, 3),
                "base_congestion_shock_days": congestion_shock_days,
                "vessel_availability_shock": 0.0,
                "assumptions": (
                    "MOCK Monte Carlo draw from illustrative freight-softening trend"
                    + (" with a tagged port-congestion shock" if is_congestion_shock else "")
                ),
            }
        )

    # Normalize probabilities exactly to 1.0 (floating point safety, per the
    # ScenarioSet validator's 1e-6 tolerance).
    total = sum(s["probability"] for s in scenarios)
    scenarios[-1]["probability"] += 1.0 - total

    # Assign headline archetypes: low/base/high by mid-horizon rate rank,
    # plus the tagged congestion-shock scenario.
    ranked = sorted(mc_costs_at_mid_horizon, key=lambda t: t[1])
    low_idx = ranked[0][0]
    high_idx = ranked[-1][0]
    base_idx = ranked[len(ranked) // 2][0]
    scenarios[low_idx]["headline_label"] = "S1_LOW"
    scenarios[base_idx]["headline_label"] = "S2_BASE"
    scenarios[high_idx]["headline_label"] = "S3_HIGH"
    scenarios[SCENARIO_COUNT - 1]["headline_label"] = "S4_CONGESTION_SHOCK"

    return {
        "scenario_run_id": "SCEN-DEMO-001",
        "forecast_run_id": "FCST-DEMO-001",
        "scenario_count": SCENARIO_COUNT,
        "headline_scenarios": ["S1_LOW", "S2_BASE", "S3_HIGH", "S4_CONGESTION_SHOCK"],
        "scenarios": scenarios,
    }


if __name__ == "__main__":
    data = generate()
    out_path = FIXTURES_DIR / "mock_forecast_scenario.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    total_prob = sum(s["probability"] for s in data["scenarios"])
    print(f"Wrote {out_path} — {data['scenario_count']} scenarios, total probability = {total_prob:.10f}")
