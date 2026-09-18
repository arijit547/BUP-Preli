"""Validate a scenario input and candidate response JSON against GridWise rules."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.directives.compiler import compile_directives
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.validation.replay import replay_and_validate_schedule


def validate_files(input_path: str, output_path: str) -> bool:
    with open(input_path, "r", encoding="utf-8") as f:
        req_data = json.load(f)
    with open(output_path, "r", encoding="utf-8") as f:
        res_data = json.load(f)

    try:
        req = OptimizeEnergyRequest.model_validate(req_data)
        res = OptimizeEnergyResponse.model_validate(res_data)

        if req.scenario_id != res.scenario_id:
            print(f"FAILED: scenario_id mismatch ('{req.scenario_id}' != '{res.scenario_id}')")
            return False

        compiled = compile_directives(req, res.directive_interpretation)
        replay_and_validate_schedule(req, compiled, res.hourly_plan)

        # Verify recalculated totals
        calc_grid = sum(h.grid_kwh for h in res.hourly_plan)
        calc_cost = sum(h.grid_kwh * req.hours[i].tariff_bdt_per_kwh for i, h in enumerate(res.hourly_plan))
        calc_peak = max(h.grid_kwh for h in res.hourly_plan)

        if abs(calc_grid - res.total_grid_kwh) > 0.01:
            print(f"FAILED: total_grid_kwh mismatch: {calc_grid} != {res.total_grid_kwh}")
            return False
        if abs(calc_cost - res.total_cost_bdt) > 0.01:
            print(f"FAILED: total_cost_bdt mismatch: {calc_cost} != {res.total_cost_bdt}")
            return False
        if abs(calc_peak - res.peak_grid_kwh) > 0.01:
            print(f"FAILED: peak_grid_kwh mismatch: {calc_peak} != {res.peak_grid_kwh}")
            return False

        print("PASSED: The solution satisfies all GridWise physical constraints and recalculations.")
        return True

    except Exception as e:
        print(f"FAILED validation: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python validate_solution.py <input.json> <output.json>")
        sys.exit(1)
    success = validate_files(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
