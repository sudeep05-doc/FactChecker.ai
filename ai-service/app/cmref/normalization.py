"""Stable vector validation and L2 normalization."""

import math
from typing import Sequence


def validate_finite(values: Sequence[float]) -> None:
    if not values:
        raise ValueError("embedding must not be empty")
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("embedding values must be finite")


def l2_normalize(values: Sequence[float], epsilon: float = 1e-12) -> list[float]:
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    validate_finite(values)
    norm = math.sqrt(sum(float(value) ** 2 for value in values))
    if norm == 0:
        raise ValueError("zero-norm embedding is invalid")
    scale = max(norm, epsilon)
    return [float(value) / scale for value in values]