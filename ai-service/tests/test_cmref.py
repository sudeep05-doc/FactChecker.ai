from uuid import uuid4

import pytest

from app.cmref import CMREF, EvidenceWeight
from app.cmref.contradiction import ContradictionEvidence
from app.cmref.contextual import ContextualFeature
from app.cmref.consistency import consistency_score
from app.cmref.projection import ProjectionAdapter, ProjectionRegistry
from app.usr import (
    USRAudioTranscript,
    USREmbedding,
    USRImage,
    USRModality,
    USROCR,
    USRText,
    USRVideo,
    UnifiedSemanticRepresentationBuilder,
)


REQUEST_ID = uuid4()


def embed(name="shared", values=None):
    values = values or [1.0, 0.0]
    return USREmbedding(model_name=name, dimension=len(values), values=values)


def text_image_usr(text_values=None, image_values=None, metadata=None):
    return UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="claim", embedding=embed(values=text_values)) if text_values is not None else None,
        image=USRImage(embedding=embed("shared", image_values)) if image_values is not None else None,
        modality_metadata=metadata or {},
    )


def cmref(**kwargs):
    return CMREF(ProjectionRegistry(working_dimension=2), **kwargs)


def test_text_only_has_fusion_but_undefined_alignment_and_reasoning():
    result = cmref().reason(text_image_usr(text_values=[1.0, 0.0]))

    assert result.valid_modalities == ["text"]
    assert result.fused_representation == pytest.approx([1.0, 0.0])
    assert result.pairwise_alignments == []
    assert result.consistency is None
    assert result.reasoning_score is None
    assert result.decision_evidence is None


def test_image_only_is_valid():
    result = cmref().reason(text_image_usr(image_values=[0.0, 1.0]))

    assert result.valid_modalities == ["image"]
    assert result.omitted_modalities == []
    assert result.fused_representation == pytest.approx([0.0, 1.0])


def test_text_and_image_have_pairwise_alignment():
    result = cmref().reason(text_image_usr([1.0, 0.0], [0.0, 1.0]))

    assert result.pairwise_alignments == []
    assert len(result.pairwise_similarities) == 1
    assert result.pairwise_similarities[0]["cosine_similarity"] == pytest.approx(0.0)
    assert result.consistency is None
    assert result.contradiction is None
    assert result.reasoning_score is None
    assert "CONSISTENCY_EVALUATOR_UNAVAILABLE" in result.undefined_score_reasons


def test_alignment_records_are_available_without_being_called_consistency():
    result = cmref(alignment_mode="alignment").reason(
        text_image_usr([1.0, 0.0], [0.0, 1.0])
    )

    assert result.pairwise_alignments[0]["signed_cosine"] == pytest.approx(0.0)
    assert result.pairwise_alignments[0]["bounded_alignment"] == pytest.approx(0.5)
    assert result.pairwise_similarities[0]["cosine_similarity"] == pytest.approx(0.0)
    assert result.consistency is None


def test_legacy_consistency_mode_is_safe_alignment_alias():
    result = cmref(alignment_mode="consistency").reason(
        text_image_usr([1.0, 0.0], [1.0, 0.0])
    )

    assert result.configuration_versions["alignment_mode"] == "alignment"
    assert result.pairwise_alignments
    assert result.consistency is None
    assert result.contradiction is None
    assert result.reasoning_score is None


def test_text_image_ocr_keeps_ocr_as_non_embedding_evidence():
    usr = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="claim", embedding=embed()),
        image=USRImage(embedding=embed("shared", [1.0, 0.0])),
        ocr=USROCR(extracted_text="claim text", ocr_confidence=0.9),
    )
    result = cmref().reason(usr)

    assert set(result.valid_modalities) == {"text", "image"}
    assert "ocr" not in result.valid_modalities
    assert "ocr" not in result.omitted_modalities


def test_multiple_modalities_and_video_frames_are_fused():
    usr = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="claim", embedding=embed()),
        image=USRImage(embedding=embed("shared", [1.0, 0.0])),
        audio=USRAudioTranscript(transcript="speech"),
        video=USRVideo(
            transcript="video speech",
            frame_embeddings=[embed("shared", [1.0, 0.0]), embed("shared", [1.0, 0.0])],
        ),
    )
    result = cmref().reason(usr)

    assert set(result.valid_modalities) == {"text", "image", "video_frames"}
    assert result.fusion_metadata["contributing_modalities"] == ["image", "text", "video_frames"]
    assert "audio_transcript" not in result.valid_modalities


def test_failed_present_modality_is_traceable_and_not_negative_evidence():
    usr = text_image_usr(text_values=[1.0, 0.0], metadata={})
    usr.preprocessing_metadata["failures"] = {"image": "IMAGE_PREPROCESSING_FAILED"}
    result = cmref().reason(usr)

    assert "image" in result.omitted_modalities
    assert any(issue.code == "MODALITY_PREPROCESSING_FAILED" for issue in result.issues)
    assert result.consistency is None


def test_missing_projection_adapter_is_recorded_without_padding_or_truncation():
    result = CMREF(ProjectionRegistry(working_dimension=2)).reason(
        text_image_usr(text_values=[1.0, 0.0])
    )
    # Same dimension uses explicit identity; a 3D model needs an adapter.
    usr = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID, text=USRText(text="claim", embedding=embed("three", [1.0, 0.0, 0.0]))
    )
    result = cmref().reason(usr)

    assert result.valid_modalities == []
    assert result.omitted_modalities == ["text"]
    assert result.issues[0].code == "PROJECTION_ADAPTER_UNAVAILABLE"
    assert result.fused_representation is None


def test_configured_projection_adapter_is_used_and_versioned():
    adapter = ProjectionAdapter("three", 3, 2, "test-projection-v1", lambda values: [values[0], values[1]])
    usr = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID, text=USRText(text="claim", embedding=embed("three", [1.0, 0.0, 0.0]))
    )
    result = CMREF(ProjectionRegistry(2, {"three": adapter})).reason(usr)

    assert result.valid_modalities == ["text"]
    assert result.projection_information["text"]["version"] == "test-projection-v1"


def test_zero_nan_and_infinite_embeddings_are_rejected():
    for values, expected in [([0.0, 0.0], "zero-norm"), ([float("nan"), 0.0], "finite"), ([float("inf"), 0.0], "finite")]:
        if expected == "finite":
            with pytest.raises(ValueError, match="finite"):
                embed(values=values)
            continue
        usr = UnifiedSemanticRepresentationBuilder().build(
            REQUEST_ID, text=USRText(text="claim", embedding=embed(values=values))
        )
        result = cmref().reason(usr)
        assert result.issues[0].code == "INVALID_EMBEDDING"
        assert "zero-norm" in result.issues[0].message


def test_identical_embeddings_are_strongly_aligned():
    result = cmref(alignment_mode="alignment").reason(text_image_usr([1.0, 0.0], [1.0, 0.0]))

    assert result.pairwise_alignments[0]["signed_cosine"] == pytest.approx(1.0)
    assert result.pairwise_alignments[0]["bounded_alignment"] == pytest.approx(1.0)


def test_weakly_aligned_embeddings_remain_evidence_not_a_label():
    result = cmref(alignment_mode="alignment").reason(text_image_usr([1.0, 0.0], [-1.0, 0.0]))

    assert result.pairwise_alignments[0]["signed_cosine"] == pytest.approx(-1.0)
    assert result.pairwise_alignments[0]["bounded_alignment"] == pytest.approx(0.0)
    assert not hasattr(result, "prediction")


def test_contradiction_unavailable_is_null():
    result = cmref().reason(text_image_usr([1.0, 0.0], [0.0, 1.0]))

    assert result.contradiction is None
    assert "CONTRADICTION_EVALUATOR_UNAVAILABLE" in result.undefined_score_reasons


def test_contradiction_evaluator_available_is_aggregated():
    def evaluator(left, right):
        return ContradictionEvidence(0.75, True, {"relation": "test"})

    result = cmref(contradiction_evaluator=evaluator).reason(
        text_image_usr([1.0, 0.0], [0.0, 1.0])
    )

    assert result.contradiction == pytest.approx(0.75)
    assert result.contradiction_records[0]["relation_metadata"]["relation"] == "test"
    assert result.reasoning_score is None


def test_alignment_proxy_is_diagnostic_only():
    result = cmref(alignment_mode="alignment", alignment_proxy_threshold=0.5).reason(
        text_image_usr([1.0, 0.0], [-1.0, 0.0])
    )

    pair = result.pairwise_alignments[0]
    assert pair["alignment_proxy_label"] == "alignment_proxy"
    assert pair["alignment_proxy"] == pytest.approx(1.5)
    assert result.decision_evidence is None


def test_contextual_features_are_optional_and_versioned():
    def provider(usr):
        return [ContextualFeature("temporal_agreement", 0.8, "context-v1", {"source": "test"})]

    result = cmref(contextual_provider=provider).reason(
        text_image_usr([1.0, 0.0], [1.0, 0.0])
    )

    assert result.contextual_records[0]["version"] == "context-v1"
    assert result.consistency is None
    assert result.consistency_status == "unavailable"
    assert result.consistency_unavailable_reason == "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    assert result.consistency_records == {"alignment": None, "context": None, "weights": {}}
    assert result.reasoning_score is None


def test_generic_alignment_and_context_aggregation_cannot_create_consistency():
    score, reason, weights = consistency_score(
        alignment=1.0,
        contextual=0.8,
        alignment_weight=3.0,
        contextual_weight=2.0,
    )

    assert score is None
    assert reason == "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    assert weights == {}


def test_missing_contextual_features_are_not_zero():
    result = cmref().reason(text_image_usr([1.0, 0.0], [1.0, 0.0]))

    assert result.consistency is None
    assert result.consistency_status == "unavailable"
    assert result.consistency_records["context"] is None
    assert "CONSISTENCY_EVALUATOR_UNAVAILABLE" in result.undefined_score_reasons


def test_no_computable_reasoning_evidence_is_null():
    result = cmref().reason(text_image_usr(text_values=[1.0, 0.0]))

    assert result.reasoning_score is None
    assert "NO_VALIDATED_REASONING_SCORE_COMPUTATION" in result.undefined_score_reasons


def test_decision_evidence_requires_explicit_coefficients():
    result = cmref(
        decision_coefficients={
            "bias": 0.0,
            "reasoning": 1.0,
            "alignment": 1.0,
            "contradiction": 1.0,
            "context": 1.0,
        },
        contradiction_evaluator=lambda left, right: ContradictionEvidence(0.2, True, {}),
        contextual_provider=lambda usr: [ContextualFeature("context", 0.8, "context-v1", {})],
    ).reason(text_image_usr([1.0, 0.0], [1.0, 0.0]))

    assert result.decision_evidence is None
    assert result.reasoning_score is None


def test_non_default_weights_are_recorded():
    result = cmref(
        modality_weights={"text": EvidenceWeight(2.0, 0.5, 1.0, "weights-v1")}
    ).reason(text_image_usr([1.0, 0.0], [1.0, 0.0]))

    assert result.modality_weights["text"] == pytest.approx(1.0)
    assert result.projection_information["text"]["weight_version"] == "weights-v1"


def test_missing_model_metadata_is_rejected_by_cmref():
    usr = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID, text=USRText(text="claim", embedding=embed(" "))
    )
    result = cmref().reason(usr)

    assert result.valid_modalities == []
    assert result.issues[0].code == "MODEL_METADATA_UNAVAILABLE"
