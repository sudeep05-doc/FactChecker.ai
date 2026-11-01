"""Conversion from CMREF evidence output to the RR audit artifact."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.cmref.cmref import CMREFResult
from app.rr.models import (
    RRAlignmentRecord,
    RRConfigurationError,
    RRConsistencyRecord,
    RRContextualFeatureRecord,
    RRContradictionRecord,
    RRDiagnosticProxy,
    RRModel,
    RRNormalizedRepresentationReference,
    RRNumericalStability,
    RRProjectionAdapter,
    RRSimilarityRecord,
    ReasoningRepresentation,
)


def build_reasoning_representation(
    cmref_result: CMREFResult,
    timestamp: Optional[datetime] = None,
) -> ReasoningRepresentation:
    """Serialize CMREF output without changing undefined evidence into zero."""

    projections = []
    model_versions: Dict[str, str] = {}
    references = []
    for modality, info in cmref_result.projection_information.items():
        projections.append(RRProjectionAdapter(
            modality=modality,
            model_name=info["model_name"],
            source_dimension=info["source_dimension"],
            target_dimension=info["target_dimension"],
            version=info["version"],
            weight_version=info["weight_version"],
        ))
        model_versions[modality] = info["model_name"]
        values = cmref_result.normalized_representations.get(modality, [])
        references.append(RRNormalizedRepresentationReference(
            modality=modality,
            reference=f"cmref://{cmref_result.request_id}/normalized/{modality}",
            dimension=len(values),
            model_name=info["model_name"],
            projection_version=info["version"],
            value_count=len(values),
        ))

    alignments = [RRAlignmentRecord(
        left_modality=pair["left_modality"],
        right_modality=pair["right_modality"],
        left_model=pair["left_model"],
        right_model=pair["right_model"],
        projection_version=pair["projection_version"],
        left_weight=pair["left_weight"],
        right_weight=pair["right_weight"],
        signed_cosine=pair["signed_cosine"],
        bounded_alignment=pair["bounded_alignment"],
        diagnostic_proxy=pair.get("alignment_proxy"),
        diagnostic_proxy_label=pair.get("alignment_proxy_label"),
    ) for pair in cmref_result.pairwise_alignments]
    similarities = [RRSimilarityRecord(**pair) for pair in cmref_result.pairwise_similarities]

    contradictions = [RRContradictionRecord(
        left_modality=record["left_modality"],
        right_modality=record["right_modality"],
        left_weight=record["left_weight"],
        right_weight=record["right_weight"],
        contradiction_score=record["contradiction_score"],
        relation_metadata=record.get("relation_metadata", {}),
    ) for record in cmref_result.contradiction_records]

    contextual = [RRContextualFeatureRecord(**record) for record in cmref_result.contextual_records]
    configuration_errors = [
        RRConfigurationError(code=issue.code, message=issue.message, modality=issue.modality)
        for issue in cmref_result.issues
        if issue.code in {
            "PROJECTION_ADAPTER_UNAVAILABLE",
            "MODEL_METADATA_UNAVAILABLE",
            "INVALID_EMBEDDING",
            "NON_POSITIVE_EVIDENCE_WEIGHT",
        }
    ]
    proxy_records = [pair for pair in cmref_result.pairwise_alignments if "alignment_proxy" in pair]
    diagnostic_proxies = []
    if proxy_records:
        diagnostic_proxies.append(RRDiagnosticProxy(label="alignment_proxy", records=proxy_records))

    fused_reference = None
    if cmref_result.fused_representation is not None:
        fused_reference = f"cmref://{cmref_result.request_id}/fused"

    return ReasoningRepresentation(
        request_id=cmref_result.request_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        available_modalities=cmref_result.valid_modalities,
        omitted_modalities=cmref_result.omitted_modalities,
        modality_weights=cmref_result.modality_weights,
        projection_adapters=projections,
        model_versions=model_versions,
        normalized_representation_references=references,
        pairwise_alignments=alignments,
        pairwise_similarities=similarities,
        consistency=RRConsistencyRecord(
            score=cmref_result.consistency,
            status=cmref_result.consistency_status,
            evaluator_version=cmref_result.consistency_evaluator_version,
            unavailable_reason=cmref_result.consistency_unavailable_reason,
        ),
        contradiction=cmref_result.contradiction,
        contradiction_records=contradictions,
        contextual_features=contextual,
        fused_representation_reference=fused_reference,
        fusion_metadata=cmref_result.fusion_metadata,
        reasoning_score=cmref_result.reasoning_score,
        decision_evidence=cmref_result.decision_evidence,
        undefined_score_reasons=cmref_result.undefined_score_reasons,
        configuration_errors=configuration_errors,
        numerical_stability=RRNumericalStability(**cmref_result.numerical_stability),
        diagnostic_proxies=diagnostic_proxies,
    )
