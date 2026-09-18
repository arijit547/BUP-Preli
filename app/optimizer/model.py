"""Data structures for optimization problem inputs and raw solutions."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SolverResult:
    """Raw mathematical result returned by the HiGHS linear programming solver."""
    success: bool
    status_message: str
    objective_cost: float
    grid_vector: np.ndarray        # shape (24,)
    solar_vector: np.ndarray       # shape (24,)
    battery_flow_vector: np.ndarray# shape (24,)
    battery_energy_vector: np.ndarray # shape (24,)
    solve_duration_ms: float
