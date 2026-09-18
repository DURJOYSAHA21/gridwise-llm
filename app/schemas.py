from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]

BatteryAction = Literal["charge", "discharge", "idle"]


class HourInput(BaseModel):
    hour: int
    demand_kwh: float
    solar_kwh: float
    tariff_bdt_per_kwh: float

    @field_validator("hour")
    @classmethod
    def hour_range(cls, v: int) -> int:
        if v < 0 or v > 23:
            raise ValueError("hour must be 0..23")
        return v


class BatteryInput(BaseModel):
    capacity_kwh: float
    initial_energy_kwh: float
    minimum_energy_kwh: float
    max_charge_kwh_per_hour: float
    max_discharge_kwh_per_hour: float


class OptimizeRequest(BaseModel):
    scenario_id: str
    operator_notes: list[str] = Field(min_length=1, max_length=3)
    hours: list[HourInput]
    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def notes_nonempty(cls, v: list[str]) -> list[str]:
        if not all(isinstance(n, str) and n.strip() for n in v):
            raise ValueError("operator_notes must be non-empty strings")
        return v

    @model_validator(mode="after")
    def validate_hours(self) -> OptimizeRequest:
        if len(self.hours) != 24:
            raise ValueError("hours must contain exactly 24 entries")
        seen = sorted(h.hour for h in self.hours)
        if seen != list(range(24)):
            raise ValueError("hours must cover unique hours 0..23")
        return self


class StructuredAdjustment(BaseModel):
    hours: list[int]
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None

    model_config = {"extra": "forbid"}


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[dict[str, Any]] = None
    explanation: str


class HourlyPlanEntry(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: BatteryAction
    battery_kwh: float
    battery_energy_after_kwh: float


class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
