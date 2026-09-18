"""Maps raw solver output into canonical HourlyPlanEntry schema."""

from app.core.constants import (
    BatteryAction,
    FLOAT_CLEANUP_EPS,
    HOURS_PER_DAY,
    SIGN_EPS,
)
from app.directives.compiler import CompiledConstraints
from app.optimizer.model import SolverResult
from app.schemas.response import HourlyPlanEntry


def _clean_float(val: float) -> float:
    """Normalize tiny floating-point artifacts to exact zero."""
    if abs(val) < FLOAT_CLEANUP_EPS:
        return 0.0
    return float(val)


def map_solver_result_to_hourly_plan(
    result: SolverResult, constraints: CompiledConstraints
) -> list[HourlyPlanEntry]:
    """Transform continuous solver arrays into discrete hourly plan records."""
    plan: list[HourlyPlanEntry] = []

    for h in range(HOURS_PER_DAY):
        g_raw = _clean_float(result.grid_vector[h])
        s_raw = _clean_float(result.solar_vector[h])
        b_raw = _clean_float(result.battery_flow_vector[h])
        e_raw = _clean_float(result.battery_energy_vector[h])

        # Grid energy must be non-negative
        grid_kwh = max(0.0, g_raw)

        # Solar energy used is bounded by available effective solar
        effective_solar = max(0.0, constraints.effective_solar[h])
        solar_used_kwh = max(0.0, min(effective_solar, s_raw))

        # Classify battery action from signed flow
        if b_raw > SIGN_EPS:
            action = BatteryAction.CHARGE
            action_kwh = b_raw
        elif b_raw < -SIGN_EPS:
            action = BatteryAction.DISCHARGE
            action_kwh = abs(b_raw)
        else:
            action = BatteryAction.IDLE
            action_kwh = 0.0

        plan.append(
            HourlyPlanEntry(
                hour=h,
                grid_kwh=round(grid_kwh, 4),
                solar_used_kwh=round(solar_used_kwh, 4),
                battery_action=action,
                battery_kwh=round(action_kwh, 4),
                battery_energy_after_kwh=round(e_raw, 4),
            )
        )

    return plan
