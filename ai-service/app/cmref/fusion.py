"""Weighted semantic feature fusion."""

import math
from typing import Dict, Optional

from app.cmref.alignment import VectorRecord
from app.cmref.normalization import l2_normalize


def fuse_vectors(records: Dict[str, VectorRecord], epsilon: float = 1e-12) -> tuple[Optional[list[float]], dict]:
    if not records:
        return None, {"contributing_modalities": [], "weights": {}}
    dimension = len(next(iter(records.values())).values)
    total_weight = sum(record.weight for record in records.values())
    if total_weight <= 0:
        return None, {"contributing_modalities": [], "weights": {}}
    barycenter = [
        sum(record.weight * record.values[index] for record in records.values())
        / max(total_weight, epsilon)
        for index in range(dimension)
    ]
    try:
        fused = l2_normalize(barycenter, epsilon)
    except ValueError as error:
        return None, {
            "contributing_modalities": sorted(records),
            "weights": {name: record.weight for name, record in records.items()},
            "dimension": dimension,
            "undefined_reason": str(error),
        }
    return fused, {
        "contributing_modalities": sorted(records),
        "weights": {name: record.weight for name, record in records.items()},
        "dimension": dimension,
    }