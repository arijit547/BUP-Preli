"""Unit tests for HiGHS linear programming optimizer and result mapper."""

from app.core.constants import BatteryAction, JUDGE_TOLERANCE
from app.directives.compiler import compile_directives
from app.optimizer.highs_solver import solve_campus_energy_lp
from app.optimizer.result_mapper import map_solver_result_to_hourly_plan
from app.schemas.directives import (
    DirectiveInterpretation,
    MaxGridAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    ReserveAdjustment,
)
from app.core.constants import DirectiveType
from app.schemas.request import BatteryConfig, HourEntry, OptimizeEnergyRequest


def test_solver_end_of_day_neutrality(sample_request):
    compiled = compile_directives(sample_request, [])
    result = solve_campus_energy_lp(sample_request, compiled)
    assert result.success is True

    final_battery = result.battery_energy_vector[-1]
    assert abs(final_battery - sample_request.battery.initial_energy_kwh) < JUDGE_TOLERANCE


def test_solver_no_charge_restriction(sample_request):
    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment=NoChargeAdjustment(hours=[14, 15]),
            explanation="Test.",
        )
    ]
    compiled = compile_directives(sample_request, directives)
    result = solve_campus_energy_lp(sample_request, compiled)
    assert result.success is True

    # b[14] and b[15] must be <= 0 (no charging)
    assert result.battery_flow_vector[14] <= JUDGE_TOLERANCE
    assert result.battery_flow_vector[15] <= JUDGE_TOLERANCE


def test_solver_zero_solar_edge_case():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=0.0, tariff_bdt_per_kwh=10.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="ZERO-SOLAR",
        operator_notes=["No notes"],
        hours=hours,
        battery=battery,
    )
    compiled = compile_directives(req, [])
    result = solve_campus_energy_lp(req, compiled)
    assert result.success is True
    plan = map_solver_result_to_hourly_plan(result, compiled)
    assert all(h.solar_used_kwh == 0.0 for h in plan)


def test_solver_zero_charge_limit_edge_case():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=0.0, # Zero charge limit
        max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="ZERO-CHARGE",
        operator_notes=["No notes"],
        hours=hours,
        battery=battery,
    )
    compiled = compile_directives(req, [])
    result = solve_campus_energy_lp(req, compiled)
    assert result.success is True
    plan = map_solver_result_to_hourly_plan(result, compiled)
    assert all(h.battery_action != BatteryAction.CHARGE for h in plan)


def test_solver_zero_tariff_edge_case():
    hours = [HourEntry(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=0.0) for h in range(24)]
    battery = BatteryConfig(
        capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0
    )
    req = OptimizeEnergyRequest(
        scenario_id="ZERO-TARIFF",
        operator_notes=["No notes"],
        hours=hours,
        battery=battery,
    )
    compiled = compile_directives(req, [])
    result = solve_campus_energy_lp(req, compiled)
    assert result.success is True
    assert abs(result.objective_cost - 0.0) < JUDGE_TOLERANCE
