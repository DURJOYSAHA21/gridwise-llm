from __future__ import annotations

from typing import Any


TOL = 0.01


def replay_validate(
    demand: list[float],
    effective_solar: list[float],
    tariff: list[float],
    capacity: float,
    initial: float,
    min_energy: list[float],
    max_charge: float,
    max_discharge: float,
    no_charge: set[int],
    no_discharge: set[int],
    max_grid: dict[int, float],
    plan: list[dict[str, Any]],
    total_grid_kwh: float,
    total_cost_bdt: float,
    peak_grid_kwh: float,
) -> None:
    if len(plan) != 24:
        raise ValueError("hourly_plan must have 24 entries")
    hours = sorted(p["hour"] for p in plan)
    if hours != list(range(24)):
        raise ValueError("hourly_plan hours must be 0..23 unique")

    e = initial
    recomputed_grid = 0.0
    recomputed_cost = 0.0
    peak = 0.0

    for p in sorted(plan, key=lambda x: x["hour"]):
        h = p["hour"]
        grid = float(p["grid_kwh"])
        solar_used = float(p["solar_used_kwh"])
        action = p["battery_action"]
        bkwh = float(p["battery_kwh"])
        e_after = float(p["battery_energy_after_kwh"])

        if grid < -TOL or solar_used < -TOL or bkwh < -TOL:
            raise ValueError(f"negative energy at hour {h}")
        if solar_used > effective_solar[h] + TOL:
            raise ValueError(f"solar_used exceeds effective solar at hour {h}")

        if action == "idle":
            if bkwh > TOL:
                raise ValueError(f"idle must have battery_kwh=0 at hour {h}")
            charge = discharge = 0.0
        elif action == "charge":
            charge, discharge = bkwh, 0.0
            if charge > max_charge + TOL:
                raise ValueError(f"charge rate exceeded at hour {h}")
            if h in no_charge and charge > TOL:
                raise ValueError(f"no_charge violated at hour {h}")
        elif action == "discharge":
            charge, discharge = 0.0, bkwh
            if discharge > max_discharge + TOL:
                raise ValueError(f"discharge rate exceeded at hour {h}")
            if h in no_discharge and discharge > TOL:
                raise ValueError(f"no_discharge violated at hour {h}")
        else:
            raise ValueError(f"invalid battery_action at hour {h}")

        if abs((grid + solar_used + discharge) - (demand[h] + charge)) > TOL:
            raise ValueError(f"energy balance failed at hour {h}")

        expected_e = e + charge - discharge
        if abs(expected_e - e_after) > TOL:
            raise ValueError(f"battery transition failed at hour {h}")
        if e_after < min_energy[h] - TOL or e_after > capacity + TOL:
            raise ValueError(f"battery bounds failed at hour {h}")
        if h in max_grid and grid > max_grid[h] + TOL:
            raise ValueError(f"max_grid violated at hour {h}")

        e = e_after
        recomputed_grid += grid
        recomputed_cost += grid * tariff[h]
        peak = max(peak, grid)

    if abs(e - initial) > TOL:
        raise ValueError("end-of-day battery neutrality failed")
    if abs(recomputed_grid - total_grid_kwh) > TOL:
        raise ValueError("total_grid_kwh mismatch")
    if abs(recomputed_cost - total_cost_bdt) > TOL:
        raise ValueError("total_cost_bdt mismatch")
    if abs(peak - peak_grid_kwh) > TOL:
        raise ValueError("peak_grid_kwh mismatch")
