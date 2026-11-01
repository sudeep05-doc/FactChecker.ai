import wave
from pathlib import Path

import numpy as np
import pytest

from app.cal import AcquisitionStatus, CALResult
from app.config.settings import Settings
from app.models import TranscriptionStatus, WhisperTranscriber
from app.preprocessing import AudioPreprocessor


class FakeWhisperModel:
    def transcribe(self, path: str, **options):
        assert len(path) > 0
        assert options["fp16"] is False
        return {
            "text": " Hello world ",
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 0.8, "text": " Hello world "},
            ],
        }


def make_short_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(np.zeros(800, dtype=np.int16).tobytes())


def make_audio_result(path: Path):
    return AudioPreprocessor().process(
        CALResult(
            request_id="00000000-0000-4000-8000-000000000014",
            input_type="audio",
            source=str(path),
            audio_path=str(path),
            acquisition_status=AcquisitionStatus.COMPLETED,
        )
    )


def test_short_audio_transcription_is_lazy_and_structured(tmp_path: Path) -> None:
    audio_result = make_audio_result(tmp_path / "short.wav")
    make_short_wav(Path(audio_result.source))
    audio_result = make_audio_result(Path(audio_result.source))
    load_count = 0

    def factory(model_variant: str, device: str):
        nonlocal load_count
        load_count += 1
        assert model_variant == "tiny"
        assert device == "cpu"
        return FakeWhisperModel()

    transcriber = WhisperTranscriber(
        settings=Settings(
            whisper_model_variant="tiny",
            whisper_device="cpu",
            whisper_max_duration_seconds=10,
        ),
        model_factory=factory,
    )

    assert transcriber.is_loaded is False
    result = transcriber.transcribe(audio_result)

    assert result.transcription_status == TranscriptionStatus.COMPLETED
    assert result.transcript == "Hello world"
    assert result.detected_language == "en"
    assert result.segments[0].start_seconds == pytest.approx(0.0)
    assert result.segments[0].end_seconds == pytest.approx(0.8)
    assert result.processing_metadata["speech_to_text_only"] is True
    assert load_count == 1


def test_audio_duration_limit_prevents_model_loading(tmp_path: Path) -> None:
    audio_path = tmp_path / "short.wav"
    make_short_wav(audio_path)
    audio_result = make_audio_result(audio_path)
    audio_result.duration_seconds = 11
    transcriber = WhisperTranscriber(
        settings=Settings(whisper_max_duration_seconds=10),
        model_factory=lambda *args: (_ for _ in ()).throw(
            AssertionError("model should not load")
        ),
    )

    result = transcriber.transcribe(audio_result)

    assert result.transcription_status == TranscriptionStatus.FAILED
    assert result.errors[0].code == "AUDIO_DURATION_LIMIT"


def test_invalid_audio_is_reported_without_model_loading() -> None:
    from app.preprocessing.audio_schema import AudioPreprocessingResult, AudioPreprocessingStatus

    audio_result = AudioPreprocessingResult(
        request_id="00000000-0000-4000-8000-000000000014",
        input_type="audio",
        source="invalid",
        preprocessing_status=AudioPreprocessingStatus.FAILED,
    )
    transcriber = WhisperTranscriber(settings=Settings(whisper_device="cpu"))

    result = transcriber.transcribe(audio_result)

    assert result.transcription_status == TranscriptionStatus.FAILED
    assert result.errors[0].code == "AUDIO_PREPROCESSING_FAILED"