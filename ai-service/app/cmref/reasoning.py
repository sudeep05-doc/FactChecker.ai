"""Reasoning and internal decision-evidence score calculations."""

import math
from typing import Any, Dict, Optional


def reasoning_score(
    consistency: Optional[float],
    contradiction: Optional[float],
    contextual: Optional[float],
    weights: Optional[Dict[str, float]] = None,
) -> tuple[Optional[float], Optional[str], dict]:
    configured = weights or {"consistency": 1.0, "no_contradiction": 1.0, "context": 1.0}
    terms = {}
    if consistency is not None:
        terms["consistency"] = consistency
    if contradiction is not None:
        terms["no_contradiction"] = 1.0 - contradiction
    if contextual is not None:
        terms["context"] = contextual
    active = {name: configured[name] for name in terms if name in configured}
    denominator = sum(active.values())
    if not active or denominator <= 0:
        return None, "NO_COMPUTABLE_REASONING_EVIDENCE", {}
    normalized = {name: weight / denominator for name, weight in active.items()}
    return sum(terms[name] * normalized[name] for name in normalized), None, normalized


def stable_sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def decision_evidence(
    reasoning: Optional[float],
    alignment: Optional[float],
    contradiction: Optional[float],
    contextual: Optional[float],
    coefficients: Optional[Dict[str, float]],
) -> Optional[float]:
    if coefficients is None or reasoning is None:
        return None
    required = {"bias", "reasoning", "alignment", "contradiction", "context"}
    if not required.issubset(coefficients):
        return None
    if any(value is None for value in (alignment, contradiction, contextual)):
        return None
    logit = (
        coefficients["bias"]
        + coefficients["reasoning"] * reasoning
        + coefficients["alignment"] * alignment
        - coefficients["contradiction"] * contradiction
        + coefficients["context"] * contextual
    )
    return stable_sigmoid(logit)