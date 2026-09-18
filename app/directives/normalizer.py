"""Normalization utilities for structured directive outputs."""

from app.core.constants import DirectiveType
from app.schemas.directives import (
    DirectiveInterpretation,
    SolarReductionAdjustment,
    ReserveAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    MaxGridAdjustment,
)


def normalize_directive(
    interp: DirectiveInterpretation, battery_capacity_kwh: float
) -> DirectiveInterpretation:
    """Normalize hours order and ensure canonical numeric representations."""
    if interp.directive_type == DirectiveType.NO_OP or interp.structured_adjustment is None:
        return interp

    adj = interp.structured_adjustment
    # Canonicalize hours to sorted unique list
    sorted_hours = sorted(list(dict.fromkeys(adj.hours)))

    if len(sorted_hours) == 0:
        return DirectiveInterpretation(
            note_index=interp.note_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation=interp.explanation or "No valid hours specified; treated as no_op.",
        )

    if isinstance(adj, SolarReductionAdjustment):
        normalized_adj = SolarReductionAdjustment(hours=sorted_hours, factor=round(adj.factor, 6))
    elif isinstance(adj, ReserveAdjustment):
        normalized_adj = ReserveAdjustment(
            hours=sorted_hours, minimum_energy_kwh=round(adj.minimum_energy_kwh, 6)
        )
    elif isinstance(adj, NoChargeAdjustment):
        normalized_adj = NoChargeAdjustment(hours=sorted_hours)
    elif isinstance(adj, NoDischargeAdjustment):
        normalized_adj = NoDischargeAdjustment(hours=sorted_hours)
    elif isinstance(adj, MaxGridAdjustment):
        normalized_adj = MaxGridAdjustment(
            hours=sorted_hours, max_grid_kwh=round(adj.max_grid_kwh, 6)
        )
    else:
        normalized_adj = adj

    return DirectiveInterpretation(
        note_index=interp.note_index,
        applies=interp.applies,
        directive_type=interp.directive_type,
        structured_adjustment=normalized_adj,
        explanation=interp.explanation,
    )
