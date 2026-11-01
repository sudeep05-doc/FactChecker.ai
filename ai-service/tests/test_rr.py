from datetime import datetime, timezone
from uuid import UUID

from app.cmref import CMREF
from app.cmref.contradiction import ContradictionEvidence
from app.cmref.projection import ProjectionRegistry
from app.rr import build_reasoning_representation
from app.rr.models import RRConsistencyRecord, RRConsistencyStatus
from app.usr import USREmbedding, USRImage, USRText, UnifiedSemanticRepresentationBuilder


def make_cmref_result():
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000019",
        text=USRText(
            text="claim",
            embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0]),
        ),
        image=USRImage(
            embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0]),
        ),
    )
    return CMREF(
        ProjectionRegistry(2),
        contradiction_evaluator=lambda left, right: ContradictionEvidence(0.25, True, {"version": "test-v1"}),
        alignment_proxy_threshold=0.5,
        alignment_mode="alignment",
    ).reason(usr)


def test_rr_preserves_cmref_trace_and_serializes_round_trip():
    timestamp = datetime(2026, 9, 19, tzinfo=timezone.utc)
    rr = build_reasoning_representation(make_cmref_result(), timestamp=timestamp)

    payload = rr.model_dump(mode="json")
    restored = type(rr).model_validate(payload)

    assert restored == rr
    assert restored.request_id == UUID("00000000-0000-4000-8000-000000000019")
    assert restored.timestamp == timestamp
    assert len(restored.pairwise_alignments) == 1
    assert len(restored.pairwise_similarities) == 1
    assert restored.contradiction == 0.25
    assert restored.consistency.score is None
    assert restored.consistency.status == RRConsistencyStatus.UNAVAILABLE
    assert restored.consistency.unavailable_reason == "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    assert restored.diagnostic_proxies[0].label == "alignment_proxy"
    assert restored.normalized_representation_references[0].reference.startswith("cmref://")


def test_rr_preserves_undefined_scores_as_null():
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000019",
        text=USRText(
            text="claim",
            embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0]),
        ),
    )
    cmref_result = CMREF(ProjectionRegistry(2)).reason(usr)
    rr = build_reasoning_representation(cmref_result)

    assert rr.consistency.score is None
    assert rr.consistency.contextual is None
    assert rr.consistency.status == RRConsistencyStatus.UNAVAILABLE
    assert rr.consistency.unavailable_reason == "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    assert rr.contradiction is None
    assert rr.reasoning_score is None
    assert rr.decision_evidence is None
    assert rr.consistency.model_dump()["score"] is None


def test_rr_rejects_context_or_similarity_as_consistency_measurements():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="deprecated"):
        RRConsistencyRecord(contextual=0.8)
    with pytest.raises(ValidationError, match="deprecated"):
        RRConsistencyRecord(alignment=1.0)
    with pytest.raises(ValidationError, match="available evaluator"):
        RRConsistencyRecord(score=0.8)


def test_rr_can_represent_a_future_evaluator_measurement_separately():
    consistency = RRConsistencyRecord(
        score=0.8,
        status=RRConsistencyStatus.AVAILABLE,
        evaluator_version="independent-consistency-v1",
        unavailable_reason=None,
    )
    rr = build_reasoning_representation(make_cmref_result())
    payload = rr.model_dump(mode="json")
    payload["consistency"] = consistency.model_dump(mode="json")
    measured = type(rr).model_validate(payload)

    assert measured.consistency.score == 0.8
    assert measured.consistency.status == RRConsistencyStatus.AVAILABLE
    assert measured.consistency.evaluator_version == "independent-consistency-v1"
    assert measured.pairwise_similarities[0].cosine_similarity == 1.0
