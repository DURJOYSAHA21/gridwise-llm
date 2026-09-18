from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.guardrails import apply_effective_solar, collect_constraints
from app.llm_interpreter import interpret_notes
from app.optimizer import optimize_schedule
from app.schemas import OptimizeRequest, OptimizeResponse
from app.validator import replay_validate

load_dotenv()

app = FastAPI(title="GridWise LLM Energy Optimizer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "GridWise LLM Energy Optimizer",
        "status": "ok",
        "health": "/health",
        "optimize": "POST /optimize-energy",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy(req: OptimizeRequest) -> OptimizeResponse:
    try:
        hours_sorted = sorted(req.hours, key=lambda h: h.hour)
        demand = [h.demand_kwh for h in hours_sorted]
        solar = [h.solar_kwh for h in hours_sorted]
        tariff = [h.tariff_bdt_per_kwh for h in hours_sorted]
        bat = req.battery

        directives = interpret_notes(req.operator_notes, bat.capacity_kwh)
        effective_solar = apply_effective_solar(solar, directives)
        constraints = collect_constraints(directives, bat.minimum_energy_kwh)

        result = optimize_schedule(
            demand=demand,
            effective_solar=effective_solar,
            tariff=tariff,
            capacity=bat.capacity_kwh,
            initial=bat.initial_energy_kwh,
            base_minimum=bat.minimum_energy_kwh,
            max_charge=bat.max_charge_kwh_per_hour,
            max_discharge=bat.max_discharge_kwh_per_hour,
            min_energy=constraints["min_energy"],
            no_charge=constraints["no_charge"],
            no_discharge=constraints["no_discharge"],
            max_grid=constraints["max_grid"],
        )

        replay_validate(
            demand=demand,
            effective_solar=effective_solar,
            tariff=tariff,
            capacity=bat.capacity_kwh,
            initial=bat.initial_energy_kwh,
            min_energy=constraints["min_energy"],
            max_charge=bat.max_charge_kwh_per_hour,
            max_discharge=bat.max_discharge_kwh_per_hour,
            no_charge=constraints["no_charge"],
            no_discharge=constraints["no_discharge"],
            max_grid=constraints["max_grid"],
            plan=result["hourly_plan"],
            total_grid_kwh=result["total_grid_kwh"],
            total_cost_bdt=result["total_cost_bdt"],
            peak_grid_kwh=result["peak_grid_kwh"],
        )

        summary = _plan_summary(directives, result)
        return OptimizeResponse(
            scenario_id=req.scenario_id,
            directive_interpretation=directives,
            hourly_plan=result["hourly_plan"],
            total_grid_kwh=result["total_grid_kwh"],
            total_cost_bdt=result["total_cost_bdt"],
            peak_grid_kwh=result["peak_grid_kwh"],
            plan_summary=summary,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal optimization error") from e


def _plan_summary(directives: list[dict[str, Any]], result: dict[str, Any]) -> str:
    applied = [d["directive_type"] for d in directives if d.get("applies")]
    ignored = sum(1 for d in directives if d.get("directive_type") == "no_op")
    parts = []
    if applied:
        parts.append("Applied directives: " + ", ".join(applied) + ".")
    if ignored:
        parts.append(f"Ignored {ignored} unrelated note(s).")
    parts.append(
        f"Optimized 24h schedule with total grid {result['total_grid_kwh']:.2f} kWh "
        f"at cost {result['total_cost_bdt']:.2f} BDT; peak import {result['peak_grid_kwh']:.2f} kWh."
    )
    return " ".join(parts)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
