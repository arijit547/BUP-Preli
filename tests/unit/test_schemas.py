"""Unit tests for Pydantic v2 schemas and validation bounds."""

import pytest
from pydantic import ValidationError
from app.core.constants import DirectiveType
from app.schemas.directives import (
    DirectiveInterpretation,
    NoChargeAdjustment,
    ReserveAdjustment,
    SolarReductionAdjustment,
)
from app.schemas.request import BatteryConfig, HourEntry, OptimizeEnergyRequest


def test_valid_hour_entry():
    entry = HourEntry(hour=5, demand_kwh=100.0, solar_kwh=10.0, tariff_bdt_per_kwh=8.5)
    assert entry.hour == 5
    assert entry.demand_kwh == 100.0
    assert entry.solar_kwh == 10.0
    assert entry.tariff_bdt_per_kwh == 8.5


def test_invalid_hour_entry_negative():
    with pytest.raises(ValidationError):
        HourEntry(hour=5, demand_kwh=-10.0, solar_kwh=10.0, tariff_bdt_per_kwh=8.5)
    with pytest.raises(ValidationError):
        HourEntry(hour=5, demand_kwh=10.0, solar_kwh=-5.0, tariff_bdt_per_kwh=8.5)


def test_invalid_hour_range():
    with pytest.raises(ValidationError):
        HourEntry(hour=24, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=8.5)
    with pytest.raises(ValidationError):
        HourEntry(hour=-1, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=8.5)


def test_battery_config_valid():
    b = BatteryConfig(
        capacity_kwh=500.0,
        initial_energy_kwh=200.0,
        minimum_energy_kwh=50.0,
        max_charge_kwh_per_hour=100.0,
        max_discharge_kwh_per_hour=100.0,
    )
    assert b.capacity_kwh == 500.0


def test_battery_config_invalid_bounds():
    # Capacity must be > 0
    with pytest.raises(ValidationError):
        BatteryConfig(
            capacity_kwh=0.0,
            initial_energy_kwh=0.0,
            minimum_energy_kwh=0.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
        )

    # Initial energy > capacity
    with pytest.raises(ValidationError):
        BatteryConfig(
            capacity_kwh=200.0,
            initial_energy_kwh=250.0,
            minimum_energy_kwh=50.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
        )

    # Minimum energy > capacity
    with pytest.raises(ValidationError):
        BatteryConfig(
            capacity_kwh=200.0,
            initial_energy_kwh=100.0,
            minimum_energy_kwh=250.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
        )


def test_request_missing_hour():
    hours = [
        HourEntry(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0)
        for h in range(23) # Only 23 entries
    ]
    battery = BatteryConfig(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="SCENARIO-ERR",
            operator_notes=["Note 1"],
            hours=hours,
            battery=battery,
        )


def test_request_duplicate_hour():
    hours = [
        HourEntry(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0)
        for h in range(23)
    ]
    hours.append(HourEntry(hour=22, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0)) # Duplicate hour 22
    battery = BatteryConfig(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest(
            scenario_id="SCENARIO-ERR",
            operator_notes=["Note 1"],
            hours=hours,
            battery=battery,
        )


def test_directive_coupling_no_op():
    # Valid no_op
    d = DirectiveInterpretation(
        note_index=0,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation="No effect.",
    )
    assert d.applies is False

    # Invalid: applies True with no_op
    with pytest.raises(ValidationError):
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Invalid.",
        )

    # Invalid: non-null adjustment with no_op
    with pytest.raises(ValidationError):
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=NoChargeAdjustment(hours=[1, 2]),
            explanation="Invalid.",
        )


def test_directive_coupling_mismatch():
    # Directive type solar_reduction with NoChargeAdjustment
    with pytest.raises(ValidationError):
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=NoChargeAdjustment(hours=[12, 13]),
            explanation="Mismatch.",
        )


def test_directive_adjustment_hours_validation():
    # Unsorted hours
    with pytest.raises(ValidationError):
        NoChargeAdjustment(hours=[15, 14])

    # Duplicate hours
    with pytest.raises(ValidationError):
        NoChargeAdjustment(hours=[14, 14])

    # Out of bounds hour
    with pytest.raises(ValidationError):
        NoChargeAdjustment(hours=[24])

    # Negative solar factor
    with pytest.raises(ValidationError):
        SolarReductionAdjustment(hours=[12, 13], factor=-0.1)

    # Solar factor > 1
    with pytest.raises(ValidationError):
        SolarReductionAdjustment(hours=[12, 13], factor=1.5)
