from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.llm_interpreter import interpret_notes

CASES = [
    (
        "SAMPLE-01",
        220,
        [
            "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
            "The sports office moved next month's registration deadline.",
        ],
        [
            ("solar_reduction", {"hours": [12, 13], "factor": 0.25}),
            ("no_op", None),
        ],
    ),
    (
        "SAMPLE-02",
        200,
        ["The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."],
        [("no_charge_window", {"hours": [2, 3, 4]})],
    ),
    (
        "SAMPLE-03",
        200,
        ["Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations."],
        [("minimum_battery_reserve", {"hours": [18, 19, 20], "minimum_energy_kwh": 100})],
    ),
    (
        "SAMPLE-04",
        230,
        ["For protection testing, the battery must not discharge from 6 PM until 8 PM."],
        [("no_discharge_window", {"hours": [18, 19]})],
    ),
    (
        "SAMPLE-05",
        240,
        ["From 6 PM until 9 PM, campus grid import must not exceed 155 kWh in any hour because the feeder is operating under a temporary limit."],
        [("max_grid_window", {"hours": [18, 19, 20], "max_grid_kwh": 155})],
    ),
    (
        "SAMPLE-06",
        220,
        [
            "Cloud cover during panel inspection will leave about half of the forecast solar output from 10 AM until noon.",
            "The charging circuit will be unavailable from 2 PM until 4 PM.",
            "The library is extending book-return hours next week.",
        ],
        [
            ("solar_reduction", {"hours": [10, 11], "factor": 0.5}),
            ("no_charge_window", {"hours": [14, 15]}),
            ("no_op", None),
        ],
    ),
    (
        "SAMPLE-07",
        250,
        [
            "Keep at least 90 kWh in the battery from 6 PM until 10 PM for emergency services.",
            "The evening transformer limit is 180 kWh of grid import from 7 PM until 9 PM.",
        ],
        [
            ("minimum_battery_reserve", {"hours": [18, 19, 20, 21], "minimum_energy_kwh": 90}),
            ("max_grid_window", {"hours": [19, 20], "max_grid_kwh": 180}),
        ],
    ),
    (
        "SAMPLE-08",
        210,
        [
            "Battery charging is disabled from 11 AM until 1 PM while technicians inspect the charger.",
            "Do not discharge the battery from 5 PM until 7 PM during relay testing.",
        ],
        [
            ("no_charge_window", {"hours": [11, 12]}),
            ("no_discharge_window", {"hours": [17, 18]}),
        ],
    ),
    (
        "SAMPLE-09",
        240,
        [
            "Expect an 80% reduction in rooftop solar between 11 AM and 2 PM because of inverter work.",
            "The student affairs office will publish club notices tomorrow.",
        ],
        [
            ("solar_reduction", {"hours": [11, 12, 13], "factor": 0.2}),
            ("no_op", None),
        ],
    ),
    (
        "SAMPLE-10",
        260,
        [
            "The data center requires at least 80 kWh to remain in the battery from 6 PM until 10 PM.",
            "Grid intake must stay at or below 190 kWh from 7 PM until 10 PM while the substation is constrained.",
            "A seminar room booking was moved to next week.",
        ],
        [
            ("minimum_battery_reserve", {"hours": [18, 19, 20, 21], "minimum_energy_kwh": 80}),
            ("max_grid_window", {"hours": [19, 20, 21], "max_grid_kwh": 190}),
            ("no_op", None),
        ],
    ),
]


def main() -> None:
    failed = 0
    for cid, cap, notes, expected in CASES:
        got = interpret_notes(notes, cap)
        for g, (etype, eadj) in zip(got, expected):
            if g["directive_type"] != etype:
                print(f"FAIL {cid}: got {g['directive_type']} expected {etype} :: {g}")
                failed += 1
                continue
            if etype == "no_op":
                continue
            ga = g["structured_adjustment"]
            if ga["hours"] != eadj["hours"]:
                print(f"FAIL {cid}: hours {ga['hours']} != {eadj['hours']}")
                failed += 1
            for k in ("factor", "minimum_energy_kwh", "max_grid_kwh"):
                if k in eadj and abs(float(ga[k]) - float(eadj[k])) > 1e-6:
                    print(f"FAIL {cid}: {k} {ga[k]} != {eadj[k]}")
                    failed += 1
        else:
            print(f"OK {cid}")
    if failed:
        raise SystemExit(f"{failed} assertion(s) failed")
    print("All heuristic interpretation checks passed.")


if __name__ == "__main__":
    main()
