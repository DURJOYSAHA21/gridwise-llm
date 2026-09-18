from __future__ import annotations

from typing import Any

import pulp


def optimize_schedule(
    demand: list[float],
    effective_solar: list[float],
    tariff: list[float],
    capacity: float,
    initial: float,
    base_minimum: float,
    max_charge: float,
    max_discharge: float,
    min_energy: list[float],
    no_charge: set[int],
    no_discharge: set[int],
    max_grid: dict[int, float],
) -> dict[str, Any]:
    """Minimize grid electricity cost subject to GridWise + directive constraints."""
    hours = range(24)
    prob = pulp.LpProblem("gridwise_optimize", pulp.LpMinimize)

    grid = pulp.LpVariable.dicts("grid", hours, lowBound=0)
    solar_used = pulp.LpVariable.dicts("solar_used", hours, lowBound=0)
    charge = pulp.LpVariable.dicts("charge", hours, lowBound=0)
    discharge = pulp.LpVariable.dicts("discharge", hours, lowBound=0)
    e_after = pulp.LpVariable.dicts("e_after", hours, lowBound=0)
    is_charge = pulp.LpVariable.dicts("is_charge", hours, cat="Binary")
    is_discharge = pulp.LpVariable.dicts("is_discharge", hours, cat="Binary")

    prob += pulp.lpSum(grid[h] * tariff[h] for h in hours)

    for h in hours:
        # Energy balance
        prob += (
            grid[h] + solar_used[h] + discharge[h] == demand[h] + charge[h],
            f"balance_{h}",
        )
        # Solar
        prob += solar_used[h] <= effective_solar[h], f"solar_cap_{h}"

        # Battery dynamics
        e_before = initial if h == 0 else e_after[h - 1]
        prob += e_after[h] == e_before + charge[h] - discharge[h], f"soc_{h}"
        prob += e_after[h] >= min_energy[h], f"min_e_{h}"
        prob += e_after[h] <= capacity, f"max_e_{h}"

        # Mutual exclusion + rate limits
        prob += charge[h] <= max_charge * is_charge[h], f"chg_bin_{h}"
        prob += discharge[h] <= max_discharge * is_discharge[h], f"dis_bin_{h}"
        prob += is_charge[h] + is_discharge[h] <= 1, f"mutex_{h}"

        if h in no_charge:
            prob += charge[h] == 0, f"no_chg_{h}"
            prob += is_charge[h] == 0, f"no_chg_bin_{h}"
        if h in no_discharge:
            prob += discharge[h] == 0, f"no_dis_{h}"
            prob += is_discharge[h] == 0, f"no_dis_bin_{h}"
        if h in max_grid:
            prob += grid[h] <= max_grid[h], f"max_grid_{h}"

    # End-of-day neutrality
    prob += e_after[23] == initial, "eod_neutrality"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Optimization failed: {pulp.LpStatus[status]}")

    plan: list[dict[str, Any]] = []
    for h in hours:
        c = float(pulp.value(charge[h]) or 0.0)
        d = float(pulp.value(discharge[h]) or 0.0)
        g = float(pulp.value(grid[h]) or 0.0)
        s = float(pulp.value(solar_used[h]) or 0.0)
        e = float(pulp.value(e_after[h]) or 0.0)

        # Round lightly for stability within 0.01 tolerance
        c, d, g, s, e = (_r(c), _r(d), _r(g), _r(s), _r(e))

        if c > 1e-6 and d > 1e-6:
            # Prefer the larger action if numerical noise
            if c >= d:
                d = 0.0
            else:
                c = 0.0

        if c > 1e-6:
            action = "charge"
            bkwh = c
        elif d > 1e-6:
            action = "discharge"
            bkwh = d
        else:
            action = "idle"
            bkwh = 0.0

        plan.append(
            {
                "hour": h,
                "grid_kwh": g,
                "solar_used_kwh": s,
                "battery_action": action,
                "battery_kwh": bkwh,
                "battery_energy_after_kwh": e,
            }
        )

    total_grid = _r(sum(p["grid_kwh"] for p in plan))
    total_cost = _r(sum(plan[h]["grid_kwh"] * tariff[h] for h in hours))
    peak = _r(max(p["grid_kwh"] for p in plan))

    return {
        "hourly_plan": plan,
        "total_grid_kwh": total_grid,
        "total_cost_bdt": total_cost,
        "peak_grid_kwh": peak,
    }


def _r(x: float, nd: int = 6) -> float:
    return round(float(x), nd)
