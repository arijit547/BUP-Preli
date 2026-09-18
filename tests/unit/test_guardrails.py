"""Unit tests for deterministic guardrail validation."""

import pytest
from app.core.constants import DirectiveType
from app.directives.validator import DirectiveValidationError, validate_directive_interpretations
from app.schemas.directives import (
    DirectiveInterpretation,
    NoChargeAdjustment,
    ReserveAdjustment,
    SolarReductionAdjustment,
)
from app.schemas.request import BatteryConfig


@pytest.fixture
def battery():
    return BatteryConfig(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )


def test_guardrail_valid_directives(battery):
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=SolarReductionAdjustment(hours=[12, 13], factor=0.25),
            explanation="Cleaning.",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Unrelated.",
        ),
    ]
    res = validate_directive_interpretations(directives, expected_note_count=2, battery=battery)
    assert len(res) == 2


def test_guardrail_count_mismatch(battery):
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Unrelated.",
        )
    ]
    with pytest.raises(DirectiveValidationError, match="Expected 2"):
        validate_directive_interpretations(directives, expected_note_count=2, battery=battery)


def test_guardrail_index_order_mismatch(battery):
    directives = [
        DirectiveInterpretation(
            note_index=1,  # Out of order
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Unrelated.",
        ),
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Unrelated.",
        ),
    ]
    with pytest.raises(DirectiveValidationError, match="note_index"):
        validate_directive_interpretations(directives, expected_note_count=2, battery=battery)


def test_guardrail_reserve_exceeds_capacity(battery):
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=ReserveAdjustment(hours=[18, 19], minimum_energy_kwh=300.0), # > 200 capacity
            explanation="Too high reserve.",
        )
    ]
    with pytest.raises(DirectiveValidationError, match="exceeds battery capacity"):
        validate_directive_interpretations(directives, expected_note_count=1, battery=battery)
