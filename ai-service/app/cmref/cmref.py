"""CMREF orchestration and structured evidence output."""

from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.cmref.alignment import VectorRecord, pairwise_alignments
from app.cmref.contextual import (
    ContextualFeature,
    collect_contextual_features,
)
from app.cmref.contradiction import ContradictionEvidence, aggregate_contradiction, alignment_proxy
from app.cmref.fusion import fuse_vectors
from app.cmref.normalization import l2_normalize
from app.cmref.projection import ProjectionRegistry
from app.usr.models import USRModality, UnifiedSemanticRepresentation


class CMREFIssue(BaseModel):
    code: str
    message: str
    modality: Optional[str] = None


class CMREFResult(BaseModel):
    request_id: UUID
    valid_modalities: List[str] = Field(default_factory=list)
    omitted_modalities: List[str] = Field(default_factory=list)
    modality_weights: Dict[str, float] = Field(default_factory=dict)
    projection_information: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    normalized_representations: Dict[str, List[float]] = Field(default_factory=dict)
    pairwise_alignments: List[Dict[str, Any]] = Field(default_factory=list)
    pairwise_similarities: List[Dict[str, Any]] = Field(default_factory=list)
    consistency: Optional[float] = Field(default=None, ge=0, le=1)
    consistency_status: Literal[
        "available", "unavailable", "not_run", "failed", "not_validated"
    ] = "unavailable"
    consistency_evaluator_version: Optional[str] = None
    consistency_unavailable_reason: Optional[str] = "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    consistency_records: Dict[str, Any] = Field(default_factory=dict)
    contradiction: Optional[float] = None
    contradiction_records: List[Dict[str, Any]] = Field(default_factory=list)
    contextual_records: List[Dict[str, Any]] = Field(default_factory=list)
    fused_representation: Optional[List[float]] = None
    fusion_metadata: Dict[str, Any] = Field(default_factory=dict)
    reasoning_score: Optional[float] = None
    decision_evidence: Optional[float] = None
    undefined_score_reasons: List[str] = Field(default_factory=list)
    configuration_versions: Dict[str, str] = Field(default_factory=dict)
    numerical_stability: Dict[str, Any] = Field(default_factory=dict)
    issues: List[CMREFIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency_contract(self) -> "CMREFResult":
        if self.consistency_status == "available":
            if self.consistency is None or not self.consistency_evaluator_version:
                raise ValueError(
                    "available consistency requires a score and evaluator version"
                )
            if self.consistency_unavailable_reason is not None:
                raise ValueError("available consistency cannot have an unavailable reason")
        elif self.consistency is not None:
            raise ValueError("consistency score requires an available evaluator")
        elif not self.consistency_unavailable_reason:
            raise ValueError("unavailable consistency requires an explicit reason")
        return self


class EvidenceWeight:
    """Versioned evidence-weight configuration for one modality."""

    def __init__(
        self,
        base: float = 1.0,
        quality: float = 1.0,
        freshness: float = 1.0,
        version: str = "default-v1",
    ) -> None:
        if min(base, quality, freshness) < 0:
            raise ValueError("evidence weights must be non-negative")
        self.base = base
        self.quality = quality
        self.freshness = freshness
        self.version = version

    @property
    def value(self) -> float:
        return self.base * self.quality * self.freshness


class CMREF:
    """Compute embedding relations without deriving consistency from cosine.

    ``alignment_mode="consistency"`` remains a compatibility alias for
    returning alignment records; it no longer produces a consistency score.
    """

    def __init__(
        self,
        projection_registry: ProjectionRegistry,
        epsilon: float = 1e-12,
        modality_weights: Optional[Dict[str, EvidenceWeight]] = None,
        contradiction_evaluator: Optional[Any] = None,
        contextual_provider: Optional[Any] = None,
        reasoning_weights: Optional[Dict[str, float]] = None,
        decision_coefficients: Optional[Dict[str, float]] = None,
        alignment_proxy_threshold: Optional[float] = None,
        alignment_mode: str = "similarity_only",
    ) -> None:
        if epsilon <= 0:
            raise ValueError("epsilon must be positive")
        if alignment_mode not in {"consistency", "alignment", "similarity_only"}:
            raise ValueError(
                "alignment_mode must be 'alignment' or 'similarity_only' "
                "('consistency' is accepted as a legacy alias)"
            )
        self.projection_registry = projection_registry
        self.epsilon = epsilon
        self.modality_weights = modality_weights or {}
        self.contradiction_evaluator = contradiction_evaluator
        self.contextual_provider = contextual_provider
        self.reasoning_weights = reasoning_weights
        self.decision_coefficients = decision_coefficients
        self.alignment_proxy_threshold = alignment_proxy_threshold
        self.alignment_mode = "alignment" if alignment_mode == "consistency" else alignment_mode

    def reason(self, usr: UnifiedSemanticRepresentation) -> CMREFResult:
        issues: List[CMREFIssue] = []
        omitted: List[str] = []
        valid: List[str] = []
        records: Dict[str, VectorRecord] = {}
        projection_info: Dict[str, Dict[str, Any]] = {}
        normalized: Dict[str, List[float]] = {}
        modality_weights: Dict[str, float] = {}
        failed_modalities = _failed_modalities(usr)

        for modality, embedding, source_record in _embeddings(usr):
            name = modality.value
            if not embedding.model_name.strip():
                omitted.append(name)
                issues.append(CMREFIssue(
                    code="MODEL_METADATA_UNAVAILABLE",
                    message="Embedding model metadata is required.",
                    modality=name,
                ))
                continue
            weight_config = self.modality_weights.get(name, EvidenceWeight())
            adapter = self.projection_registry.resolve(embedding.model_name, embedding.dimension)
            if adapter is None:
                omitted.append(name)
                issues.append(CMREFIssue(
                    code="PROJECTION_ADAPTER_UNAVAILABLE",
                    message="No configured projection adapter for embedding dimension.",
                    modality=name,
                ))
                continue
            try:
                projected = adapter.project(embedding.values)
                values = l2_normalize(projected, self.epsilon)
            except ValueError as error:
                omitted.append(name)
                issues.append(CMREFIssue(code="INVALID_EMBEDDING", message=str(error), modality=name))
                continue
            weight = weight_config.value
            if weight <= 0:
                omitted.append(name)
                issues.append(CMREFIssue(code="NON_POSITIVE_EVIDENCE_WEIGHT", message="Modality weight is not positive.", modality=name))
                continue
            valid.append(name)
            modality_weights[name] = weight
            normalized[name] = values
            records[name] = VectorRecord(
                modality=name,
                model_name=embedding.model_name,
                values=tuple(values),
                weight=weight,
                projection_version=adapter.version,
            )
            projection_info[name] = {
                "model_name": embedding.model_name,
                "source_dimension": embedding.dimension,
                "target_dimension": adapter.target_dimension,
                "version": adapter.version,
                "weight_version": weight_config.version,
                "weight_components": {
                    "base": weight_config.base,
                    "quality": weight_config.quality,
                    "freshness": weight_config.freshness,
                },
                "source_record": source_record,
            }

        for name in failed_modalities:
            if name not in omitted:
                omitted.append(name)
            issues.append(CMREFIssue(
                code="MODALITY_PREPROCESSING_FAILED",
                message="Modality was present but its preprocessing failed; it was excluded from numerical fusion.",
                modality=name,
            ))

        pairs = pairwise_alignments(records)
        for pair in pairs:
            pair["left_record"] = _record_for(usr, pair["left_modality"])
            pair["right_record"] = _record_for(usr, pair["right_modality"])
        similarity_pairs = [
            {
                "left_modality": pair["left_modality"],
                "right_modality": pair["right_modality"],
                "left_model": pair["left_model"],
                "right_model": pair["right_model"],
                "projection_version": pair["projection_version"],
                "cosine_similarity": pair["signed_cosine"],
            }
            for pair in pairs
        ]
        context_features = collect_contextual_features(usr, self.contextual_provider)
        consistency_reason = "CONSISTENCY_EVALUATOR_UNAVAILABLE"
        contradiction, contradiction_records, contradiction_reason = aggregate_contradiction(
            pairs, self.contradiction_evaluator
        )

        if self.alignment_proxy_threshold is not None and self.alignment_mode == "alignment":
            for pair in pairs:
                pair["alignment_proxy"] = alignment_proxy(
                    pair["signed_cosine"], self.alignment_proxy_threshold
                )
                pair["alignment_proxy_label"] = "alignment_proxy"

        fused, fusion_metadata = fuse_vectors(records, self.epsilon)
        reasoning = None
        reasoning_reason = "NO_VALIDATED_REASONING_SCORE_COMPUTATION"
        internal_decision = None

        undefined = [reason for reason in (consistency_reason, contradiction_reason, reasoning_reason) if reason]
        if len(valid) < 2:
            undefined.append("INSUFFICIENT_CROSS_MODAL_EVIDENCE")
        if fusion_metadata.get("undefined_reason"):
            undefined.append("FUSED_REPRESENTATION_UNDEFINED")
        if internal_decision is None:
            undefined.append("DECISION_EVIDENCE_UNAVAILABLE_NO_VALIDATED_COMPUTATION")

        contextual_records = [
            {"name": feature.name, "value": feature.value, "version": feature.version, "metadata": feature.metadata}
            for feature in context_features
        ]
        return CMREFResult(
            request_id=usr.request_id,
            valid_modalities=valid,
            omitted_modalities=sorted(set(omitted)),
            modality_weights=modality_weights,
            projection_information=projection_info,
            normalized_representations=normalized,
            pairwise_alignments=pairs if self.alignment_mode == "alignment" else [],
            pairwise_similarities=similarity_pairs,
            consistency=None,
            consistency_status="unavailable",
            consistency_evaluator_version=None,
            consistency_unavailable_reason=consistency_reason,
            consistency_records={"alignment": None, "context": None, "weights": {}},
            contradiction=contradiction,
            contradiction_records=contradiction_records,
            contextual_records=contextual_records,
            fused_representation=fused,
            fusion_metadata=fusion_metadata,
            reasoning_score=reasoning,
            decision_evidence=internal_decision,
            undefined_score_reasons=sorted(set(undefined)),
            configuration_versions={
                "projection_working_dimension": str(self.projection_registry.working_dimension),
                "reasoning_score": "unavailable_no_validated_computation",
                "decision_evidence": "unavailable_no_validated_computation",
                "alignment_mode": self.alignment_mode,
            },
            numerical_stability={"epsilon": self.epsilon, "cosine_clamped": True},
            issues=issues,
        )


def _embeddings(usr: UnifiedSemanticRepresentation) -> list[Tuple[USRModality, Any, dict]]:
    result = []
    if usr.text and usr.text.embedding:
        result.append((USRModality.TEXT, usr.text.embedding, usr.text.metadata))
    if usr.image and usr.image.embedding:
        result.append((USRModality.IMAGE, usr.image.embedding, usr.image.metadata))
    if usr.video and usr.video.frame_embeddings:
        # Frame embeddings are one modality; average them before projection.
        first = usr.video.frame_embeddings[0]
        if all(item.dimension == first.dimension and item.model_name == first.model_name for item in usr.video.frame_embeddings):
            values = [
                sum(item.values[index] for item in usr.video.frame_embeddings) / len(usr.video.frame_embeddings)
                for index in range(first.dimension)
            ]
            embedding = first.model_copy(update={"values": values})
            result.append((USRModality.VIDEO_FRAMES, embedding, usr.video.metadata))
    return result


def _record_for(usr: UnifiedSemanticRepresentation, modality: str) -> dict:
    return {"modality": modality, "metadata": usr.modality_metadata.get(modality, {})}


def _failed_modalities(usr: UnifiedSemanticRepresentation) -> list[str]:
    failures = usr.preprocessing_metadata.get("failures", {})
    return list(failures.keys()) if isinstance(failures, dict) else []
