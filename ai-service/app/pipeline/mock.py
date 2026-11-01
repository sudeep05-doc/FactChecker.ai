"""Temporary mock implementation of the verification pipeline."""

from app.schemas.verification import (
    EvidenceStatus,
    PredictionType,
    ResponseStatus,
    VerificationRequest,
    VerificationResponse,
)


class MockVerificationPipeline:
    """Return a contract-valid result without loading models or inferring."""

    def analyze(self, request: VerificationRequest) -> VerificationResponse:
        return VerificationResponse(
            request_id=request.request_id,
            status=ResponseStatus.UNAVAILABLE,
            is_mock=True,
            prediction_type=PredictionType.EVIDENCE_VERIFICATION,
            evidence_status=EvidenceStatus.NOT_IMPLEMENTED,
            verdict=None,
            dataset_prediction=None,
            model_identity=None,
            dataset_identity=None,
            confidence=None,
            confidence_semantics="not_available",
            explanation_provenance="mock_notice",
            modality_weights=[],
            diagnostic_signals=[],
            reasoning={},
            explanation=(
                "Evidence-based factual verification is not implemented. "
                "No verdict or confidence score was produced."
            ),
        )