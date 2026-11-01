from datetime import datetime, timezone

from app.cmrea import ExplainabilityService
from app.cmref import CMREF
from app.cmref.contradiction import ContradictionEvidence
from app.cmref.contextual import ContextualFeature
from app.cmref.projection import ProjectionRegistry
from app.rr import build_reasoning_representation
from app.usr import USREmbedding, USRImage, USRText, UnifiedSemanticRepresentationBuilder


def make_rr(text=True, image=False, contradiction=False, contextual=False):
    kwargs = {}
    if text:
        kwargs["text"] = USRText(text="claim", embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0]))
    if image:
        kwargs["image"] = USRImage(embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0]))
    usr = UnifiedSemanticRepresentationBuilder().build("00000000-0000-4000-8000-000000000020", **kwargs)
    cmref = CMREF(
        ProjectionRegistry(2),
        contradiction_evaluator=(lambda left, right: ContradictionEvidence(0.2, True, {})) if contradiction else None,
        contextual_provider=(
            lambda usr: [ContextualFeature("temporal_agreement", 0.8, "context-v1", {})]
        )
        if contextual
        else None,
    )
    return build_reasoning_representation(cmref.reason(usr), timestamp=datetime.now(timezone.utc))


def test_text_only_explanation_has_null_confidence():
    result = ExplainabilityService().explain(make_rr())

    assert result.confidence is None
    assert result.prediction is None
    assert result.modality_weights[0].modality == "text"
    assert result.uncertainty_reasons
    assert "CMREF" not in result.explanation
    assert "RR" not in result.explanation
    assert "not independent factual verification" in result.explanation


def test_image_only_and_missing_modality_are_not_penalized():
    result = ExplainabilityService().explain(make_rr(text=False, image=True))

    assert result.modality_weights[0].modality == "image"
    assert all(item.configured_weight >= 0 for item in result.modality_weights)
    assert all(item.normalized_weight >= 0 for item in result.modality_weights)
    assert "image" in result.explanation
    assert "heuristic" in result.explanation


def test_multimodal_heuristic_weights_and_diagnostic_path():
    result = ExplainabilityService().explain(make_rr(text=True, image=True, contradiction=True))

    assert {item.modality for item in result.modality_weights} == {"text", "image"}
    assert result.diagnostic_signals
    assert all("not_truth" in item.interpretation for item in result.diagnostic_signals)
    assert any(event.event == "cosine_similarity_recorded" for event in result.reasoning_path)
    assert any(event.event == "contradiction_assessed" for event in result.reasoning_path)


def test_shared_space_similarity_is_explained_separately_from_consistency():
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000020",
        text=USRText(text="claim", embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0])),
        image=USRImage(embedding=USREmbedding(model_name="shared", dimension=2, values=[1.0, 0.0])),
    )
    cmref_result = CMREF(
        ProjectionRegistry(2),
        alignment_mode="similarity_only",
    ).reason(usr)
    rr = build_reasoning_representation(cmref_result)

    explanation = ExplainabilityService().explain(rr)

    assert rr.consistency.alignment is None
    assert rr.consistency.score is None
    assert rr.pairwise_alignments == []
    assert rr.pairwise_similarities[0].cosine_similarity == 1.0
    assert rr.contradiction is None
    assert rr.reasoning_score is None
    assert explanation.diagnostic_signals == []
    assert any(event.event == "cosine_similarity_recorded" for event in explanation.reasoning_path)
    assert "semantic similarity, not as consistency or truth" in explanation.explanation


def test_undefined_contradiction_and_consistency_are_explained_as_uncertainty():
    result = ExplainabilityService().explain(make_rr())

    assert result.uncertainty_reasons
    assert "CONTRADICTION_EVALUATOR_UNAVAILABLE" in result.uncertainty_reasons
    assert "INSUFFICIENT_CROSS_MODAL_EVIDENCE" in result.uncertainty_reasons
    assert "uncertain" in result.explanation


def test_contextual_diagnostics_are_not_explained_as_consistency_or_attribution():
    result = ExplainabilityService().explain(
        make_rr(text=True, image=True, contextual=True)
    )

    assert result.diagnostic_signals[0].signal == "temporal_agreement"
    assert result.diagnostic_signals[0].source == "contextual_feature"
    assert "not_classifier_attribution" in result.diagnostic_signals[0].interpretation
    assert all(signal.signal != "consistency_score" for signal in result.diagnostic_signals)
    assert any("CONSISTENCY_EVALUATOR_UNAVAILABLE" == reason for reason in result.uncertainty_reasons)
    assert "not classifier attributions" in result.explanation


def test_calibrated_confidence_and_prediction_are_consumed_without_invention():
    result = ExplainabilityService(
        calibrator=lambda rr: {"prediction": "LIKELY_REAL", "confidence": 0.73}
    ).explain(make_rr(text=True, image=True, contradiction=True))

    assert result.prediction == "LIKELY_REAL"
    assert result.confidence == 0.73
    assert result.confidence_status == "calibrated"
    assert "model prediction is LIKELY_REAL" in result.explanation
    assert "not independent factual verification" in result.explanation


def test_predicted_real_confidence_contract_is_preserved_in_explanation():
    result = ExplainabilityService().explain(
        make_rr(),
        decision_result={
            "prediction": "REAL",
            "confidence": 0.91,
            "status": "CALIBRATED",
        },
    )

    assert result.prediction == "REAL"
    assert result.confidence == 0.91
    assert result.confidence_status == "calibrated"
    assert "prediction is REAL" in result.explanation
    assert "confidence is 0.910" in result.explanation


def test_explainer_rejects_confidence_without_calibrated_status_or_valid_range():
    import pytest

    for result in (
        {"prediction": "FAKE", "confidence": 0.8, "status": "UNAVAILABLE"},
        {"prediction": "FAKE", "confidence": float("nan"), "status": "CALIBRATED"},
        {"prediction": "FAKE", "confidence": 1.1, "status": "CALIBRATED"},
        {
            "prediction": "REAL",
            "confidence": 0.2,
            "calibrated_probability": 0.2,
            "status": "CALIBRATED",
        },
        {"prediction": None, "confidence": 0.8, "status": "CALIBRATED"},
    ):
        with pytest.raises(ValueError):
            ExplainabilityService().explain(make_rr(), decision_result=result)


def test_incomplete_reasoning_evidence_keeps_confidence_unavailable():
    result = ExplainabilityService().explain(make_rr(text=True))

    assert result.confidence is None
    assert result.confidence_status == "unavailable"
    assert "CONFIDENCE_CALIBRATION_UNAVAILABLE" in result.uncertainty_reasons
