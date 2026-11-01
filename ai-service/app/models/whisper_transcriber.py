"""Lazy local Whisper transcription for audio and extracted video audio."""

import io
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

import av
import numpy as np

from app.config.settings import Settings, get_settings
from app.models.text_encoder import resolve_device
from app.models.whisper_schema import TranscriptionIssue, TranscriptionResult, TranscriptionSegment, TranscriptionStatus
from app.preprocessing.audio_schema import AudioPreprocessingResult, AudioPreprocessingStatus
from app.preprocessing.video_schema import VideoPreprocessingResult, VideoPreprocessingStatus
from app.preprocessing.text import clean_text
from app.usr.models import USRAudioTranscript, USRVideo


DEFAULT_WHISPER_MODEL = "tiny"


class WhisperTranscriber:
    """Load one Whisper model lazily and produce timestamped speech evidence."""

    def __init__(self, settings: Optional[Settings] = None, model_factory: Optional[Callable[..., Any]] = None) -> None:
        self.settings = settings or get_settings()
        self.model_variant = self.settings.whisper_model_variant
        self.requested_device = self.settings.whisper_device
        self.language = self.settings.whisper_language
        self.task = self.settings.whisper_task
        self.max_duration_seconds = self.settings.whisper_max_duration_seconds
        self.chunk_seconds = self.settings.whisper_chunk_seconds
        self.model_factory = model_factory
        self._model: Optional[Any] = None
        self._resolved_device: Optional[str] = None
        self._backend: Optional[str] = None
        self._device_fallback_reason: Optional[str] = None
        if self.max_duration_seconds < 1:
            raise ValueError("whisper_max_duration_seconds must be positive")
        if self.chunk_seconds is not None and self.chunk_seconds < 1:
            raise ValueError("whisper_chunk_seconds must be positive")
        if self.task not in {"transcribe", "translate"}:
            raise ValueError("whisper_task must be transcribe or translate")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def resolved_device(self) -> Optional[str]:
        return self._resolved_device

    def transcribe(self, audio: Any, language: Optional[str] = None) -> TranscriptionResult:
        request_id, waveform, duration, failure = self._prepare_audio(audio)
        if failure is not None:
            return failure
        if duration is not None and duration > self.max_duration_seconds:
            return self._failure(request_id, "AUDIO_DURATION_LIMIT", f"Audio duration exceeds the configured limit of {self.max_duration_seconds} seconds.")
        try:
            model = self._get_model()
        except Exception as error:
            return self._failure(request_id, "TRANSCRIPTION_UNAVAILABLE", f"Whisper model could not be loaded: {error}.")
        started_at = time.perf_counter()
        try:
            segments: List[TranscriptionSegment] = []
            chunks = self._chunks(waveform, self.chunk_seconds)
            for chunk_index, (offset, chunk) in enumerate(chunks):
                options: Dict[str, Any] = {
                    "fp16": False,
                    "verbose": False,
                    "task": self.task,
                }
                selected_language = language or self.language
                if selected_language:
                    options["language"] = selected_language
                output = model.transcribe(chunk, **options)
                segments.extend(_segments(output.get("segments") or [], offset, len(segments)))
            raw_transcript = " ".join(segment.text for segment in segments if segment.text).strip()
            if not raw_transcript:
                raw_transcript = str(output.get("text") or "").strip() if "output" in locals() else ""
            normalized_transcript = clean_text(raw_transcript) if raw_transcript else ""
            warnings: List[TranscriptionIssue] = []
            if not normalized_transcript:
                warnings.append(TranscriptionIssue(code="AUDIO_NO_SPEECH", message="Whisper did not detect speech in the audio."))
            detected_language = (output.get("language") if "output" in locals() else None) or language or self.language
            result = TranscriptionResult(
                request_id=request_id,
                transcript=normalized_transcript,
                raw_transcript=raw_transcript,
                normalized_transcript=normalized_transcript,
                detected_language=detected_language,
                segments=segments,
                model=self.model_variant,
                modality="audio_transcript",
                processing_metadata={
                    "device": self._resolved_device,
                    "backend": self._backend,
                    "requested_device": self.requested_device,
                    "language_requested": language or self.language,
                    "task": self.task,
                    "duration_seconds": duration,
                    "max_duration_seconds": self.max_duration_seconds,
                    "chunk_seconds": self.chunk_seconds,
                    "chunk_count": len(chunks),
                    "speech_to_text_only": True,
                    "whisper_confidence_semantics": "transcription_metadata_only",
                    "timestamp_semantics": "model_segments_only",
                    "inference_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
                    "device_fallback_reason": self._device_fallback_reason,
                },
                transcription_status=TranscriptionStatus.COMPLETED,
                warnings=warnings,
            )
            return result
        except Exception as error:
            return self._failure(request_id, "TRANSCRIPTION_FAILED", f"Whisper transcription failed: {error}.")

    def transcribe_video(self, video: VideoPreprocessingResult, language: Optional[str] = None) -> TranscriptionResult:
        if video.preprocessing_status != VideoPreprocessingStatus.COMPLETED:
            return self._failure(video.request_id, "VIDEO_PREPROCESSING_FAILED", "Video was not prepared successfully.")
        if not video.extracted_audio_path:
            return self._failure(video.request_id, "VIDEO_AUDIO_UNAVAILABLE", "Video preprocessing did not provide an extracted audio path.")
        result = self.transcribe(
            AudioPreprocessingResult(
                request_id=video.request_id,
                input_type="audio",
                source=video.extracted_audio_path,
                prepared_audio_path=video.extracted_audio_path,
                duration_seconds=video.duration_seconds,
                preprocessing_status=AudioPreprocessingStatus.COMPLETED,
            ),
            language=language,
        )
        result.modality = "video_transcript"
        result.processing_metadata["video_audio_path"] = video.extracted_audio_path
        result.processing_metadata["video_speech_pathway"] = "video_to_extracted_audio_to_whisper"
        return result

    def to_usr_audio(self, audio: Any, language: Optional[str] = None) -> Optional[USRAudioTranscript]:
        result = self.transcribe(audio, language=language)
        if result.transcription_status != TranscriptionStatus.COMPLETED:
            return None
        return USRAudioTranscript(
            transcript=result.transcript,
            raw_transcript=result.raw_transcript,
            normalized_transcript=result.normalized_transcript,
            language=result.detected_language,
            segments=[segment.model_dump() for segment in result.segments],
            metadata={"modality": result.modality, "processing": result.processing_metadata, "transcription_confidence_is_truth_confidence": False},
        )

    def to_usr_video(self, video: VideoPreprocessingResult, language: Optional[str] = None) -> Optional[USRVideo]:
        result = self.transcribe_video(video, language=language)
        if result.transcription_status != TranscriptionStatus.COMPLETED:
            return None
        return USRVideo(
            transcript=result.transcript,
            language=result.detected_language,
            transcript_segments=[segment.model_dump() for segment in result.segments],
            metadata={"modality": result.modality, "processing": result.processing_metadata, "transcription_confidence_is_truth_confidence": False},
        )

    def _prepare_audio(self, audio: Any) -> Tuple[Any, Optional[np.ndarray], Optional[float], Optional[TranscriptionResult]]:
        if isinstance(audio, AudioPreprocessingResult):
            if audio.preprocessing_status != AudioPreprocessingStatus.COMPLETED:
                return audio.request_id, None, None, self._failure(audio.request_id, "AUDIO_PREPROCESSING_FAILED", "Audio was not prepared successfully.")
            if not audio.prepared_audio_path:
                return audio.request_id, None, None, self._failure(audio.request_id, "AUDIO_PATH_UNAVAILABLE", "No prepared audio path was provided.")
            request_id = audio.request_id
            path = Path(audio.prepared_audio_path)
            duration = audio.duration_seconds
        elif isinstance(audio, (str, Path)):
            request_id = uuid4()
            path = Path(audio).expanduser()
            duration = None
        elif isinstance(audio, bytes):
            request_id = uuid4()
            if not audio:
                return request_id, None, None, self._failure(request_id, "AUDIO_EMPTY", "Audio bytes are empty.")
            temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temporary.write(audio)
            temporary.close()
            path = Path(temporary.name)
            duration = None
        else:
            request_id = uuid4()
            return request_id, None, None, self._failure(request_id, "UNSUPPORTED_AUDIO_INPUT", "Expected audio preprocessing result, local path, or bytes.")
        if not path.is_file():
            return request_id, None, duration, self._failure(request_id, "AUDIO_NOT_FOUND", "The audio path does not exist.")
        try:
            waveform = _load_normalized_waveform(path)
            if duration is None:
                duration = len(waveform) / 16000.0
            return request_id, waveform, duration, None
        except (OSError, ValueError, wave.Error) as error:
            return request_id, None, duration, self._failure(request_id, "INVALID_AUDIO", f"Audio could not be read: {error}.")

    def _chunks(self, waveform: np.ndarray, chunk_seconds: Optional[int]) -> List[Tuple[float, np.ndarray]]:
        if not chunk_seconds:
            return [(0.0, waveform)]
        size = chunk_seconds * 16000
        return [(index / 16000.0, waveform[index:index + size]) for index in range(0, len(waveform), size)]

    def _get_model(self) -> Any:
        if self._model is None:
            self._resolved_device = resolve_device(self.requested_device)
            self._backend = "openai-whisper"
            factory = self.model_factory or _load_whisper
            try:
                self._model = factory(self.model_variant, self._resolved_device)
            except Exception as error:
                if self._resolved_device != "mps":
                    raise
                self._device_fallback_reason = str(error)
                self._resolved_device = "cpu"
                self._model = factory(self.model_variant, "cpu")
        return self._model

    def _failure(self, request_id: Any, code: str, message: str) -> TranscriptionResult:
        return TranscriptionResult(
            request_id=request_id,
            model=self.model_variant,
            modality="audio_transcript",
            processing_metadata={"device": self._resolved_device, "backend": self._backend, "requested_device": self.requested_device, "whisper_confidence_semantics": "transcription_metadata_only"},
            transcription_status=TranscriptionStatus.FAILED,
            errors=[TranscriptionIssue(code=code, message=message)],
        )


def _load_whisper(model_variant: str, device: str) -> Any:
    import whisper
    return whisper.load_model(model_variant, device=device)


def _segments(raw_segments: List[Dict[str, Any]], offset: float = 0.0, start_index: int = 0) -> List[TranscriptionSegment]:
    segments = []
    for index, segment in enumerate(raw_segments, start=start_index):
        start = segment.get("start")
        end = segment.get("end")
        segments.append(
            TranscriptionSegment(
                index=index,
                start_seconds=(max(0.0, float(start)) + offset) if start is not None else None,
                end_seconds=(max(0.0, float(end)) + offset) if end is not None else None,
                text=str(segment.get("text", "")).strip(),
            )
        )
    return segments


def _probe_duration(path: Path) -> Optional[float]:
    try:
        with av.open(str(path)) as container:
            if container.duration is not None:
                return float(container.duration / 1_000_000)
    except (av.error.FFmpegError, OSError, ValueError):
        return None
    return None


def _load_normalized_waveform(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as audio_file:
        if audio_file.getnchannels() != 1 or audio_file.getsampwidth() != 2:
            raise ValueError("Whisper input must be 16-bit mono PCM WAV.")
        frames = audio_file.readframes(audio_file.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
