"""Fail-closed compatibility shim for the retired generic consistency score."""

from typing import Optional


def consistency_score(
    alignment: Optional[float],
    contextual: Optional[float] = None,
    alignment_weight: float = 1.0,
    contextual_weight: float = 1.0,
) -> tuple[Optional[float], Optional[str], dict]:
    """Do not infer consistency from generic alignment or contextual values."""
    return None, "CONSISTENCY_EVALUATOR_UNAVAILABLE", {}
