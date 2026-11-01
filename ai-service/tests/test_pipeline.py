from types import SimpleNamespace
from uuid import UUID

import pytest

from app.cal.schemas import AcquisitionStatus, CALResult
from app.cmrea import ExplainabilityService
from app.cmref import CMREF
from app.cmref.contextual import ContextualFeature
from app.cmref.projection import ProjectionRegistry
from app.pipeline import (
    CallableDecisionCalibration,
    DecisionCalibration,
    FoundationAdapters,
    VerificationPipeline,
)
from app.preprocessing.schemas import PreprocessingStatus
from app.rr.models import ReasoningRepresentation
from app.schemas.verification import InputType, VerificationRequest
from app.usr import USREmbedding, USRImage, USROCR, USRText


REQUEST_ID = UUID("00000000-0000-4000-8000-000000000021")


class FakeAcquisition:
    def __init__(self, input_type="text", failed=False):
        self.input_type = input_type
        self.failed = failed

    def acquire(self, request):
        return CALResult(
            request_id=request.request_id,
            input_type=self.input_type,
            source="mock",
            text_content="claim",
            acquisition_status=(
                AcquisitionStatus.FAILED if self.failed else AcquisitionStatus.COMPLETED
            ),
        )


class FakePreprocessing:
    def __init__(self, failed=False):
        self.failed = failed

    def process(self, content):
        return SimpleNamespace(
            preprocessing_status=(
                PreprocessingStatus.FAILED if self.failed else PreprocessingStatus.COMPLETED
            ),
            errors=[],
        )


def request(input_type=InputType.TEXT):
    content = (
        {"text": "claim"}
        if input_type == InputType.TEXT
        else {"url": "https://www.youtube.com/watch?v=example"}
        if input_type == InputType.YOUTUBE_URL
        else {"file_reference": "mock"}
    )
    return VerificationRequest(request_id=REQUEST_ID, input_type=input_type, content=content)


def embedding(values=(1.0, 0.0)):
    return USREmbedding(model_name="mock", dimension=2, values=list(values))


def text_representation(_prepared):
    return USRText(text="claim", embedding=embedding())


def image_representation(_prepared):
    return USRImage(image_paths=["mock.png"], embedding=embedding())


def ocr_representation(_prepared):
    return USROCR(extracted_text="claim")


def pipeline(
    foundation,
    decision=None,
    acquisition=None,
    preprocessing=None,
    cmrea=None,
    contextual_provider=None,
):
    return VerificationPipeline(
        acquisition=acquisition or FakeAcquisition(),
        preprocessing=preprocessing or FakePreprocessing(),
        foundation=foundation,
        cmref=CMREF(
            ProjectionRegistry(2),
            contextual_provider=contextual_provider,
        ),
        decision=decision,
        cmrea=cmrea,
    )


def test_text_only_and_image_only_are_supported_without_model_downloads():
    text_result = pipeline(FoundationAdapters(text=text_representation)).analyze(request())
    image_result = pipeline(
        FoundationAdapters(image=image_representation),
        acquisition=FakeAcquisition("image"),
    ).analyze(request(InputType.IMAGE))

    assert "text" in text_result.available_modalities
    assert "image" in image_result.available_modalities
    assert text_result.prediction is None
    assert text_result.calibrated_confidence is None


def test_text_image_and_ocr_flow_through_usr_and_cmref():
    result = pipeline(
        FoundationAdapters(
            multimodal=lambda prepared: {
                "text": text_representation(prepared),
                "image": image_representation(prepared),
                "ocr": ocr_representation(prepared),
            }
        )
    ).analyze(request())

    assert set(result.available_modalities) == {"text", "image", "ocr"}
    assert result.evidence is not None
    assert result.evidence["pairwise_similarities"][0]["left_modality"] == "image"
    assert result.evidence["pairwise_similarities"][0]["right_modality"] == "text"
    assert result.prediction is None


def test_pipeline_serializes_context_as_diagnostic_and_consistency_as_unavailable():
    result = pipeline(
        FoundationAdapters(
            multimodal=lambda prepared: {
                "text": text_representation(prepared),
                "image": image_representation(prepared),
            }
        ),
        contextual_provider=lambda _: [
            ContextualFeature("temporal_agreement", 0.8, "context-v1", {})
        ],
    ).analyze(request())

    assert result.evidence["consistency"]["score"] is None
    assert result.evidence["consistency"]["contextual"] is None
    assert result.evidence["consistency"]["status"] == "unavailable"
    assert result.evidence["consistency"]["unavailable_reason"] == "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    assert result.evidence["contextual_features"][0]["name"] == "temporal_agreement"
    assert any(
        signal["signal"] == "temporal_agreement"
        and "not_classifier_attribution" in signal["interpretation"]
        for signal in result.diagnostic_signals
    )
    assert "CONSISTENCY_EVALUATOR_UNAVAILABLE" in result.uncertainty


def test_missing_modality_is_recorded_without_fake_evidence():
    result = pipeline(FoundationAdapters(text=text_representation)).analyze(request())

    assert result.prediction is None
    assert result.calibrated_confidence is None
    assert "CALIBRATION_UNAVAILABLE" in result.uncertainty
    assert result.evidence["consistency"]["score"] is None


def test_preprocessing_failure_stops_downstream_stages():
    result = pipeline(
        FoundationAdapters(text=text_representation),
        preprocessing=FakePreprocessing(failed=True),
    ).analyze(request())

    assert result.status.value == "failed"
    assert result.errors[-1].code == "PREPROCESSING_FAILURE"
    assert result.prediction is None


def test_invalid_embedding_is_not_converted_to_a_prediction():
    def invalid(_prepared):
        raise ValueError("embedding values must be finite")

    result = pipeline(FoundationAdapters(text=invalid)).analyze(request())

    assert result.prediction is None
    assert any(issue.code == "MODEL_INFERENCE_FAILURE" for issue in result.errors)
    assert "MODEL_INFERENCE_FAILURE" in result.uncertainty


def test_insufficient_embeddings_preserve_null_scores():
    result = pipeline(
        FoundationAdapters(multimodal=lambda prepared: {"text": USRText(text="claim")})
    ).analyze(request())

    assert result.evidence["consistency"]["alignment"] is None
    assert result.evidence["consistency"]["score"] is None
    assert result.prediction is None
    assert result.calibrated_confidence is None


def test_contradiction_unavailable_is_explicit():
    result = pipeline(FoundationAdapters(text=text_representation)).analyze(request())

    assert "CONTRADICTION_EVALUATOR_UNAVAILABLE" in result.uncertainty
    assert result.evidence["contradiction"] is None


def test_calibration_unavailable_is_not_a_fabricated_decision():
    result = pipeline(FoundationAdapters(text=text_representation)).analyze(request())

    assert result.prediction is None
    assert result.calibrated_confidence is None
    assert "CALIBRATION_UNAVAILABLE" in result.uncertainty
    assert not any(issue.code == "CALIBRATION_UNAVAILABLE" for issue in result.errors)


def test_injected_calibrated_decision_is_consumed():
    decision = CallableDecisionCalibration(
        lambda rr: {"prediction": "LIKELY_REAL", "confidence": 0.73, "status": "calibrated", "reason": ""}
    )
    result = pipeline(FoundationAdapters(text=text_representation), decision=decision).analyze(request())

    assert result.prediction == "LIKELY_REAL"
    assert result.calibrated_confidence == 0.73


def test_youtube_description_uses_explicit_text_adapter_only():
    seen = {}

    class YouTubeAcquisition:
        def acquire(self, request_value):
            return CALResult(
                request_id=request_value.request_id,
                input_type="youtube_url",
                source="https://www.youtube.com/watch?v=example",
                text_content="The video description only.",
                metadata={"downloaded": False},
                acquisition_status=AcquisitionStatus.COMPLETED,
            )

    def description_encoder(prepared):
        seen["description"] = prepared.cleaned_text
        return text_representation(prepared)

    service = VerificationPipeline(
        acquisition=YouTubeAcquisition(),
        foundation=FoundationAdapters(youtube_description=description_encoder),
        cmref=CMREF(ProjectionRegistry(2)),
    )
    result = service.analyze(request(InputType.YOUTUBE_URL))

    assert seen["description"] == "The video description only."
    assert result.status.value == "completed"
    assert result.available_modalities == ["text"]
    assert {"youtube_audio", "youtube_video"} <= set(result.omitted_modalities)
    assert result.warnings[0].code == "YOUTUBE_DESCRIPTION_ONLY"
    assert result.errors == []


def test_youtube_description_without_adapter_fails_explicitly():
    result = pipeline(
        FoundationAdapters(text=text_representation),
        acquisition=FakeAcquisition("youtube_url"),
    ).analyze(request(InputType.YOUTUBE_URL))

    assert result.status.value == "failed"
    assert result.prediction is None
    assert any(
        issue.code == "YOUTUBE_DESCRIPTION_ADAPTER_UNAVAILABLE"
        for issue in result.errors
    )


def test_cmrea_receives_rr_and_pipeline_is_deterministically_structured():
    seen = {}

    class SpyCMREA(ExplainabilityService):
        def explain(self, reasoning_representation, calibration=None):
            seen["rr"] = reasoning_representation
            seen["calibration"] = calibration
            return super().explain(reasoning_representation, calibration)

    result = pipeline(
        FoundationAdapters(text=text_representation),
        cmrea=SpyCMREA(),
    ).analyze(request())

    assert isinstance(seen["rr"], ReasoningRepresentation)
    assert seen["calibration"]["confidence"] is None
    assert list(result.model_dump()) == [
        "request_id",
        "status",
        "available_modalities",
        "omitted_modalities",
        "prediction",
        "calibrated_confidence",
        "reasoning_score",
        "modality_weights",
        "diagnostic_signals",
        "reasoning_path",
        "explanation",
        "uncertainty",
        "evidence",
        "errors",
        "warnings",
        "model_versions",
        "configuration_versions",
        "processing_metadata",
    ]


def test_partial_multimodal_input_keeps_successful_modalities():
    def failing_ocr(_prepared):
        raise RuntimeError("OCR unavailable")

    result = pipeline(
        FoundationAdapters(image=image_representation, ocr=failing_ocr),
        acquisition=FakeAcquisition("image"),
    ).analyze(request(InputType.IMAGE))

    assert "image" in result.available_modalities
    assert "ocr" in result.omitted_modalities
    assert result.prediction is None


def test_acquisition_failure_is_structured():
    result = pipeline(
        FoundationAdapters(text=text_representation),
        acquisition=FakeAcquisition(failed=True),
    ).analyze(request())

    assert result.status.value == "failed"
    assert result.errors[-1].code == "ACQUISITION_FAILURE"


def test_decision_boundary_does_not_use_reasoning_scores():
    decision = DecisionCalibration()
    rr = object.__new__(ReasoningRepresentation)
    assert decision.decide(rr).prediction is None
    assert decision.decide(rr).confidence is None
