import io
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.config.settings import Settings
from app.models import TranscriptionStatus, WhisperTranscriber
from app.preprocessing.audio import AudioPreprocessor
from app.preprocessing.audio_schema import AudioPreprocessingStatus
from app.preprocessing.video_schema import VideoPreprocessingResult, VideoPreprocessingStatus
from app.rr import build_reasoning_representation
from app.usr import USRAudioTranscript, USRImage, USROCR, USRText, UnifiedSemanticRepresentationBuilder, USREmbedding
from tests.test_whisper_transcriber import make_audio_result, make_short_wav


class FakeWhisper:
    def __init__(self, output=None):
        self.output = output or {
            "text": " Hello world ",
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 0.8, "text": " Hello "},
                {"start": 0.8, "end": 1.4, "text": "world"},
            ],
        }
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append((audio, options))
        return self.output


def make_transcriber(model=None, **settings_overrides):
    model = model or FakeWhisper()
    loads = []

    def factory(model_variant, device):
        loads.append((model_variant, device))
        return model

    settings = Settings(whisper_device="cpu", whisper_model_variant="tiny", **settings_overrides)
    return WhisperTranscriber(settings=settings, model_factory=factory), model, loads


def test_valid_transcription_preserves_segments_and_language(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    audio_result = make_audio_result(audio_path)
    transcriber, model, loads = make_transcriber(whisper_language="en", whisper_task="transcribe")

    result = transcriber.transcribe(audio_result)

    assert result.transcription_status == TranscriptionStatus.COMPLETED
    assert result.transcript == "Hello world"
    assert result.raw_transcript == "Hello world"
    assert [segment.index for segment in result.segments] == [0, 1]
    assert result.segments[0].start_seconds == pytest.approx(0.0)
    assert result.segments[1].end_seconds == pytest.approx(1.4)
    assert result.detected_language == "en"
    assert result.model == "tiny"
    assert result.processing_metadata["backend"] == "openai-whisper"
    assert result.processing_metadata["whisper_confidence_semantics"] == "transcription_metadata_only"
    assert loads == [("tiny", "cpu")]
    assert len(model.calls) == 1


def test_model_is_lazy_and_reused_with_configured_language_and_task(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    audio_result = make_audio_result(audio_path)
    transcriber, model, loads = make_transcriber(whisper_language="fr", whisper_task="translate")

    assert transcriber.is_loaded is False
    transcriber.transcribe(audio_result)
    transcriber.transcribe(audio_result)

    assert transcriber.is_loaded is True
    assert loads == [("tiny", "cpu")]
    assert model.calls[0][1]["language"] == "fr"
    assert model.calls[0][1]["task"] == "translate"
    assert len(model.calls) == 2


def test_empty_and_missing_audio_are_structured_without_model_loading(tmp_path: Path):
    transcriber, _, loads = make_transcriber()
    missing = transcriber.transcribe(tmp_path / "missing.wav")
    empty = transcriber.transcribe(b"")

    assert missing.errors[0].code == "AUDIO_NOT_FOUND"
    assert empty.errors[0].code == "AUDIO_EMPTY"
    assert loads == []


def test_invalid_audio_and_unavailable_model_are_not_negative_evidence(tmp_path: Path):
    invalid_path = tmp_path / "invalid.wav"
    invalid_path.write_bytes(b"not audio")
    transcriber, _, loads = make_transcriber()
    invalid = transcriber.transcribe(invalid_path)

    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    unavailable, _, unavailable_loads = make_transcriber()
    unavailable.model_factory = lambda *args: (_ for _ in ()).throw(RuntimeError("weights unavailable"))
    unavailable_result = unavailable.transcribe(make_audio_result(audio_path))

    assert invalid.errors[0].code == "INVALID_AUDIO"
    assert unavailable_result.errors[0].code == "TRANSCRIPTION_UNAVAILABLE"
    assert loads == []
    assert unavailable_loads == []
    assert all("FAKE" not in issue.code for issue in unavailable_result.errors)


def test_no_speech_is_explicit_warning_not_negative_evidence(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    model = FakeWhisper({"text": "", "language": "en", "segments": []})
    transcriber, _, _ = make_transcriber(model)

    result = transcriber.transcribe(make_audio_result(audio_path))

    assert result.transcription_status == TranscriptionStatus.COMPLETED
    assert result.transcript == ""
    assert result.warnings[0].code == "AUDIO_NO_SPEECH"
    assert result.processing_metadata["whisper_confidence_semantics"] == "transcription_metadata_only"


def test_timestamp_unavailable_remains_null_and_order_is_deterministic(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    model = FakeWhisper({"text": "ordered", "segments": [{"text": "ordered"}]})
    transcriber, _, _ = make_transcriber(model)

    result = transcriber.transcribe(make_audio_result(audio_path))

    assert result.segments[0].index == 0
    assert result.segments[0].start_seconds is None
    assert result.segments[0].end_seconds is None
    assert result.processing_metadata["timestamp_semantics"] == "model_segments_only"


def test_long_audio_chunking_preserves_offsets(tmp_path: Path):
    audio_path = tmp_path / "long.wav"
    with wave.open(str(audio_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(np.zeros(32000, dtype=np.int16).tobytes())
    model = FakeWhisper({"text": "part", "language": "en", "segments": [{"start": 0.0, "end": 0.5, "text": "part"}]})
    transcriber, _, _ = make_transcriber(model, whisper_chunk_seconds=1)

    result = transcriber.transcribe(make_audio_result(audio_path))

    assert result.processing_metadata["chunk_count"] == 2
    assert [segment.start_seconds for segment in result.segments] == [0.0, 1.0]
    assert [segment.index for segment in result.segments] == [0, 1]


def test_raw_wav_bytes_are_supported(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    raw_bytes = audio_path.read_bytes()
    transcriber, _, _ = make_transcriber()

    result = transcriber.transcribe(raw_bytes)

    assert result.transcription_status == TranscriptionStatus.COMPLETED


def test_video_audio_pathway_reuses_extracted_audio(tmp_path: Path):
    audio_path = tmp_path / "extracted.wav"
    make_short_wav(audio_path)
    video = VideoPreprocessingResult(
        request_id="00000000-0000-4000-8000-000000000023",
        input_type="video",
        source="video.mp4",
        extracted_audio_path=str(audio_path),
        duration_seconds=0.1,
        preprocessing_status=VideoPreprocessingStatus.COMPLETED,
    )
    transcriber, _, _ = make_transcriber()

    result = transcriber.transcribe_video(video)

    assert result.transcription_status == TranscriptionStatus.COMPLETED
    assert result.modality == "video_transcript"
    assert result.processing_metadata["video_speech_pathway"] == "video_to_extracted_audio_to_whisper"


def test_video_without_extracted_audio_is_structured():
    video = VideoPreprocessingResult(
        request_id="00000000-0000-4000-8000-000000000023",
        input_type="video",
        source="video.mp4",
        preprocessing_status=VideoPreprocessingStatus.COMPLETED,
    )
    transcriber, _, loads = make_transcriber()

    result = transcriber.transcribe_video(video)

    assert result.errors[0].code == "VIDEO_AUDIO_UNAVAILABLE"
    assert loads == []


def test_transcript_usr_boundary_preserves_evidence_without_embedding(tmp_path: Path):
    audio_path = tmp_path / "sample.wav"
    make_short_wav(audio_path)
    transcriber, _, _ = make_transcriber()

    usr_audio = transcriber.to_usr_audio(make_audio_result(audio_path))
    usr_video = transcriber.to_usr_video(VideoPreprocessingResult(
        request_id="00000000-0000-4000-8000-000000000023",
        input_type="video",
        source="video.mp4",
        extracted_audio_path=str(audio_path),
        preprocessing_status=VideoPreprocessingStatus.COMPLETED,
    ))

    assert usr_audio is not None
    assert usr_audio.segments[0]["index"] == 0
    assert "embedding" not in usr_audio.metadata
    assert usr_video is not None
    assert usr_video.transcript_segments[0]["start_seconds"] == 0.0


def test_audio_transcript_text_image_ocr_evidence_coexists_without_cmref_changes():
    audio = USRAudioTranscript(transcript="spoken claim", segments=[{"index": 0, "start_seconds": 0.0, "end_seconds": 1.0, "text": "spoken claim"}])
    text = USRText(text="written claim", embedding=USREmbedding(model_name="text", dimension=2, values=[1.0, 0.0]))
    image = USRImage(embedding=USREmbedding(model_name="image", dimension=2, values=[1.0, 0.0]))
    ocr = USROCR(extracted_text="caption", normalized_text="caption")

    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023", text=text, image=image, ocr=ocr, audio=audio
    )
    rr = build_reasoning_representation(CMREF(ProjectionRegistry(2)).reason(usr))

    assert {item.value for item in usr.available_modalities} == {"text", "image", "ocr", "audio_transcript"}
    assert len(rr.pairwise_similarities) == 1
    assert rr.contradiction is None
