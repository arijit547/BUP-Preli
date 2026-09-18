"""Deterministic guardrails validating LLM output before optimization."""

import math
from app.core.constants import DirectiveType
from app.schemas.request import BatteryConfig
from app.schemas.directives import (
    DirectiveInterpretation,
    SolarReductionAdjustment,
    ReserveAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    MaxGridAdjustment,
)


class DirectiveValidationError(Exception):
    """Raised when an interpreted directive violates security or validation guardrails."""
    pass


def validate_directive_interpretations(
    interpretations: list[DirectiveInterpretation],
    expected_note_count: int,
    battery: BatteryConfig,
) -> list[DirectiveInterpretation]:
    """Strict deterministic validation of the LLM interpretation output.

    Guarantees:
    1. Exact 1-to-1 mapping with note indices 0..N-1 in exact ascending order.
    2. Only the six official directive types are accepted.
    3. applies == False if and only if directive_type == 'no_op'.
    4. structured_adjustment matches the exact required class for the directive type.
    5. Hours are unique integers within [0, 23] in strictly ascending order.
    6. All numeric parameters are finite and within strict physical bounds.
    """
    if len(interpretations) != expected_note_count:
        raise DirectiveValidationError(
            f"Expected {expected_note_count} directive interpretations, got {len(interpretations)}."
        )

    for i, interp in enumerate(interpretations):
        # 1. Note mapping and order
        if interp.note_index != i:
            raise DirectiveValidationError(
                f"Directive interpretation at index {i} has note_index {interp.note_index}; expected {i}."
            )

        dtype = interp.directive_type

        # 2. applies semantics
        if dtype == DirectiveType.NO_OP:
            if interp.applies is not False:
                raise DirectiveValidationError(
                    f"Directive at note_index {i} has type 'no_op' but applies is True."
                )
            if interp.structured_adjustment is not None:
                raise DirectiveValidationError(
                    f"Directive at note_index {i} has type 'no_op' but non-null structured_adjustment."
                )
            continue

        # Non-no_op directives
        if interp.applies is not True:
            raise DirectiveValidationError(
                f"Directive at note_index {i} has type '{dtype.value}' but applies is False."
            )
        if interp.structured_adjustment is None:
            raise DirectiveValidationError(
                f"Directive at note_index {i} has type '{dtype.value}' but structured_adjustment is null."
            )

        adj = interp.structured_adjustment

        # 3. Hours array validation
        if not hasattr(adj, "hours") or not isinstance(adj.hours, list):
            raise DirectiveValidationError(
                f"Directive at note_index {i} is missing a valid 'hours' list."
            )
        if len(adj.hours) == 0:
            raise DirectiveValidationError(
                f"Directive at note_index {i} has an empty 'hours' list."
            )
        for h in adj.hours:
            if not isinstance(h, int) or isinstance(h, bool):
                raise DirectiveValidationError(
                    f"Directive at note_index {i} contains non-integer hour: {h}."
                )
            if h < 0 or h > 23:
                raise DirectiveValidationError(
                    f"Directive at note_index {i} contains out-of-range hour: {h}."
                )
        if len(adj.hours) != len(set(adj.hours)):
            raise DirectiveValidationError(
                f"Directive at note_index {i} contains duplicate hours: {adj.hours}."
            )
        if adj.hours != sorted(adj.hours):
            raise DirectiveValidationError(
                f"Directive at note_index {i} hours must be in strictly ascending order: {adj.hours}."
            )

        # 4. Directive-specific numeric checks
        if dtype == DirectiveType.SOLAR_REDUCTION:
            if not isinstance(adj, SolarReductionAdjustment):
                raise DirectiveValidationError(
                    f"Directive type 'solar_reduction' must use SolarReductionAdjustment, got {type(adj).__name__}."
                )
            if not math.isfinite(adj.factor) or adj.factor < 0.0 or adj.factor > 1.0:
                raise DirectiveValidationError(
                    f"solar_reduction factor must be between 0.0 and 1.0, got {adj.factor}."
                )

        elif dtype == DirectiveType.MINIMUM_BATTERY_RESERVE:
            if not isinstance(adj, ReserveAdjustment):
                raise DirectiveValidationError(
                    f"Directive type 'minimum_battery_reserve' must use ReserveAdjustment, got {type(adj).__name__}."
                )
            if not math.isfinite(adj.minimum_energy_kwh) or adj.minimum_energy_kwh < 0.0:
                raise DirectiveValidationError(
                    f"minimum_battery_reserve must be finite and non-negative, got {adj.minimum_energy_kwh}."
                )
            if adj.minimum_energy_kwh > battery.capacity_kwh:
                raise DirectiveValidationError(
                    f"minimum_battery_reserve ({adj.minimum_energy_kwh} kWh) exceeds battery capacity ({battery.capacity_kwh} kWh)."
                )

        elif dtype == DirectiveType.NO_CHARGE_WINDOW:
            if not isinstance(adj, NoChargeAdjustment):
                raise DirectiveValidationError(
                    f"Directive type 'no_charge_window' must use NoChargeAdjustment, got {type(adj).__name__}."
                )

        elif dtype == DirectiveType.NO_DISCHARGE_WINDOW:
            if not isinstance(adj, NoDischargeAdjustment):
                raise DirectiveValidationError(
                    f"Directive type 'no_discharge_window' must use NoDischargeAdjustment, got {type(adj).__name__}."
                )

        elif dtype == DirectiveType.MAX_GRID_WINDOW:
            if not isinstance(adj, MaxGridAdjustment):
                raise DirectiveValidationError(
                    f"Directive type 'max_grid_window' must use MaxGridAdjustment, got {type(adj).__name__}."
                )
            if not math.isfinite(adj.max_grid_kwh) or adj.max_grid_kwh < 0.0:
                raise DirectiveValidationError(
                    f"max_grid_kwh must be finite and non-negative, got {adj.max_grid_kwh}."
                )

    return interpretations
