"""Directive compiler that transforms validated directives into mathematical constraints."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional
from app.core.constants import DirectiveType, HOURS_PER_DAY
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.directives import (
    DirectiveInterpretation,
    SolarReductionAdjustment,
    ReserveAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    MaxGridAdjustment,
)


@dataclass(frozen=True)
class CompiledConstraints:
    """Compiled 24-hour mathematical constraint vectors for the LP optimizer."""
    effective_solar: list[float]
    minimum_battery_required: list[float]
    no_charge: list[bool]
    no_discharge: list[bool]
    max_grid: list[Optional[float]]


def compile_directives(
    request: OptimizeEnergyRequest, directives: list[DirectiveInterpretation]
) -> CompiledConstraints:
    """Compile validated directives and hourly data into immutable constraint vectors.

    Ensures the original request is never mutated.
    """
    # 1. Initialize baseline arrays from the immutable request
    effective_solar = [h.solar_kwh for h in request.hours]
    minimum_battery_required = [request.battery.minimum_energy_kwh for _ in range(HOURS_PER_DAY)]
    no_charge = [False for _ in range(HOURS_PER_DAY)]
    no_discharge = [False for _ in range(HOURS_PER_DAY)]
    max_grid: list[Optional[float]] = [None for _ in range(HOURS_PER_DAY)]

    # 2. Sequentially apply validated directives
    for interp in directives:
        if not interp.applies or interp.directive_type in (DirectiveType.NO_OP, DirectiveType.COST_OPTIMIZATION):
            continue

        adj = interp.structured_adjustment
        if adj is None or adj.__class__.__name__ == "EmptyAdjustment":
            continue

        if interp.directive_type == DirectiveType.SOLAR_REDUCTION:
            assert isinstance(adj, SolarReductionAdjustment)
            for h in adj.hours:
                # Apply reduction factor to available solar
                effective_solar[h] = effective_solar[h] * adj.factor

        elif interp.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
            assert isinstance(adj, ReserveAdjustment)
            for h in adj.hours:
                # Active reserve is the maximum of baseline and all applicable directives
                minimum_battery_required[h] = max(
                    minimum_battery_required[h], adj.minimum_energy_kwh
                )

        elif interp.directive_type == DirectiveType.NO_CHARGE_WINDOW:
            assert isinstance(adj, NoChargeAdjustment)
            for h in adj.hours:
                no_charge[h] = True

        elif interp.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
            assert isinstance(adj, NoDischargeAdjustment)
            for h in adj.hours:
                no_discharge[h] = True

        elif interp.directive_type == DirectiveType.MAX_GRID_WINDOW:
            assert isinstance(adj, MaxGridAdjustment)
            for h in adj.hours:
                if max_grid[h] is None:
                    max_grid[h] = adj.max_grid_kwh
                else:
                    max_grid[h] = min(max_grid[h], adj.max_grid_kwh)

    return CompiledConstraints(
        effective_solar=effective_solar,
        minimum_battery_required=minimum_battery_required,
        no_charge=no_charge,
        no_discharge=no_discharge,
        max_grid=max_grid,
    )
