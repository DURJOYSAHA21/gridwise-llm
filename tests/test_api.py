from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _hours():
    # SAMPLE-01 profile (abbreviated construction matching public pack)
    demand = [90,85,80,80,85,95,110,130,150,165,175,180,185,180,170,165,170,185,205,215,205,175,135,105]
    solar = [0,0,0,0,0,0,5,20,50,90,130,160,180,170,140,90,45,10,0,0,0,0,0,0]
    tariff = [6,6,5,5,5,6,8,10,12,14,16,16,15,14,13,14,18,22,28,30,26,18,10,7]
    return [
        {"hour": h, "demand_kwh": demand[h], "solar_kwh": solar[h], "tariff_bdt_per_kwh": tariff[h]}
        for h in range(24)
    ]


def test_optimize_sample01_like():
    payload = {
        "scenario_id": "SAMPLE-01",
        "operator_notes": [
            "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
            "The sports office moved next month's registration deadline.",
        ],
        "hours": _hours(),
        "battery": {
            "capacity_kwh": 220,
            "initial_energy_kwh": 110,
            "minimum_energy_kwh": 40,
            "max_charge_kwh_per_hour": 50,
            "max_discharge_kwh_per_hour": 50,
        },
    }
    r = client.post("/optimize-energy", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scenario_id"] == "SAMPLE-01"
    assert len(data["directive_interpretation"]) == 2
    d0, d1 = data["directive_interpretation"]
    assert d0["directive_type"] == "solar_reduction"
    assert d0["structured_adjustment"]["hours"] == [12, 13]
    assert abs(d0["structured_adjustment"]["factor"] - 0.25) < 1e-9
    assert d1["directive_type"] == "no_op"
    assert len(data["hourly_plan"]) == 24
    assert abs(data["hourly_plan"][23]["battery_energy_after_kwh"] - 110) <= 0.01
    # Reference optimal cost from public pack
    assert data["total_cost_bdt"] <= 38365 + 0.05
    print("OK API SAMPLE-01-like", data["total_cost_bdt"], data["total_grid_kwh"])


if __name__ == "__main__":
    test_health()
    print("OK health")
    test_optimize_sample01_like()
