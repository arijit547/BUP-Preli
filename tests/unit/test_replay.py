"""Unit tests for independent physical replay validator."""

import pytest
from app.core.constants import BatteryAction, DirectiveType
from app.directives.compiler import compile_directives
from app.optimizer.highs_solver import solve_campus_energy_lp
from app.optimizer.result_mapper import map_solver_result_to_hourly_plan
from app.schemas.directives import DirectiveInterpretation, NoChargeAdjustment
from app.validation.replay import ReplayValidationError, replay_and_validate_schedule


def test_replay_valid_plan_passes(sample_request):
    compiled = compile_directives(sample_request, [])
    result = solve_campus_energy_lp(sample_request, compiled)
    plan = map_solver_result_to_hourly_plan(result, compiled)

    # Must pass without raising exception
    replay_and_validate_schedule(sample_request, compiled, plan)


def test_replay_catches_energy_balance_violation(sample_request):
    compiled = compile_directives(sample_request, [])
    result = solve_campus_energy_lp(sample_request, compiled)
    plan = map_solver_result_to_hourly_plan(result, compiled)

    # Artificially modify grid_kwh in hour 5 to cause imbalance
    plan[5] = plan[5].model_copy(update={"grid_kwh": plan[5].grid_kwh + 25.0})

    with pytest.raises(ReplayValidationError, match="energy balance violation"):
        replay_and_validate_schedule(sample_request, compiled, plan)


def test_replay_catches_neutrality_violation(sample_request):
    compiled = compile_directives(sample_request, [])
    result = solve_campus_energy_lp(sample_request, compiled)
    plan = map_solver_result_to_hourly_plan(result, compiled)

    # Create a request with modified initial energy so transitions remain valid but neutrality fails
    mutated_battery = sample_request.battery.model_copy(update={"initial_energy_kwh": sample_request.battery.initial_energy_kwh + 20.0})
    mutated_request = sample_request.model_copy(update={"battery": mutated_battery})

    with pytest.raises(ReplayValidationError, match="(neutrality violation|battery transition error)"):
        replay_and_validate_schedule(mutated_request, compiled, plan)


def test_replay_catches_charging_in_no_charge_window(sample_request):
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
    plan = map_solver_result_to_hourly_plan(result, compiled)

    # Artificially set hour 14 to charge
    plan[14] = plan[14].model_copy(update={"battery_action": BatteryAction.CHARGE, "battery_kwh": 10.0})

    with pytest.raises(ReplayValidationError, match="no_charge_window"):
        replay_and_validate_schedule(sample_request, compiled, plan)
