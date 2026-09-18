"""Unit tests for directive compiler."""

from app.core.constants import DirectiveType
from app.directives.compiler import compile_directives
from app.schemas.directives import (
    DirectiveInterpretation,
    MaxGridAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    ReserveAdjustment,
    SolarReductionAdjustment,
)
from app.schemas.request import BatteryConfig, HourEntry, OptimizeEnergyRequest


def test_compiler_single_solar_reduction():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=100.0, tariff_bdt_per_kwh=5.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="TEST-COMPILER",
        operator_notes=["Solar cut"],
        hours=hours,
        battery=battery,
    )
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=SolarReductionAdjustment(hours=[12, 13], factor=0.25),
            explanation="Cleaning.",
        )
    ]

    compiled = compile_directives(req, directives)

    assert compiled.effective_solar[11] == 100.0
    assert compiled.effective_solar[12] == 25.0
    assert compiled.effective_solar[13] == 25.0
    assert compiled.effective_solar[14] == 100.0
    # Original request remains untouched
    assert req.hours[12].solar_kwh == 100.0


def test_compiler_combined_charge_discharge_restrictions():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="TEST-COMPILER-2",
        operator_notes=["No charge", "No discharge"],
        hours=hours,
        battery=battery,
    )
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment=NoChargeAdjustment(hours=[14, 15]),
            explanation="No charge.",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
            structured_adjustment=NoDischargeAdjustment(hours=[15, 16]),
            explanation="No discharge.",
        ),
    ]

    compiled = compile_directives(req, directives)

    # Hour 14: no charge only
    assert compiled.no_charge[14] is True
    assert compiled.no_discharge[14] is False

    # Hour 15: both no charge and no discharge
    assert compiled.no_charge[15] is True
    assert compiled.no_discharge[15] is True

    # Hour 16: no discharge only
    assert compiled.no_charge[16] is False
    assert compiled.no_discharge[16] is True


def test_compiler_multiple_reserves_max_rule():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=5.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="TEST-COMPILER-3",
        operator_notes=["Reserve 80", "Reserve 120"],
        hours=hours,
        battery=battery,
    )
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=ReserveAdjustment(hours=[18, 19], minimum_energy_kwh=80.0),
            explanation="Reserve 80.",
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=ReserveAdjustment(hours=[19, 20], minimum_energy_kwh=120.0),
            explanation="Reserve 120.",
        ),
    ]

    compiled = compile_directives(req, directives)

    assert compiled.minimum_battery_required[17] == 40.0  # Base
    assert compiled.minimum_battery_required[18] == 80.0  # First directive
    assert compiled.minimum_battery_required[19] == 120.0 # max(80, 120)
    assert compiled.minimum_battery_required[20] == 120.0 # Second directive
    assert compiled.minimum_battery_required[21] == 40.0  # Base
