import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_verify_returns_explicit_mock_result() -> None:
    request_id = "00000000-0000-4000-8000-000000000001"
    response = client.post(
        "/api/v1/verify",
        json={
            "request_id": request_id,
            "input_type": "text",
            "content": {"text": "A claim that requires verification."},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": request_id,
        "status": "unavailable",
        "is_mock": True,
        "prediction_type": "evidence_verification",
        "evidence_status": "not_implemented",
        "verdict": None,
        "dataset_prediction": None,
        "model_identity": None,
        "dataset_identity": None,
        "confidence": None,
        "confidence_semantics": "not_available",
        "explanation_provenance": "mock_notice",
        "modality_weights": [],
        "diagnostic_signals": [],
        "reasoning": {},
        "explanation": (
            "Evidence-based factual verification is not implemented. "
            "No verdict or confidence score was produced."
        ),
        "errors": [],
    }


def test_mock_contract_rejects_prediction_or_confidence() -> None:
    from pydantic import ValidationError

    from app.schemas.verification import VerificationResponse

    with pytest.raises(ValidationError):
        VerificationResponse(
            request_id="00000000-0000-4000-8000-000000000001",
            status="unavailable",
            is_mock=True,
            verdict="SUPPORTED",
        )


def test_dataset_classification_contract_requires_dataset_scope() -> None:
    from app.schemas.verification import VerificationResponse

    result = VerificationResponse(
        request_id="00000000-0000-4000-8000-000000000001",
        status="completed",
        is_mock=False,
        prediction_type="dataset_classification",
        evidence_status="not_applicable",
        verdict=None,
        dataset_prediction="FAKE",
        model_identity="task47/text_only",
        dataset_identity="Fakeddit 2-way distant-supervision label",
        confidence=0.82,
        confidence_semantics="uncalibrated_dataset_score",
        explanation_provenance="dataset_classifier",
    )

    assert result.verdict is None


def test_verify_validates_input_before_mock_pipeline() -> None:
    response = client.post(
        "/api/v1/verify",
        json={
            "input_type": "image",
            "content": {"file_name": "claim.png"},
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Request validation failed."}