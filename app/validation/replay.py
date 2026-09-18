"""Independent deterministic replay validator for 24-hour campus energy plans."""

from app.core.constants import (
    BatteryAction,
    HOURS_PER_DAY,
    JUDGE_TOLERANCE,
)
from app.directives.compiler import CompiledConstraints
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import HourlyPlanEntry


class ReplayValidationError(Exception):
    """Raised when an hourly plan fails deterministic physical replay."""
    pass


def replay_and_validate_schedule(
    request: OptimizeEnergyRequest,
    constraints: CompiledConstraints,
    plan: list[HourlyPlanEntry],
    tolerance: float = JUDGE_TOLERANCE,
) -> None:
    """Independently simulate and verify the 24-hour energy plan against all physical laws.

    Performs 12 distinct checks completely decoupled from the LP solver implementation.
    """
    # 1. Plan completeness and ordering
    if len(plan) != HOURS_PER_DAY:
        raise ReplayValidationError(
            f"Plan contains {len(plan)} entries; expected exactly {HOURS_PER_DAY}."
        )

    current_battery_energy = request.battery.initial_energy_kwh

    for h, entry in enumerate(plan):
        if entry.hour != h:
            raise ReplayValidationError(
                f"Plan entry at index {h} has hour {entry.hour}; expected {h}."
            )

        demand = request.hours[h].demand_kwh
        effective_solar = constraints.effective_solar[h]
        max_grid = constraints.max_grid[h]
        min_reserve = constraints.minimum_battery_required[h]

        # 2. Grid electricity validation
        if entry.grid_kwh < -tolerance:
            raise ReplayValidationError(
                f"Hour {h}: grid_kwh ({entry.grid_kwh}) cannot be negative (no grid export)."
            )
        if max_grid is not None and entry.grid_kwh > (max_grid + tolerance):
            raise ReplayValidationError(
                f"Hour {h}: grid_kwh ({entry.grid_kwh}) violates max_grid cap ({max_grid} kWh)."
            )

        # 3. Solar electricity validation
        if entry.solar_used_kwh < -tolerance:
            raise ReplayValidationError(
                f"Hour {h}: solar_used_kwh ({entry.solar_used_kwh}) cannot be negative."
            )
        if entry.solar_used_kwh > (effective_solar + tolerance):
            raise ReplayValidationError(
                f"Hour {h}: solar_used_kwh ({entry.solar_used_kwh}) exceeds effective solar ({effective_solar} kWh)."
            )

        # 4. Battery action and magnitude consistency
        if entry.battery_action == BatteryAction.IDLE:
            if abs(entry.battery_kwh) > tolerance:
                raise ReplayValidationError(
                    f"Hour {h}: battery is idle but battery_kwh is {entry.battery_kwh} (must be 0)."
                )
        elif entry.battery_action == BatteryAction.CHARGE:
            if entry.battery_kwh < -tolerance:
                raise ReplayValidationError(
                    f"Hour {h}: battery charge magnitude ({entry.battery_kwh}) must be non-negative."
                )
            if entry.battery_kwh > (request.battery.max_charge_kwh_per_hour + tolerance):
                raise ReplayValidationError(
                    f"Hour {h}: charge amount ({entry.battery_kwh}) exceeds max_charge rate ({request.battery.max_charge_kwh_per_hour})."
                )
            if constraints.no_charge[h] and entry.battery_kwh > tolerance:
                raise ReplayValidationError(
                    f"Hour {h}: battery charged during an active no_charge_window."
                )

        elif entry.battery_action == BatteryAction.DISCHARGE:
            if entry.battery_kwh < -tolerance:
                raise ReplayValidationError(
                    f"Hour {h}: battery discharge magnitude ({entry.battery_kwh}) must be non-negative."
                )
            if entry.battery_kwh > (request.battery.max_discharge_kwh_per_hour + tolerance):
                raise ReplayValidationError(
                    f"Hour {h}: discharge amount ({entry.battery_kwh}) exceeds max_discharge rate ({request.battery.max_discharge_kwh_per_hour})."
                )
            if constraints.no_discharge[h] and entry.battery_kwh > tolerance:
                raise ReplayValidationError(
                    f"Hour {h}: battery discharged during an active no_discharge_window."
                )

        # 5. State of energy transition
        if entry.battery_action == BatteryAction.CHARGE:
            expected_after = current_battery_energy + entry.battery_kwh
            discharge_kwh = 0.0
            charge_kwh = entry.battery_kwh
        elif entry.battery_action == BatteryAction.DISCHARGE:
            expected_after = current_battery_energy - entry.battery_kwh
            discharge_kwh = entry.battery_kwh
            charge_kwh = 0.0
        else:
            expected_after = current_battery_energy
            discharge_kwh = 0.0
            charge_kwh = 0.0

        if abs(entry.battery_energy_after_kwh - expected_after) > tolerance:
            raise ReplayValidationError(
                f"Hour {h}: battery transition error. Expected {expected_after:.3f} kWh after {entry.battery_action.value}, "
                f"got {entry.battery_energy_after_kwh:.3f} kWh (starting from {current_battery_energy:.3f} kWh)."
            )

        # 6. Battery capacity and reserve bounds
        if entry.battery_energy_after_kwh > (request.battery.capacity_kwh + tolerance):
            raise ReplayValidationError(
                f"Hour {h}: battery energy after ({entry.battery_energy_after_kwh}) exceeds capacity ({request.battery.capacity_kwh})."
            )
        if entry.battery_energy_after_kwh < (min_reserve - tolerance):
            raise ReplayValidationError(
                f"Hour {h}: battery energy after ({entry.battery_energy_after_kwh}) falls below required reserve ({min_reserve})."
            )

        # 7. Hourly energy balance equation:
        # grid + solar_used + battery_discharge = demand + battery_charge
        lhs = entry.grid_kwh + entry.solar_used_kwh + discharge_kwh
        rhs = demand + charge_kwh
        if abs(lhs - rhs) > tolerance:
            raise ReplayValidationError(
                f"Hour {h}: energy balance violation. Supply (grid {entry.grid_kwh} + solar {entry.solar_used_kwh} + discharge {discharge_kwh} = {lhs:.3f}) "
                f"!= Demand & Storage (demand {demand} + charge {charge_kwh} = {rhs:.3f}). Imbalance: {abs(lhs - rhs):.4f} kWh."
            )

        # Update battery state for next hour
        current_battery_energy = entry.battery_energy_after_kwh

    # 8. End-of-day battery neutrality: final state must match starting state
    initial_energy = request.battery.initial_energy_kwh
    final_energy = plan[-1].battery_energy_after_kwh
    if abs(final_energy - initial_energy) > tolerance:
        raise ReplayValidationError(
            f"End-of-day neutrality violation. Final battery energy ({final_energy:.3f} kWh) "
            f"must equal initial energy ({initial_energy:.3f} kWh). Difference: {abs(final_energy - initial_energy):.4f} kWh."
        )
