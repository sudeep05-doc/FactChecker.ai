"""Pairwise cross-modal cosine alignment."""

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class VectorRecord:
    modality: str
    model_name: str
    values: Tuple[float, ...]
    weight: float
    projection_version: str


def cosine_alignment(left: Sequence[float], right: Sequence[float]) -> tuple[float, float]:
    if len(left) != len(right):
        raise ValueError("alignment vectors must have equal dimensions")
    signed = sum(a * b for a, b in zip(left, right))
    signed = max(-1.0, min(1.0, float(signed)))
    return signed, (signed + 1.0) / 2.0


def pairwise_alignments(records: Dict[str, VectorRecord]) -> list[dict]:
    names = sorted(records)
    result = []
    for index, left_name in enumerate(names):
        for right_name in names[index + 1:]:
            left, right = records[left_name], records[right_name]
            signed, bounded = cosine_alignment(left.values, right.values)
            result.append({
                "left_modality": left.modality,
                "right_modality": right.modality,
                "left_model": left.model_name,
                "right_model": right.model_name,
                "projection_version": left.projection_version,
                "left_weight": left.weight,
                "right_weight": right.weight,
                "signed_cosine": signed,
                "bounded_alignment": bounded,
            })
    return result


def weighted_alignment(pairs: list[dict]) -> Optional[float]:
    denominator = sum(pair["left_weight"] * pair["right_weight"] for pair in pairs)
    if denominator <= 0:
        return None
    return sum(
        pair["left_weight"] * pair["right_weight"] * pair["bounded_alignment"]
        for pair in pairs
    ) / denominator