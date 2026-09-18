"""Core constants, enumerations, and numerical precision thresholds."""

from enum import Enum


class DirectiveType(str, Enum):
    """The six officially supported directive types in GridWise."""
    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"


class BatteryAction(str, Enum):
    """Allowed battery actions in the hourly plan."""
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


# Numerical precision & threshold levels
FEASIBILITY_EPS = 1e-7   # Tolerance for LP constraint checking
SIGN_EPS = 1e-8          # Threshold for distinguishing charge/discharge vs idle
FLOAT_CLEANUP_EPS = 1e-9 # Values strictly below this are normalized to 0.0
JUDGE_TOLERANCE = 0.01   # Official judging tolerance (0.01 kWh, 0.01 BDT)
HOURS_PER_DAY = 24

PROMPT_VERSION = "v1.0.0"
SCHEMA_VERSION = "v1.0.0"
