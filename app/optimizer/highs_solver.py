"""SciPy linprog solver with HiGHS backend for 24-hour campus energy scheduling."""

import time
import numpy as np
from scipy.optimize import linprog
from app.core.constants import HOURS_PER_DAY
from app.core.logging import logger
from app.directives.compiler import CompiledConstraints
from app.optimizer.model import SolverResult
from app.schemas.request import OptimizeEnergyRequest


class SolverError(Exception):
    """Raised when the LP optimization fails or reports infeasibility."""
    pass


def solve_campus_energy_lp(
    request: OptimizeEnergyRequest, constraints: CompiledConstraints
) -> SolverResult:
    """Solve the 24-hour campus energy schedule via linear programming.

    Variables (96 total):
      g[0..23]: grid energy import (indices 0..23)
      s[0..23]: solar energy used (indices 24..47)
      b[0..23]: net battery flow (indices 48..71), where b > 0 is charge, b < 0 is discharge
      e[0..23]: battery energy stored after hour (indices 72..95)

    Objective:
      Minimize SUM(g[h] * tariff[h]) for h = 0..23
    """
    start_time = time.perf_counter()
    num_vars = 4 * HOURS_PER_DAY  # 96 variables

    # 1. Objective coefficients
    c = np.zeros(num_vars, dtype=np.float64)
    for h in range(HOURS_PER_DAY):
        c[h] = request.hours[h].tariff_bdt_per_kwh

    # 2. Variable bounds
    bounds = []

    # g[h]: grid energy import [0, max_grid[h]]
    for h in range(HOURS_PER_DAY):
        upper_g = constraints.max_grid[h]
        bounds.append((0.0, upper_g))

    # s[h]: solar energy used [0, effective_solar[h]]
    for h in range(HOURS_PER_DAY):
        upper_s = max(0.0, constraints.effective_solar[h])
        bounds.append((0.0, upper_s))

    # b[h]: net battery flow [-max_discharge, +max_charge]
    for h in range(HOURS_PER_DAY):
        min_b = -request.battery.max_discharge_kwh_per_hour
        max_b = request.battery.max_charge_kwh_per_hour

        # Restrict charging if no_charge_window applies
        if constraints.no_charge[h]:
            max_b = min(max_b, 0.0)

        # Restrict discharging if no_discharge_window applies
        if constraints.no_discharge[h]:
            min_b = max(min_b, 0.0)

        bounds.append((min_b, max_b))

    # e[h]: battery energy stored [minimum_battery_required[h], capacity]
    # Enforcing strict end-of-day neutrality: e[23] == initial_energy
    for h in range(HOURS_PER_DAY):
        min_e = constraints.minimum_battery_required[h]
        max_e = request.battery.capacity_kwh

        if h == HOURS_PER_DAY - 1:
            # Hour 23 must restore battery exactly to initial energy
            min_e = request.battery.initial_energy_kwh
            max_e = request.battery.initial_energy_kwh

        bounds.append((min_e, max_e))

    # 3. Equality constraints (A_eq * x = b_eq)
    # A) 24 Energy balance equations: g[h] + s[h] - b[h] = demand[h]
    # B) 24 Battery state transition equations:
    #    e[0] - b[0] = initial_energy
    #    e[h] - e[h-1] - b[h] = 0 for h = 1..23
    num_eq = 2 * HOURS_PER_DAY  # 48 equality constraints
    A_eq = np.zeros((num_eq, num_vars), dtype=np.float64)
    b_eq = np.zeros(num_eq, dtype=np.float64)

    # A) Energy balance rows: 0..23
    for h in range(HOURS_PER_DAY):
        row = h
        A_eq[row, h] = 1.0       # g[h]
        A_eq[row, 24 + h] = 1.0  # s[h]
        A_eq[row, 48 + h] = -1.0 # -b[h]
        b_eq[row] = request.hours[h].demand_kwh

    # B) State transition rows: 24..47
    # Hour 0
    row_0 = 24
    A_eq[row_0, 72] = 1.0       # e[0]
    A_eq[row_0, 48] = -1.0      # -b[0]
    b_eq[row_0] = request.battery.initial_energy_kwh

    # Hours 1..23
    for h in range(1, HOURS_PER_DAY):
        row = 24 + h
        A_eq[row, 72 + h] = 1.0      # e[h]
        A_eq[row, 72 + h - 1] = -1.0  # -e[h-1]
        A_eq[row, 48 + h] = -1.0     # -b[h]
        b_eq[row] = 0.0

    # 4. Invoke SciPy HiGHS LP Solver
    res = linprog(
        c=c,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options={"presolve": True},
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    if not res.success:
        logger.error(
            "HiGHS optimization failed",
            extra={"solver_status": res.status, "solver_msg": res.message, "duration_ms": elapsed_ms},
        )
        raise SolverError(f"HiGHS solver failed: {res.message} (status {res.status})")

    x = res.x
    grid_vec = x[0:24]
    solar_vec = x[24:48]
    battery_flow_vec = x[48:72]
    battery_energy_vec = x[72:96]

    return SolverResult(
        success=True,
        status_message=res.message,
        objective_cost=float(res.fun),
        grid_vector=grid_vec,
        solar_vector=solar_vec,
        battery_flow_vector=battery_flow_vec,
        battery_energy_vector=battery_energy_vec,
        solve_duration_ms=elapsed_ms,
    )
