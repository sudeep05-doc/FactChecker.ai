"""Deterministic RR-to-decision feature extraction."""

import math
from typing import List

from app.decision.schemas import FeatureVector
from app.rr.models import ReasoningRepresentation


FEATURE_SCHEMA_VERSION = "rr-decision-v1"
FEATURE_NAMES = [
    "reasoning_score", "reasoning_score_present", "decision_evidence", "decision_evidence_present",
    "consistency_alignment", "consistency_alignment_present", "consistency_contextual", "consistency_contextual_present",
    "consistency_score", "consistency_score_present", "contradiction", "contradiction_present",
    "alignment_mean", "alignment_mean_present", "alignment_count", "contextual_mean", "contextual_count",
    "available_modality_count", "embedded_modality_count", "omitted_modality_count",
]


def extract_features(rr: ReasoningRepresentation) -> FeatureVector:
    alignments = rr.pairwise_alignments
    contextual = rr.contextual_features
    alignment_mean = _mean([item.bounded_alignment for item in alignments])
    contextual_mean = _mean([item.value for item in contextual])
    optional = {
        "reasoning_score": rr.reasoning_score,
        "decision_evidence": rr.decision_evidence,
        "consistency_alignment": rr.consistency.alignment,
        "consistency_contextual": rr.consistency.contextual,
        "consistency_score": rr.consistency.score,
        "contradiction": rr.contradiction,
        "alignment_mean": alignment_mean,
        "contextual_mean": contextual_mean,
    }
    values = []
    missing = {}
    provenance = {}
    for name in FEATURE_NAMES:
        if name.endswith("_present"):
            source = name.removesuffix("_present")
            value = 0.0 if optional.get(source) is None else 1.0
            missing[name] = False
            provenance[name] = f"presence:{source}"
        elif name in optional:
            value = optional[name]
            missing[name] = value is None
            provenance[name] = f"rr.{name}"
            if value is None:
                value = 0.0
        elif name == "alignment_count":
            value, provenance[name] = float(len(alignments)), "len(rr.pairwise_alignments)"
            missing[name] = False
        elif name == "contextual_count":
            value, provenance[name] = float(len(contextual)), "len(rr.contextual_features)"
            missing[name] = False
        elif name == "available_modality_count":
            value, provenance[name] = float(len(rr.available_modalities)), "len(rr.available_modalities)"
            missing[name] = False
        elif name == "embedded_modality_count":
            value, provenance[name] = float(len(rr.normalized_representation_references)), "len(rr.normalized_representation_references)"
            missing[name] = False
        elif name == "omitted_modality_count":
            value, provenance[name] = float(len(rr.omitted_modalities)), "len(rr.omitted_modalities)"
            missing[name] = False
        else:
            raise ValueError(f"unsupported decision feature: {name}")
        if not math.isfinite(float(value)):
            raise ValueError(f"non-finite decision feature: {name}")
        values.append(float(value))
    return FeatureVector(names=FEATURE_NAMES.copy(), values=values, missing=missing, schema_version=FEATURE_SCHEMA_VERSION, provenance=provenance)


def _mean(values: List[float]):
    return sum(values) / len(values) if values else None
