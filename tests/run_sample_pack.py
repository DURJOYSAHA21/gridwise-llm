"""Save the public sample pack JSON next to this script as:
samples/GridWise_Public_LLM_Sample_Case_Pack_v2.json

Then run: python tests/run_sample_pack.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.guardrails import apply_effective_solar, collect_constraints, validate_and_normalize_directives
from app.llm_interpreter import interpret_notes
from app.optimizer import optimize_schedule
from app.validator import replay_validate

PACK = ROOT / "samples" / "GridWise_Public_LLM_Sample_Case_Pack_v2.json"
TOL = 0.05


def directives_match(got, expected) -> list[str]:
    errs = []
    if len(got) != len(expected):
        return [f"length {len(got)} != {len(expected)}"]
    for g, e in zip(got, expected):
        if g["directive_type"] != e["directive_type"] or g["applies"] != e["applies"]:
            errs.append(f"note {e['note_index']}: type/applies {g['directive_type']}/{g['applies']} != {e['directive_type']}/{e['applies']}")
            continue
        if e["directive_type"] == "no_op":
            continue
        ga, ea = g["structured_adjustment"], e["structured_adjustment"]
        if ga["hours"] != ea["hours"]:
            errs.append(f"note {e['note_index']}: hours {ga['hours']} != {ea['hours']}")
        for key in ("factor", "minimum_energy_kwh", "max_grid_kwh"):
            if key in ea:
                if abs(float(ga.get(key, -1)) - float(ea[key])) > 1e-6:
                    errs.append(f"note {e['note_index']}: {key} {ga.get(key)} != {ea[key]}")
    return errs


def run_case(case: dict) -> None:
    cid = case["id"]
    inp = case["input"]
    exp = case["expected_output"]
    notes = inp["operator_notes"]
    bat = inp["battery"]
    hours = sorted(inp["hours"], key=lambda h: h["hour"])
    demand = [h["demand_kwh"] for h in hours]
    solar = [h["solar_kwh"] for h in hours]
    tariff = [h["tariff_bdt_per_kwh"] for h in hours]

    got = interpret_notes(notes, bat["capacity_kwh"])
    # Compare structured fields only
    exp_dirs = [
        {
            "note_index": d["note_index"],
            "applies": d["applies"],
            "directive_type": d["directive_type"],
            "structured_adjustment": d["structured_adjustment"],
        }
        for d in exp["directive_interpretation"]
    ]
    errs = directives_match(got, exp_dirs)
    if errs:
        raise AssertionError(f"{cid} interpretation errors: {errs}")

    # Also verify optimizer with ground-truth directives achieves ~optimal cost
    gt = validate_and_normalize_directives(exp["directive_interpretation"], len(notes), bat["capacity_kwh"])
    effective = apply_effective_solar(solar, gt)
    cons = collect_constraints(gt, bat["minimum_energy_kwh"])
    result = optimize_schedule(
        demand,
        effective,
        tariff,
        bat["capacity_kwh"],
        bat["initial_energy_kwh"],
        bat["minimum_energy_kwh"],
        bat["max_charge_kwh_per_hour"],
        bat["max_discharge_kwh_per_hour"],
        cons["min_energy"],
        cons["no_charge"],
        cons["no_discharge"],
        cons["max_grid"],
    )
    replay_validate(
        demand,
        effective,
        tariff,
        bat["capacity_kwh"],
        bat["initial_energy_kwh"],
        cons["min_energy"],
        bat["max_charge_kwh_per_hour"],
        bat["max_discharge_kwh_per_hour"],
        cons["no_charge"],
        cons["no_discharge"],
        cons["max_grid"],
        result["hourly_plan"],
        result["total_grid_kwh"],
        result["total_cost_bdt"],
        result["peak_grid_kwh"],
    )
    if result["total_cost_bdt"] > exp["total_cost_bdt"] + TOL:
        raise AssertionError(
            f"{cid} cost {result['total_cost_bdt']} > reference {exp['total_cost_bdt']}"
        )
    print(f"OK {cid}: cost={result['total_cost_bdt']} (ref {exp['total_cost_bdt']})")


def main() -> None:
    if not PACK.exists():
        print(f"Missing {PACK}")
        print("Save the official sample pack JSON to that path, then re-run.")
        sys.exit(1)
    data = json.loads(PACK.read_text(encoding="utf-8"))
    for case in data["cases"]:
        run_case(case)
    print("All sample cases passed.")


if __name__ == "__main__":
    main()
