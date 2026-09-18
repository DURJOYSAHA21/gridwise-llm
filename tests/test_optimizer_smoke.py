from __future__ import annotations

"""Synthetic optimizer smoke test (no sample pack required)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.guardrails import apply_effective_solar, collect_constraints, validate_and_normalize_directives
from app.optimizer import optimize_schedule
from app.validator import replay_validate


def main() -> None:
    demand = [100.0] * 24
    solar = [0.0] * 24
    for h in range(10, 15):
        solar[h] = 80.0
    tariff = [5.0] * 24
    for h in range(17, 21):
        tariff[h] = 25.0

    directives = validate_and_normalize_directives(
        [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "no_charge_window",
                "structured_adjustment": {"hours": [2, 3, 4]},
                "explanation": "test",
            }
        ],
        1,
        200.0,
    )
    effective = apply_effective_solar(solar, directives)
    cons = collect_constraints(directives, 40.0)
    result = optimize_schedule(
        demand,
        effective,
        tariff,
        200.0,
        100.0,
        40.0,
        50.0,
        50.0,
        cons["min_energy"],
        cons["no_charge"],
        cons["no_discharge"],
        cons["max_grid"],
    )
    replay_validate(
        demand,
        effective,
        tariff,
        200.0,
        100.0,
        cons["min_energy"],
        50.0,
        50.0,
        cons["no_charge"],
        cons["no_discharge"],
        cons["max_grid"],
        result["hourly_plan"],
        result["total_grid_kwh"],
        result["total_cost_bdt"],
        result["peak_grid_kwh"],
    )
    for h in (2, 3, 4):
        p = result["hourly_plan"][h]
        assert p["battery_action"] != "charge", p
    assert abs(result["hourly_plan"][23]["battery_energy_after_kwh"] - 100.0) <= 0.01
    print("OK synthetic optimizer", result["total_cost_bdt"], result["total_grid_kwh"])


if __name__ == "__main__":
    main()
