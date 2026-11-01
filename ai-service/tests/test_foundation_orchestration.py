from uuid import UUID

import pytest

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.foundation import FoundationAdapterSet, UnifiedFoundationOrchestrator
from app.models.image_encoder_schema import ImageEncodingResult
from app.models.ocr_schema import OCRDetection, OCRResult, OCRStatus
from app.models.text_encoder_schema import TextEncodingResult
from app.models.whisper_schema import TranscriptionResult, TranscriptionSegment, TranscriptionStatus
from app.usr import USRAudioTranscript, USRImage, USROCR, USRText, USREmbedding, USRVideo


REQUEST_ID = UUID("00000000-0000-4000-8000-000000000023")


def text_output():
    return TextEncodingResult(
        model_name="text-test",
        embedding_dimension=2,
        embedding=[1.0, 0.0],
        normalized=True,
        processing_metadata={"device": "cpu", "preprocessing": "clean"},
    )


def image_output():
    return ImageEncodingResult.available(
        request_id=REQUEST_ID,
        model_name="image-test",
        checkpoint="openai",
        embedding_dimension=2,
        embedding=[1.0, 0.0],
        image_path="image.png",
        normalized=True,
        processing_metadata={"device": "cpu"},
    )


def ocr_output():
    return OCRResult(
        request_id=REQUEST_ID,
        extracted_text="caption",
        raw_text=" caption ",
        detections=[OCRDetection(index=0, text="caption", raw_text=" caption ", normalized_text="caption", confidence=0.8, bounding_box=[[0.0, 0.0]])],
        ocr_status=OCRStatus.COMPLETED,
        language_configuration=["en"],
        processing_metadata={"device": "cpu"},
    )


def transcript_output():
    return TranscriptionResult(
        request_id=REQUEST_ID,
        transcript="spoken claim",
        raw_transcript=" spoken claim ",
        normalized_transcript="spoken claim",
        detected_language="en",
        segments=[TranscriptionSegment(index=0, start_seconds=0.0, end_seconds=1.0, text="spoken claim")],
        model="tiny",
        transcription_status=TranscriptionStatus.COMPLETED,
        processing_metadata={"device": "cpu"},
    )


def test_text_only_and_image_only_assembly():
    orchestrator = UnifiedFoundationOrchestrator()

    text = orchestrator.assemble(REQUEST_ID, text_output=text_output(), text_content="written claim")
    image = orchestrator.assemble(REQUEST_ID, image_output=image_output())

    assert text.active_modalities == ["text"]
    assert image.active_modalities == ["image"]
    assert text.usr.text.embedding.model_name == "text-test"
    assert image.usr.image.embedding.model_name == "image-test"
    assert text.usr.ocr is None


def test_ocr_audio_and_video_transcript_only_remain_structured_evidence():
    orchestrator = UnifiedFoundationOrchestrator()

    ocr = orchestrator.assemble(REQUEST_ID, ocr_output=ocr_output())
    audio = orchestrator.assemble(REQUEST_ID, audio_output=transcript_output())
    video = orchestrator.assemble(REQUEST_ID, video_output=transcript_output())

    assert ocr.active_modalities == ["ocr"]
    assert audio.active_modalities == ["audio_transcript"]
    assert video.active_modalities == ["video_transcript"]
    assert "embedding" not in ocr.usr.ocr.metadata
    assert audio.usr.audio.segments[0]["start_seconds"] == 0.0
    assert video.usr.video.transcript_segments[0]["end_seconds"] == 1.0


def test_text_image_ocr_transcript_coexist_and_cmref_receives_usr():
    seen = {}

    class SpyCMREF(CMREF):
        def reason(self, usr):
            seen["usr"] = usr
            return super().reason(usr)

    result = UnifiedFoundationOrchestrator(cmref=SpyCMREF(ProjectionRegistry(2))).assemble(
        REQUEST_ID,
        text_output=text_output(),
        text_content="written claim",
        image_output=image_output(),
        ocr_output=ocr_output(),
        audio_output=transcript_output(),
    )

    assert result.usr is seen["usr"]
    assert result.active_modalities == ["text", "image", "ocr", "audio_transcript"]
    assert result.cmref_result is not None
    assert len(result.cmref_result.pairwise_similarities) == 1
    assert result.cmref_result.contradiction is None


def test_missing_modalities_are_omitted_without_negative_evidence():
    result = UnifiedFoundationOrchestrator().assemble(REQUEST_ID, text_output=text_output(), text_content="claim")

    assert result.omitted_modalities == ["image", "ocr", "audio_transcript", "video_transcript"]
    assert result.usr.image is None
    assert result.processing_metadata["textual_evidence_embedding"] is False


def test_failed_modality_does_not_discard_successful_modalities():
    failed_image = ImageEncodingResult.unavailable(
        request_id=REQUEST_ID,
        model_name="image-test",
        checkpoint="openai",
        errors=[],
    )
    result = UnifiedFoundationOrchestrator().assemble(
        REQUEST_ID,
        text_output=text_output(),
        text_content="claim",
        image_output=failed_image,
        ocr_output=ocr_output(),
    )

    assert result.active_modalities == ["text", "ocr"]
    assert result.failed_modalities == ["image"]
    assert result.usr.text is not None
    assert result.usr.ocr is not None


def test_adapter_failures_are_isolated_and_provenance_is_recorded():
    calls = []
    orchestrator = UnifiedFoundationOrchestrator(adapters=FoundationAdapterSet(
        text=lambda value: calls.append("text") or text_output(),
        image=lambda value: (_ for _ in ()).throw(RuntimeError("image failed")),
    ))

    result = orchestrator.run(
        REQUEST_ID,
        text_input="raw text",
        image_input="raw image",
        text_content="claim",
    )

    assert calls == ["text"]
    assert result.active_modalities == ["text"]
    assert result.failed_modalities == []
    assert result.errors[0].modality == "image"
    assert result.provenance["text"]["device"] == "cpu"


def test_invalid_text_output_does_not_create_fabricated_embedding():
    invalid = TextEncodingResult(
        model_name="text-test",
        status="unavailable",
        error_code="TEXT_ENCODING_UNAVAILABLE",
    )

    result = UnifiedFoundationOrchestrator().assemble(REQUEST_ID, text_output=invalid, text_content="claim")

    assert result.usr is None
    assert result.failed_modalities == ["text"]
    assert result.errors[0].code == "TEXT_ENCODING_UNAVAILABLE"


def test_optional_textual_evidence_embedding_is_explicitly_not_silent():
    result = UnifiedFoundationOrchestrator().run(
        REQUEST_ID,
        ocr_input=ocr_output(),
        embed_textual_evidence=True,
    )

    assert result.usr.ocr is not None
    assert result.processing_metadata["textual_evidence_embedding"] is False
    assert result.warnings[0].code == "TEXTUAL_EVIDENCE_EMBEDDING_UNSUPPORTED"


def test_deterministic_modality_order_and_provenance():
    result = UnifiedFoundationOrchestrator().assemble(
        REQUEST_ID,
        audio_output=transcript_output(),
        ocr_output=ocr_output(),
        image_output=image_output(),
        text_output=text_output(),
        text_content="claim",
    )

    assert result.active_modalities == ["text", "image", "ocr", "audio_transcript"]
    assert list(result.provenance) == result.active_modalities
    assert result.usr.preprocessing_metadata == {}


def test_video_transcript_output_is_preserved_as_video_evidence():
    result = UnifiedFoundationOrchestrator().assemble(REQUEST_ID, video_output=transcript_output())

    assert isinstance(result.usr.video, USRVideo)
    assert result.usr.video.transcript == "spoken claim"
    assert result.usr.video.transcript_segments[0]["index"] == 0


def test_no_valid_outputs_does_not_call_cmref_or_fabricate_usr():
    class FailingCMREF:
        def reason(self, usr):
            raise AssertionError("CMREF should not receive empty USR")

    result = UnifiedFoundationOrchestrator(cmref=FailingCMREF()).assemble(REQUEST_ID)

    assert result.usr is None
    assert result.cmref_result is None
    assert result.active_modalities == []
