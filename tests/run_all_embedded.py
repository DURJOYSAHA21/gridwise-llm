from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def H(demand, solar, tariff):
    return [
        {"hour": i, "demand_kwh": demand[i], "solar_kwh": solar[i], "tariff_bdt_per_kwh": tariff[i]}
        for i in range(24)
    ]


CASES = [
    {
        "id": "SAMPLE-01",
        "notes": [
            "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
            "The sports office moved next month's registration deadline.",
        ],
        "hours": H(
            [90,85,80,80,85,95,110,130,150,165,175,180,185,180,170,165,170,185,205,215,205,175,135,105],
            [0,0,0,0,0,0,5,20,50,90,130,160,180,170,140,90,45,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,14,16,16,15,14,13,14,18,22,28,30,26,18,10,7],
        ),
        "battery": {"capacity_kwh": 220, "initial_energy_kwh": 110, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 50, "max_discharge_kwh_per_hour": 50},
        "types": ["solar_reduction", "no_op"],
        "cost": 38365,
    },
    {
        "id": "SAMPLE-02",
        "notes": ["The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."],
        "hours": H(
            [100,95,90,90,95,105,120,135,145,155,165,175,180,175,165,160,170,190,210,220,210,180,145,115],
            [0,0,0,0,0,0,0,10,30,55,80,100,110,105,85,60,30,10,0,0,0,0,0,0],
            [6,5,4,4,4,5,7,9,11,13,15,16,16,15,14,15,19,24,31,33,29,20,11,7],
        ),
        "battery": {"capacity_kwh": 200, "initial_energy_kwh": 70, "minimum_energy_kwh": 30, "max_charge_kwh_per_hour": 55, "max_discharge_kwh_per_hour": 55},
        "types": ["no_charge_window"],
        "cost": 42885,
    },
    {
        "id": "SAMPLE-03",
        "notes": ["Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations."],
        "hours": H(
            [90,85,80,80,85,95,110,130,150,165,175,180,185,180,170,165,170,185,205,215,205,175,135,105],
            [0,0,0,0,0,0,5,20,50,90,130,160,180,170,140,90,45,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,14,16,16,15,14,13,14,18,22,28,30,26,18,10,7],
        ),
        "battery": {"capacity_kwh": 200, "initial_energy_kwh": 120, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 50, "max_discharge_kwh_per_hour": 50},
        "types": ["minimum_battery_reserve"],
        "cost": 35480,
    },
    {
        "id": "SAMPLE-04",
        "notes": ["For protection testing, the battery must not discharge from 6 PM until 8 PM."],
        "hours": H(
            [95,90,85,85,90,100,115,130,145,155,165,175,180,175,170,165,175,195,215,225,215,185,150,120],
            [0,0,0,0,0,0,5,15,40,75,110,145,165,155,125,80,35,5,0,0,0,0,0,0],
            [7,6,6,5,5,6,8,10,12,14,16,16,15,14,13,14,17,21,29,32,30,20,11,8],
        ),
        "battery": {"capacity_kwh": 230, "initial_energy_kwh": 130, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 55, "max_discharge_kwh_per_hour": 55},
        "types": ["no_discharge_window"],
        "cost": 40495,
    },
    {
        "id": "SAMPLE-05",
        "notes": ["From 6 PM until 9 PM, campus grid import must not exceed 155 kWh in any hour because the feeder is operating under a temporary limit."],
        "hours": H(
            [90,85,80,80,85,95,110,130,150,165,175,180,185,180,170,165,170,185,205,215,205,175,135,105],
            [0,0,0,0,0,0,5,20,50,90,130,160,180,170,140,90,45,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,14,16,16,15,14,13,14,18,22,28,30,26,18,10,7],
        ),
        "battery": {"capacity_kwh": 240, "initial_energy_kwh": 120, "minimum_energy_kwh": 30, "max_charge_kwh_per_hour": 60, "max_discharge_kwh_per_hour": 60},
        "types": ["max_grid_window"],
        "cost": 33950,
    },
    {
        "id": "SAMPLE-06",
        "notes": [
            "Cloud cover during panel inspection will leave about half of the forecast solar output from 10 AM until noon.",
            "The charging circuit will be unavailable from 2 PM until 4 PM.",
            "The library is extending book-return hours next week.",
        ],
        "hours": H(
            [85,80,80,80,85,95,110,125,140,155,165,175,180,175,170,165,175,190,205,215,205,175,140,110],
            [0,0,0,0,0,0,5,20,55,100,150,190,210,200,160,100,50,15,0,0,0,0,0,0],
            [5,5,5,6,6,7,8,9,11,13,15,16,16,15,14,15,18,22,27,29,27,18,10,7],
        ),
        "battery": {"capacity_kwh": 220, "initial_energy_kwh": 100, "minimum_energy_kwh": 35, "max_charge_kwh_per_hour": 50, "max_discharge_kwh_per_hour": 50},
        "types": ["solar_reduction", "no_charge_window", "no_op"],
        "cost": 34090,
    },
    {
        "id": "SAMPLE-07",
        "notes": [
            "Keep at least 90 kWh in the battery from 6 PM until 10 PM for emergency services.",
            "The evening transformer limit is 180 kWh of grid import from 7 PM until 9 PM.",
        ],
        "hours": H(
            [100,95,90,90,95,105,120,135,150,165,175,185,190,185,175,170,180,195,210,225,215,185,145,115],
            [0,0,0,0,0,0,5,20,50,90,135,170,190,180,145,95,45,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,14,15,16,16,15,14,15,18,23,29,32,30,21,11,7],
        ),
        "battery": {"capacity_kwh": 250, "initial_energy_kwh": 150, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 60, "max_discharge_kwh_per_hour": 60},
        "types": ["minimum_battery_reserve", "max_grid_window"],
        "cost": 38550,
    },
    {
        "id": "SAMPLE-08",
        "notes": [
            "Battery charging is disabled from 11 AM until 1 PM while technicians inspect the charger.",
            "Do not discharge the battery from 5 PM until 7 PM during relay testing.",
        ],
        "hours": H(
            [90,85,80,80,85,95,110,125,140,155,165,175,180,175,165,160,170,190,210,220,210,180,145,115],
            [0,0,0,0,0,0,0,15,40,80,120,155,175,165,130,85,40,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,14,15,16,15,14,13,14,18,24,30,31,28,19,10,7],
        ),
        "battery": {"capacity_kwh": 210, "initial_energy_kwh": 105, "minimum_energy_kwh": 35, "max_charge_kwh_per_hour": 50, "max_discharge_kwh_per_hour": 50},
        "types": ["no_charge_window", "no_discharge_window"],
        "cost": 37665,
    },
    {
        "id": "SAMPLE-09",
        "notes": [
            "Expect an 80% reduction in rooftop solar between 11 AM and 2 PM because of inverter work.",
            "The student affairs office will publish club notices tomorrow.",
        ],
        "hours": H(
            [90,85,80,80,85,95,105,120,135,150,165,175,180,175,165,160,170,185,200,210,200,170,135,105],
            [0,0,0,0,0,0,5,25,65,120,180,230,260,240,190,120,55,10,0,0,0,0,0,0],
            [6,6,5,5,5,6,8,10,12,13,14,15,15,14,13,14,18,22,27,29,26,18,10,7],
        ),
        "battery": {"capacity_kwh": 240, "initial_energy_kwh": 120, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 60, "max_discharge_kwh_per_hour": 60},
        "types": ["solar_reduction", "no_op"],
        "cost": 34873,
    },
    {
        "id": "SAMPLE-10",
        "notes": [
            "The data center requires at least 80 kWh to remain in the battery from 6 PM until 10 PM.",
            "Grid intake must stay at or below 190 kWh from 7 PM until 10 PM while the substation is constrained.",
            "A seminar room booking was moved to next week.",
        ],
        "hours": H(
            [105,100,95,95,100,110,125,140,155,170,180,190,195,190,180,175,185,200,215,230,220,190,150,120],
            [0,0,0,0,0,0,5,20,50,90,130,165,185,175,140,90,40,10,0,0,0,0,0,0],
            [7,6,6,5,5,6,8,10,12,14,16,17,16,15,14,15,19,24,30,34,31,21,11,8],
        ),
        "battery": {"capacity_kwh": 260, "initial_energy_kwh": 140, "minimum_energy_kwh": 40, "max_charge_kwh_per_hour": 65, "max_discharge_kwh_per_hour": 65},
        "types": ["minimum_battery_reserve", "max_grid_window", "no_op"],
        "cost": 41620,
    },
]


def main() -> None:
    failed = 0
    for c in CASES:
        payload = {
            "scenario_id": c["id"],
            "operator_notes": c["notes"],
            "hours": c["hours"],
            "battery": c["battery"],
        }
        r = client.post("/optimize-energy", json=payload)
        if r.status_code != 200:
            print(f"FAIL {c['id']} HTTP {r.status_code}: {r.text}")
            failed += 1
            continue
        data = r.json()
        types = [d["directive_type"] for d in data["directive_interpretation"]]
        if types != c["types"]:
            print(f"FAIL {c['id']} types {types} != {c['types']}")
            failed += 1
            continue
        if data["total_cost_bdt"] > c["cost"] + 0.05:
            print(f"FAIL {c['id']} cost {data['total_cost_bdt']} > {c['cost']}")
            failed += 1
            continue
        print(f"OK {c['id']}: cost={data['total_cost_bdt']} (ref {c['cost']})")
    if failed:
        raise SystemExit(f"{failed} case(s) failed")
    print("All 10 embedded sample cases passed.")


if __name__ == "__main__":
    main()
