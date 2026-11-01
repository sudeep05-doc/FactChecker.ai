from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import Prediction as PackagePrediction
from app.schemas import PredictionType as PackagePredictionType
from app.schemas.verification import (
    InputType,
    Prediction,
    PredictionType,
    ReasoningRepresentation,
    ResponseStatus,
    VerificationRequest,
    VerificationResponse,
)


def test_text_verification_request_generates_request_id() -> None:
    request = VerificationRequest(
        input_type=InputType.TEXT,
        content={"text": "A claim that requires verification."},
    )

    assert isinstance(request.request_id, UUID)
    assert request.content.text == "A claim that requires verification."


def test_file_input_requires_opaque_reference() -> None:
    with pytest.raises(ValidationError, match="file_reference"):
        VerificationRequest(
            input_type=InputType.IMAGE,
            content={"file_name": "claim.png", "mime_type": "image/png"},
        )


def test_response_keeps_prediction_and_confidence_optional() -> None:
    response = VerificationResponse(
        request_id="00000000-0000-4000-8000-000000000000",
        status=ResponseStatus.COMPLETED,
    )

    assert response.prediction is None
    assert response.confidence is None
    assert response.reasoning == {}
    assert Prediction.LIKELY_FAKE.value == "LIKELY_FAKE"


def test_prediction_public_exports_preserve_distinct_label_and_type_contracts() -> None:
    assert PackagePrediction is Prediction
    assert PackagePredictionType is PredictionType
    assert {item.value for item in Prediction} == {
        "LIKELY_FAKE",
        "LIKELY_REAL",
    }
    assert {item.value for item in PredictionType} == {
        "evidence_verification",
        "dataset_classification",
    }
    assert Prediction("LIKELY_FAKE") is Prediction.LIKELY_FAKE
    assert TypeAdapter(Prediction).validate_json('"LIKELY_REAL"') is Prediction.LIKELY_REAL
    assert TypeAdapter(Prediction).dump_json(Prediction.LIKELY_FAKE) == b'"LIKELY_FAKE"'


def test_legacy_prediction_accessor_only_maps_dataset_labels() -> None:
    dataset_result = VerificationResponse(
        request_id="00000000-0000-4000-8000-000000000000",
        status=ResponseStatus.COMPLETED,
        prediction_type=PredictionType.DATASET_CLASSIFICATION,
        evidence_status="not_applicable",
        dataset_prediction="FAKE",
        model_identity="task47/text_only",
        dataset_identity="Fakeddit 2-way distant-supervision label",
        explanation_provenance="dataset_classifier",
    )
    evidence_result = VerificationResponse(
        request_id="00000000-0000-4000-8000-000000000000",
        status=ResponseStatus.COMPLETED,
        verdict="SUPPORTED",
        evidence_status="evaluated",
        explanation_provenance="evidence_evaluator",
    )

    assert dataset_result.prediction is Prediction.LIKELY_FAKE
    assert evidence_result.prediction is None
    assert "prediction" not in dataset_result.model_dump()
    assert dataset_result.model_dump()["dataset_prediction"] == "FAKE"


def test_verification_reasoning_requires_status_for_consistency_measurement() -> None:
    with pytest.raises(ValidationError, match="available evaluator"):
        ReasoningRepresentation(consistency_score=0.8)

    unavailable = ReasoningRepresentation()
    assert unavailable.consistency_score is None
    assert unavailable.consistency_status == "unavailable"
    assert unavailable.consistency_unavailable_reason == "CONSISTENCY_EVALUATOR_UNAVAILABLE"

    measured = ReasoningRepresentation(
        consistency_score=0.8,
        consistency_status="available",
        consistency_evaluator_version="independent-consistency-v1",
        consistency_unavailable_reason=None,
    )
    assert measured.consistency_score == 0.8
