from datetime import datetime, timezone
from uuid import uuid4

import pytest

import pytest

from app.cmrea import ExplainabilityService
from app.cmref import CMREF
from app.cmref.contextual import ContextualFeature
from app.cmref.projection import ProjectionRegistry
from app.decision import (
    DecisionCalibrationService,
    DecisionLifecycle,
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    extract_features,
)
from app.pipeline import DecisionCalibrationAdapter
from app.rr import build_reasoning_representation
from app.rr.models import (
    RRConsistencyRecord,
    RRNumericalStability,
    ReasoningRepresentation,
)
from app.usr import USREmbedding, USRText, UnifiedSemanticRepresentationBuilder


def make_rr(*, multimodal=False, missing=False):
    kwargs = {}
    text = USRText(
        text="claim",
        embedding=USREmbedding(model_name="text", dimension=2, values=[1.0, 0.0]),
    )
    if multimodal:
        kwargs["image"] = __import__("app.usr", fromlist=["USRImage"]).USRImage(
            embedding=USREmbedding(model_name="image", dimension=2, values=[0.0, 1.0])
        )
    usr = UnifiedSemanticRepresentationBuilder().build(str(uuid4()), text=text, **kwargs)
    return build_reasoning_representation(CMREF(ProjectionRegistry(2)).reason(usr))


def synthetic_features(service):
    rr = make_rr(multimodal=True)
    first = service.extract(rr)
    second = service.extract(make_rr())
    return [first, second, first, second], ["REAL", "FAKE", "REAL", "FAKE"]


def test_decision_service_starts_unfitted_and_fails_cleanly_before_training():
    service = DecisionCalibrationService()
    result = service.decide(make_rr())

    assert service.lifecycle == DecisionLifecycle.UNFITTED
    assert result.lifecycle == DecisionLifecycle.UNFITTED
    assert result.prediction is None
    assert result.raw_probability is None
    assert result.confidence is None
    assert result.reason == "DECISION_UNFITTED"
    with pytest.raises(RuntimeError, match="UNFITTED"):
        service.classifier.predict([[0.0]])


def test_features_have_fixed_order_schema_and_presence_missingness():
    vector = extract_features(make_rr())

    assert vector.schema_version == FEATURE_SCHEMA_VERSION
    assert vector.names == FEATURE_NAMES
    assert len(vector.values) == len(FEATURE_NAMES)
    assert vector.missing["consistency_alignment"] is True
    assert vector.values[vector.names.index("consistency_alignment_present")] == 0.0
    assert vector.provenance["reasoning_score"] == "rr.reasoning_score"


def test_present_zero_is_distinguishable_from_missing():
    rr = make_rr()
    vector = extract_features(rr)
    index = vector.names.index("consistency_alignment")
    present_index = vector.names.index("consistency_alignment_present")

    assert vector.values[index] == 0.0
    assert vector.missing["consistency_alignment"] is True
    assert vector.values[present_index] == 0.0


def test_raw_contextual_aggregate_is_not_a_consistency_predictor():
    usr = UnifiedSemanticRepresentationBuilder().build(
        str(uuid4()),
        text=USRText(
            text="claim",
            embedding=USREmbedding(model_name="text", dimension=2, values=[1.0, 0.0]),
        ),
    )
    rr = build_reasoning_representation(
        CMREF(
            ProjectionRegistry(2),
            contextual_provider=lambda _: [
                ContextualFeature("temporal_agreement", 0.8, "context-v1", {})
            ],
        ).reason(usr)
    )

    vector = extract_features(rr)

    assert rr.contextual_features[0].value == 0.8
    assert rr.consistency.contextual is None
    assert vector.missing["consistency_contextual"] is True
    assert vector.values[vector.names.index("consistency_contextual_present")] == 0.0


def test_classifier_rejects_empty_invalid_labels_and_malformed_features():
    service = DecisionCalibrationService()
    with pytest.raises(ValueError, match="must not be empty"):
        service.fit([], [])
    vectors, labels = synthetic_features(service)
    with pytest.raises(ValueError, match="REAL or FAKE"):
        service.fit(vectors, ["MAYBE"] * len(vectors))
    with pytest.raises(ValueError, match="finite"):
        service.classifier.fit([[float("nan")], [0.0]], ["REAL", "FAKE"])
    with pytest.raises(ValueError, match="dimensions"):
        service.classifier.fit([[0.0], [0.0, 1.0]], ["REAL", "FAKE"])


def test_fit_predict_and_probability_use_canonical_labels_and_metadata():
    service = DecisionCalibrationService()
    vectors, labels = synthetic_features(service)
    service.fit(vectors, labels)
    result = service.decide(make_rr(multimodal=True))

    assert service.lifecycle == DecisionLifecycle.TRAINED
    assert result.lifecycle == DecisionLifecycle.TRAINED
    assert result.prediction in {"REAL", "FAKE"}
    assert result.raw_probability is not None
    assert 0.0 <= result.raw_probability <= 1.0
    assert result.confidence is None
    assert result.status == "CALIBRATION_UNAVAILABLE"
    assert result.classifier_metadata["classifier_type"].endswith("LogisticRegression")
    assert result.classifier_metadata["training_sample_count"] == 4
    assert result.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert result.provenance["features"]["schema_version"] == FEATURE_SCHEMA_VERSION


def test_calibration_requires_fitted_classifier_and_validation_data():
    service = DecisionCalibrationService()
    vectors, labels = synthetic_features(service)
    with pytest.raises(RuntimeError, match="fitted"):
        service.calibrate(vectors, labels)
    service.fit(vectors, labels)
    with pytest.raises(ValueError, match="must not be empty"):
        service.calibrate([], [])
    with pytest.raises(ValueError, match="both REAL and FAKE"):
        service.calibrate(vectors, ["REAL"] * len(vectors))


def test_calibrated_probability_and_confidence_only_appear_after_validation_calibration():
    service = DecisionCalibrationService()
    vectors, labels = synthetic_features(service)
    service.fit(vectors, labels)
    before = service.decide(make_rr())
    service.calibrate(vectors, labels)
    after = service.decide(make_rr())

    assert before.calibrated_probability is None
    assert before.confidence is None
    assert after.lifecycle == DecisionLifecycle.READY
    assert after.status == "CALIBRATED"
    assert after.calibrated_probability is not None
    expected_confidence = (
        after.calibrated_probability
        if after.prediction == "FAKE"
        else 1.0 - after.calibrated_probability
    )
    assert after.confidence == pytest.approx(expected_confidence)
    assert 0.0 <= after.confidence <= 1.0
    assert after.calibration_metadata["method"] == "sigmoid"


@pytest.mark.parametrize(
    ("probability_fake", "expected_prediction", "expected_confidence"),
    [
        (0.0, "REAL", 1.0),
        (0.2, "REAL", 0.8),
        (0.5, "FAKE", 0.5),
        (0.8, "FAKE", 0.8),
        (1.0, "FAKE", 1.0),
    ],
)
def test_decision_confidence_is_calibrated_probability_of_predicted_class(
    probability_fake, expected_prediction, expected_confidence
):
    class FixedClassifier:
        is_fitted = True

        def predict_proba(self, _features):
            return [0.4]

        def metadata(self, _schema):
            return {}

    class FixedCalibrator:
        metadata = {"method": "test"}

        def predict_fake_probability(self, _probability):
            return probability_fake

    service = DecisionCalibrationService(classifier=FixedClassifier())
    service.calibrator = FixedCalibrator()
    result = service.decide(make_rr())

    assert result.prediction == expected_prediction
    assert result.raw_probability == pytest.approx(0.4)
    assert result.calibrated_probability == pytest.approx(probability_fake)
    assert result.confidence == pytest.approx(expected_confidence)


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01])
def test_decision_rejects_malformed_classifier_probabilities(probability):
    class FixedClassifier:
        is_fitted = True

        def predict_proba(self, _features):
            return [probability]

    service = DecisionCalibrationService(classifier=FixedClassifier())

    with pytest.raises(ValueError, match="finite and in \\[0, 1\\]"):
        service.decide(make_rr())


@pytest.mark.parametrize("values", [[], None, [float("nan")], [1.01]])
def test_decision_rejects_unavailable_or_malformed_probability_outputs(values):
    class FixedClassifier:
        is_fitted = True

        def predict_proba(self, _features):
            return values

    service = DecisionCalibrationService(classifier=FixedClassifier())

    with pytest.raises(ValueError, match="probability"):
        service.decide(make_rr())


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01])
def test_decision_rejects_malformed_calibrated_probabilities(probability):
    class FixedClassifier:
        is_fitted = True

        def predict_proba(self, _features):
            return [0.4]

    class FixedCalibrator:
        metadata = {}

        def predict_fake_probability(self, _probability):
            return probability

    service = DecisionCalibrationService(classifier=FixedClassifier())
    service.calibrator = FixedCalibrator()

    with pytest.raises(ValueError, match="calibrated FAKE probability"):
        service.decide(make_rr())


def test_pipeline_adapter_exposes_structured_decision_result():
    service = DecisionCalibrationService()
    vectors, labels = synthetic_features(service)
    service.fit(vectors, labels)
    adapter = DecisionCalibrationAdapter(service)

    result = adapter.decide(make_rr())

    assert result.prediction in {"REAL", "FAKE"}
    assert result.raw_probability is not None
    assert result.confidence is None
    assert result.status == "CALIBRATION_UNAVAILABLE"
    assert result.metadata["lifecycle"] == "trained"


def test_service_predict_probability_and_metadata_exports_are_explicit():
    service = DecisionCalibrationService()
    vectors, labels = synthetic_features(service)
    service.fit(vectors, labels)

    assert set(service.predict(vectors)) <= {"REAL", "FAKE"}
    assert all(0.0 <= value <= 1.0 for value in service.predict_proba(vectors))
    assert service.metadata()["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    with pytest.raises(RuntimeError, match="unavailable"):
        service.predict_proba(vectors, calibrated=True)


def test_cmrea_preserves_unavailable_calibration_and_does_not_invent_confidence():
    rr = make_rr()
    result = ExplainabilityService().explain(
        rr,
        calibration={
            "prediction": "REAL",
            "raw_probability": 0.2,
            "calibrated_probability": None,
            "confidence": None,
            "status": "CALIBRATION_UNAVAILABLE",
            "reason": "CALIBRATION_UNAVAILABLE",
            "metadata": {"lifecycle": "trained"},
        },
    )

    assert result.prediction == "REAL"
    assert result.confidence is None
    assert result.confidence_status == "unavailable"
    assert result.processing_metadata["decision_status"] == "CALIBRATION_UNAVAILABLE"
    assert "CONFIDENCE_CALIBRATION_UNAVAILABLE" in result.uncertainty_reasons


def test_decision_metadata_does_not_create_research_metrics():
    service = DecisionCalibrationService()
    assert service.classifier.metadata(FEATURE_SCHEMA_VERSION)["training_status"] == "unfitted"
    assert "accuracy" not in service.classifier.metadata(FEATURE_SCHEMA_VERSION)
