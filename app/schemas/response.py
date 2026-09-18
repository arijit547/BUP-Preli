"""Response schemas for POST /optimize-energy and GET /health."""

from pydantic import BaseModel, Field
from app.core.constants import BatteryAction
from app.schemas.directives import DirectiveInterpretation


class HealthResponse(BaseModel):
    """Readiness response for GET /health."""
    status: str = "ok"


class HourlyPlanEntry(BaseModel):
    """Single hour energy dispatch plan."""
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0 to 23)")
    grid_kwh: float = Field(..., ge=0.0, description="Grid electricity imported in kWh")
    solar_used_kwh: float = Field(..., ge=0.0, description="Solar electricity utilized in kWh")
    battery_action: BatteryAction = Field(..., description="Action taken: charge, discharge, or idle")
    battery_kwh: float = Field(..., ge=0.0, description="Magnitude of battery charge/discharge in kWh (0 if idle)")
    battery_energy_after_kwh: float = Field(..., ge=0.0, description="State of energy in battery after hour in kWh")


class OptimizeEnergyResponse(BaseModel):
    """Complete response payload for POST /optimize-energy."""
    scenario_id: str = Field(..., description="Scenario identifier matching the request")
    directive_interpretation: list[DirectiveInterpretation] = Field(..., description="Interpreted operator directives")
    hourly_plan: list[HourlyPlanEntry] = Field(..., min_length=24, max_length=24, description="24-hour dispatch schedule")
    total_grid_kwh: float = Field(..., ge=0.0, description="Total grid energy imported across all 24 hours")
    total_cost_bdt: float = Field(..., description="Total cost of grid electricity in BDT")
    peak_grid_kwh: float = Field(..., ge=0.0, description="Peak hourly grid import in kWh")
    plan_summary: str = Field(..., min_length=1, description="Concise strategy summary")
