"""Schemas for GridWise directive adjustments and interpretations."""

import math
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from app.core.constants import DirectiveType


def _validate_hours_list(hours: list[int]) -> list[int]:
    """Ensure hours are a list of unique integers 0..23 in strictly ascending order."""
    if not isinstance(hours, list):
        raise ValueError("hours must be a list of integers.")
    for h in hours:
        if not isinstance(h, int) or isinstance(h, bool):
            raise ValueError(f"Each hour must be an integer, got {h}.")
        if h < 0 or h > 23:
            raise ValueError(f"Hour {h} is outside the allowed range [0, 23].")
    if len(hours) != len(set(hours)):
        raise ValueError("Hours list cannot contain duplicate hours.")
    if hours != sorted(hours):
        raise ValueError("Hours list must be in strictly ascending order.")
    return hours


class SolarReductionAdjustment(BaseModel):
    """Adjusts usable solar availability during listed hours."""
    hours: list[int]
    factor: float = Field(..., description="Usable fraction remaining (0.0 to 1.0)")

    @field_validator("hours")
    @classmethod
    def check_hours(cls, v: list[int]) -> list[int]:
        return _validate_hours_list(v)

    @field_validator("factor")
    @classmethod
    def check_factor(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("factor must be a finite number.")
        if v < 0.0 or v > 1.0:
            raise ValueError(f"factor must be between 0.0 and 1.0, got {v}.")
        return round(float(v), 6)


class ReserveAdjustment(BaseModel):
    """Requires battery energy to stay at or above the given reserve in kWh."""
    hours: list[int]
    minimum_energy_kwh: float = Field(..., description="Minimum battery reserve in kWh")

    @field_validator("hours")
    @classmethod
    def check_hours(cls, v: list[int]) -> list[int]:
        return _validate_hours_list(v)

    @field_validator("minimum_energy_kwh")
    @classmethod
    def check_min_energy(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("minimum_energy_kwh must be a finite number.")
        if v < 0.0:
            raise ValueError("minimum_energy_kwh must be non-negative.")
        return round(float(v), 6)


class NoChargeAdjustment(BaseModel):
    """Forbids battery charging during listed hours."""
    hours: list[int]

    @field_validator("hours")
    @classmethod
    def check_hours(cls, v: list[int]) -> list[int]:
        return _validate_hours_list(v)


class NoDischargeAdjustment(BaseModel):
    """Forbids battery discharging during listed hours."""
    hours: list[int]

    @field_validator("hours")
    @classmethod
    def check_hours(cls, v: list[int]) -> list[int]:
        return _validate_hours_list(v)


class MaxGridAdjustment(BaseModel):
    """Caps grid electricity import during listed hours in kWh."""
    hours: list[int]
    max_grid_kwh: float = Field(..., description="Maximum grid import in kWh")

    @field_validator("hours")
    @classmethod
    def check_hours(cls, v: list[int]) -> list[int]:
        return _validate_hours_list(v)

    @field_validator("max_grid_kwh")
    @classmethod
    def check_max_grid(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("max_grid_kwh must be a finite number.")
        if v < 0.0:
            raise ValueError("max_grid_kwh must be non-negative.")
        return round(float(v), 6)


class EmptyAdjustment(BaseModel):
    """Empty adjustment when directive notes contain no actionable numerical parameters."""
    pass


StructuredAdjustmentUnion = Union[
    SolarReductionAdjustment,
    ReserveAdjustment,
    NoChargeAdjustment,
    NoDischargeAdjustment,
    MaxGridAdjustment,
    EmptyAdjustment,
]


class DirectiveInterpretation(BaseModel):
    """Structured interpretation of a single operator note."""
    note_index: int = Field(..., ge=0, description="0-based index of the operator note")
    applies: bool = Field(..., description="True for applicable directives, False only for no_op")
    directive_type: DirectiveType
    structured_adjustment: Optional[StructuredAdjustmentUnion] = None
    explanation: str = Field(default="Directive interpreted from operator note.", description="Short human-readable justification")

    @model_validator(mode="before")
    @classmethod
    def resolve_adjustment_type(cls, data: Any) -> Any:
        """Explicitly resolve structured_adjustment into the matching class for directive_type."""
        if isinstance(data, dict):
            dtype = data.get("directive_type")
            adj = data.get("structured_adjustment")
            if dtype and adj is not None and isinstance(adj, dict):
                if len(adj) == 0:
                    data["structured_adjustment"] = EmptyAdjustment()
                else:
                    dtype_str = dtype.value if isinstance(dtype, DirectiveType) else str(dtype)
                    if dtype_str == DirectiveType.NO_DISCHARGE_WINDOW.value and "hours" in adj:
                        data["structured_adjustment"] = NoDischargeAdjustment.model_validate(adj)
                    elif dtype_str == DirectiveType.NO_CHARGE_WINDOW.value and "hours" in adj:
                        data["structured_adjustment"] = NoChargeAdjustment.model_validate(adj)
                    elif dtype_str == DirectiveType.SOLAR_REDUCTION.value and "hours" in adj:
                        data["structured_adjustment"] = SolarReductionAdjustment.model_validate(adj)
                    elif dtype_str == DirectiveType.MINIMUM_BATTERY_RESERVE.value and "hours" in adj:
                        data["structured_adjustment"] = ReserveAdjustment.model_validate(adj)
                    elif dtype_str == DirectiveType.MAX_GRID_WINDOW.value and "hours" in adj:
                        data["structured_adjustment"] = MaxGridAdjustment.model_validate(adj)
                    else:
                        data["structured_adjustment"] = EmptyAdjustment()
        return data

    @model_validator(mode="after")
    def validate_directive_coupling(self) -> "DirectiveInterpretation":
        if self.directive_type == DirectiveType.NO_OP:
            if self.applies is not False:
                raise ValueError("For no_op directive, applies must be False.")
            if self.structured_adjustment is not None and not isinstance(self.structured_adjustment, EmptyAdjustment):
                raise ValueError("For no_op directive, structured_adjustment must be None/null.")
        elif self.directive_type == DirectiveType.COST_OPTIMIZATION:
            pass
        else:
            if self.applies is not True:
                raise ValueError(f"For directive '{self.directive_type.value}', applies must be True.")
            if self.structured_adjustment is not None and not isinstance(self.structured_adjustment, EmptyAdjustment):
                expected_classes = {
                    DirectiveType.SOLAR_REDUCTION: SolarReductionAdjustment,
                    DirectiveType.MINIMUM_BATTERY_RESERVE: ReserveAdjustment,
                    DirectiveType.NO_CHARGE_WINDOW: NoChargeAdjustment,
                    DirectiveType.NO_DISCHARGE_WINDOW: NoDischargeAdjustment,
                    DirectiveType.MAX_GRID_WINDOW: MaxGridAdjustment,
                }
                expected_cls = expected_classes.get(self.directive_type)
                if expected_cls and not isinstance(self.structured_adjustment, expected_cls):
                    raise ValueError(
                        f"Directive type '{self.directive_type.value}' requires adjustment of type "
                        f"{expected_cls.__name__}, got {type(self.structured_adjustment).__name__}."
                    )
        return self


class DirectiveInterpretationBatch(BaseModel):
    """Container for the batch of interpreted directives produced by the LLM."""
    directive_interpretation: list[DirectiveInterpretation]
