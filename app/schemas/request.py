"""Request schemas for POST /optimize-energy."""

import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HourEntry(BaseModel):
    """Single hour energy parameters."""
    model_config = ConfigDict(frozen=True)

    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0 to 23)")
    demand_kwh: float = Field(..., description="Campus electrical demand in kWh")
    solar_kwh: float = Field(..., description="Base forecast solar generation in kWh")
    tariff_bdt_per_kwh: float = Field(..., description="Grid electricity tariff in BDT/kWh")

    @field_validator("demand_kwh", "solar_kwh")
    @classmethod
    def check_non_negative_finite(cls, v: float, info) -> float:
        if not math.isfinite(v):
            raise ValueError(f"{info.field_name} must be a finite number.")
        if v < 0.0:
            raise ValueError(f"{info.field_name} cannot be negative.")
        return float(v)

    @field_validator("tariff_bdt_per_kwh")
    @classmethod
    def check_tariff_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("tariff_bdt_per_kwh must be a finite number.")
        return float(v)


class BatteryConfig(BaseModel):
    """Battery system parameters."""
    model_config = ConfigDict(frozen=True)

    capacity_kwh: float = Field(..., description="Maximum storage capacity in kWh")
    initial_energy_kwh: float = Field(..., description="Starting battery energy at hour 0 in kWh")
    minimum_energy_kwh: float = Field(..., description="Minimum allowable reserve energy in kWh")
    max_charge_kwh_per_hour: float = Field(..., description="Maximum hourly charge rate in kWh")
    max_discharge_kwh_per_hour: float = Field(..., description="Maximum hourly discharge rate in kWh")

    @field_validator("capacity_kwh")
    @classmethod
    def check_capacity(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0.0:
            raise ValueError("capacity_kwh must be a finite positive number.")
        return float(v)

    @field_validator("initial_energy_kwh", "minimum_energy_kwh", "max_charge_kwh_per_hour", "max_discharge_kwh_per_hour")
    @classmethod
    def check_non_negative(cls, v: float, info) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError(f"{info.field_name} must be a finite non-negative number.")
        return float(v)

    @model_validator(mode="after")
    def check_battery_consistency(self) -> "BatteryConfig":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})."
            )
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"minimum_energy_kwh ({self.minimum_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})."
            )
        return self


class OptimizeEnergyRequest(BaseModel):
    """Top-level request body for POST /optimize-energy."""
    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(..., min_length=1, description="Unique scenario identifier")
    operator_notes: list[str] = Field(..., min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: list[HourEntry] = Field(..., min_length=24, max_length=24, description="Exactly 24 hourly records")
    battery: BatteryConfig

    @field_validator("scenario_id")
    @classmethod
    def check_scenario_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("scenario_id cannot be empty or whitespace.")
        return s

    @field_validator("operator_notes")
    @classmethod
    def check_operator_notes(cls, v: list[str]) -> list[str]:
        if not (1 <= len(v) <= 3):
            raise ValueError("operator_notes must contain between 1 and 3 items.")
        cleaned = []
        for i, note in enumerate(v):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"operator_note[{i}] must be a non-empty string.")
            cleaned.append(note.strip())
        return cleaned

    @field_validator("hours")
    @classmethod
    def check_hours_completeness(cls, v: list[HourEntry]) -> list[HourEntry]:
        if len(v) != 24:
            raise ValueError(f"hours array must contain exactly 24 entries, got {len(v)}.")
        hours_seen = [h.hour for h in v]
        if hours_seen != list(range(24)):
            raise ValueError(
                f"hours array must contain hours 0 through 23 in exact order without duplicates. "
                f"Got: {hours_seen}"
            )
        return v
