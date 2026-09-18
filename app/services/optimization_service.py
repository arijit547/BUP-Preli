"""Core optimization orchestrator coordinating LLM, compiler, solver, and replay."""

import time
from app.core.constants import JUDGE_TOLERANCE
from app.core.logging import logger
from app.directives.compiler import compile_directives
from app.directives.normalizer import normalize_directive
from app.directives.validator import validate_directive_interpretations
from app.llm.interpreter import LLMInterpreter
from app.optimizer.highs_solver import solve_campus_energy_lp
from app.optimizer.result_mapper import map_solver_result_to_hourly_plan
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import OptimizeEnergyResponse
from app.validation.replay import replay_and_validate_schedule


def _generate_deterministic_plan_summary(
    directives_count: int,
    total_grid_kwh: float,
    total_cost_bdt: float,
    peak_grid_kwh: float,
) -> str:
    """Generate an informative, deterministic summary of the dispatch schedule."""
    return (
        f"Optimized 24-hour dispatch schedule incorporating {directives_count} operator directive(s). "
        f"Maximizes rooftop solar self-consumption, shifts battery charging toward lower-cost tariff hours, "
        f"avoids restricted operational windows, respects all active reserve requirements, "
        f"and restores the battery to initial state of charge at hour 23. "
        f"Total grid import: {total_grid_kwh:.2f} kWh across 24h, Peak: {peak_grid_kwh:.2f} kWh, Total Cost: {total_cost_bdt:.2f} BDT."
    )


class OptimizationService:
    """End-to-end service coordinating note interpretation, LP scheduling, and verification."""

    def __init__(self, interpreter: LLMInterpreter | None = None):
        self.interpreter = interpreter or LLMInterpreter()

    async def optimize(self, request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
        total_start = time.perf_counter()

        # Step 1: LLM interpretation of operator notes
        raw_directives, llm_ms = await self.interpreter.interpret_notes(
            request.operator_notes, request.battery.capacity_kwh
        )

        # Step 2: Normalization
        normalized_directives = [
            normalize_directive(d, request.battery.capacity_kwh) for d in raw_directives
        ]

        # Step 3: Strict deterministic guardrail validation
        validated_directives = validate_directive_interpretations(
            normalized_directives,
            expected_note_count=len(request.operator_notes),
            battery=request.battery,
        )

        # Step 4: Directive compilation into immutable constraint arrays
        compiled_constraints = compile_directives(request, validated_directives)

        # Step 5: HiGHS LP Solve
        solver_start = time.perf_counter()
        solver_result = solve_campus_energy_lp(request, compiled_constraints)
        solver_ms = (time.perf_counter() - solver_start) * 1000.0

        # Step 6: Plan reconstruction from continuous solver vectors
        hourly_plan = map_solver_result_to_hourly_plan(solver_result, compiled_constraints)

        # Step 7: Independent physical replay verification
        val_start = time.perf_counter()
        replay_and_validate_schedule(request, compiled_constraints, hourly_plan)
        val_ms = (time.perf_counter() - val_start) * 1000.0

        # Step 8: Recalculate totals directly from the validated hourly plan
        recalculated_total_grid = sum(h.grid_kwh for h in hourly_plan)
        recalculated_total_cost = sum(
            h.grid_kwh * request.hours[i].tariff_bdt_per_kwh for i, h in enumerate(hourly_plan)
        )
        recalculated_peak_grid = max(h.grid_kwh for h in hourly_plan)

        # Step 9: Optimality sanity verification (solver objective vs plan recalculated cost)
        cost_difference = abs(solver_result.objective_cost - recalculated_total_cost)
        if cost_difference > JUDGE_TOLERANCE:
            logger.warning(
                "Solver objective differs from recalculated plan cost beyond tolerance",
                extra={
                    "solver_cost": solver_result.objective_cost,
                    "recalculated_cost": recalculated_total_cost,
                    "diff": cost_difference,
                },
            )

        total_ms = (time.perf_counter() - total_start) * 1000.0

        logger.info(
            "Optimization pipeline successfully completed",
            extra={
                "scenario_id": request.scenario_id,
                "llm_ms": round(llm_ms, 2),
                "solver_ms": round(solver_ms, 2),
                "validation_ms": round(val_ms, 2),
                "total_ms": round(total_ms, 2),
                "total_cost_bdt": round(recalculated_total_cost, 2),
            },
        )

        summary = _generate_deterministic_plan_summary(
            directives_count=len(validated_directives),
            total_grid_kwh=recalculated_total_grid,
            total_cost_bdt=recalculated_total_cost,
            peak_grid_kwh=recalculated_peak_grid,
        )

        return OptimizeEnergyResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=validated_directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=round(recalculated_total_grid, 4),
            total_cost_bdt=round(recalculated_total_cost, 4),
            peak_grid_kwh=round(recalculated_peak_grid, 4),
            plan_summary=summary,
        )
