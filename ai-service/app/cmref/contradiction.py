"""Explicit contradiction evaluator interface and diagnostic proxy."""

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ContradictionEvidence:
    score: float
    valid: bool
    metadata: dict[str, Any]


class ContradictionEvaluator:
    """Interface for a future semantic contradiction relation evaluator."""

    def evaluate(self, left: Any, right: Any) -> ContradictionEvidence:
        raise NotImplementedError


def aggregate_contradiction(
    records: list[dict],
    evaluator: Optional[Callable[[dict, dict], ContradictionEvidence]] = None,
) -> tuple[Optional[float], list[dict], Optional[str]]:
    if evaluator is None:
        return None, [], "CONTRADICTION_EVALUATOR_UNAVAILABLE"
    evidence = []
    for pair in records:
        result = evaluator(pair["left_record"], pair["right_record"])
        if result.valid:
            if not 0 <= result.score <= 1:
                raise ValueError("contradiction score must be in [0, 1]")
            evidence.append({**pair, "contradiction_score": result.score, "relation_metadata": result.metadata})
    if not evidence:
        return None, [], "NO_VALID_CONTRADICTION_EVIDENCE"
    denominator = sum(item["left_weight"] * item["right_weight"] for item in evidence)
    score = sum(
        item["left_weight"] * item["right_weight"] * item["contradiction_score"]
        for item in evidence
    ) / denominator
    return score, evidence, None


def alignment_proxy(signed_cosine: float, threshold: float) -> float:
    return max(0.0, threshold - signed_cosine)