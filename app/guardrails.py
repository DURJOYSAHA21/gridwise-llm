from __future__ import annotations

from typing import Any

ALLOWED_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


def _noop(note_index: int, explanation: str = "This note does not affect today's energy schedule.") -> dict[str, Any]:
    return {
        "note_index": note_index,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": explanation,
    }


def _normalize_hours(hours: Any) -> list[int] | None:
    if not isinstance(hours, list) or not hours:
        return None
    cleaned: list[int] = []
    for h in hours:
        try:
            hi = int(h)
        except (TypeError, ValueError):
            return None
        if hi < 0 or hi > 23:
            return None
        cleaned.append(hi)
    unique = sorted(set(cleaned))
    if not unique:
        return None
    return unique


def validate_and_normalize_directives(
    raw_items: list[dict[str, Any]] | None,
    n_notes: int,
    battery_capacity_kwh: float,
) -> list[dict[str, Any]]:
    """Deterministic guardrails. Invalid/malformed items become no_op."""
    by_index: dict[int, dict[str, Any]] = {}

    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("note_index"))
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= n_notes or idx in by_index:
                continue
            normalized = _normalize_one(item, idx, battery_capacity_kwh)
            by_index[idx] = normalized

    result: list[dict[str, Any]] = []
    for i in range(n_notes):
        result.append(by_index.get(i, _noop(i, "Interpretation unavailable; treated as no_op.")))
    return result


def _normalize_one(item: dict[str, Any], idx: int, battery_capacity_kwh: float) -> dict[str, Any]:
    dtype = item.get("directive_type")
    if dtype not in ALLOWED_TYPES:
        return _noop(idx, "Unsupported directive type; treated as no_op.")

    explanation = str(item.get("explanation") or "").strip() or f"Interpreted as {dtype}."
    adj = item.get("structured_adjustment")

    if dtype == "no_op":
        return _noop(idx, explanation)

    if not isinstance(adj, dict):
        return _noop(idx, "Missing structured adjustment; treated as no_op.")

    hours = _normalize_hours(adj.get("hours"))
    if hours is None:
        return _noop(idx, "Invalid hours; treated as no_op.")

    if dtype == "solar_reduction":
        try:
            factor = float(adj.get("factor"))
        except (TypeError, ValueError):
            return _noop(idx, "Invalid solar factor; treated as no_op.")
        if factor < 0 or factor > 1 or not _finite(factor):
            return _noop(idx, "Solar factor out of range; treated as no_op.")
        return {
            "note_index": idx,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": {"hours": hours, "factor": factor},
            "explanation": explanation,
        }

    if dtype == "minimum_battery_reserve":
        try:
            reserve = float(adj.get("minimum_energy_kwh"))
        except (TypeError, ValueError):
            return _noop(idx, "Invalid reserve; treated as no_op.")
        if not _finite(reserve) or reserve < 0 or reserve > battery_capacity_kwh + 1e-9:
            return _noop(idx, "Reserve out of range; treated as no_op.")
        return {
            "note_index": idx,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": {"hours": hours, "minimum_energy_kwh": reserve},
            "explanation": explanation,
        }

    if dtype == "no_charge_window":
        return {
            "note_index": idx,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": {"hours": hours},
            "explanation": explanation,
        }

    if dtype == "no_discharge_window":
        return {
            "note_index": idx,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": {"hours": hours},
            "explanation": explanation,
        }

    if dtype == "max_grid_window":
        try:
            cap = float(adj.get("max_grid_kwh"))
        except (TypeError, ValueError):
            return _noop(idx, "Invalid grid cap; treated as no_op.")
        if not _finite(cap) or cap < 0:
            return _noop(idx, "Grid cap out of range; treated as no_op.")
        return {
            "note_index": idx,
            "applies": True,
            "directive_type": dtype,
            "structured_adjustment": {"hours": hours, "max_grid_kwh": cap},
            "explanation": explanation,
        }

    return _noop(idx)


def _finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def apply_effective_solar(
    solar: list[float],
    directives: list[dict[str, Any]],
) -> list[float]:
    effective = list(solar)
    for d in directives:
        if d.get("directive_type") != "solar_reduction" or not d.get("applies"):
            continue
        adj = d["structured_adjustment"]
        factor = float(adj["factor"])
        for h in adj["hours"]:
            effective[h] = solar[h] * factor
    return effective


def collect_constraints(directives: list[dict[str, Any]], base_min: float) -> dict[str, Any]:
    min_energy = [base_min] * 24
    no_charge: set[int] = set()
    no_discharge: set[int] = set()
    max_grid: dict[int, float] = {}

    for d in directives:
        if not d.get("applies") or d.get("directive_type") == "no_op":
            continue
        adj = d["structured_adjustment"]
        hours = adj["hours"]
        dtype = d["directive_type"]

        if dtype == "minimum_battery_reserve":
            reserve = float(adj["minimum_energy_kwh"])
            for h in hours:
                min_energy[h] = max(min_energy[h], reserve)
        elif dtype == "no_charge_window":
            no_charge.update(hours)
        elif dtype == "no_discharge_window":
            no_discharge.update(hours)
        elif dtype == "max_grid_window":
            cap = float(adj["max_grid_kwh"])
            for h in hours:
                if h in max_grid:
                    max_grid[h] = min(max_grid[h], cap)
                else:
                    max_grid[h] = cap

    return {
        "min_energy": min_energy,
        "no_charge": no_charge,
        "no_discharge": no_discharge,
        "max_grid": max_grid,
    }
