"""Streaming audio validation and Whisper-ready WAV normalization."""

import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List

import av
import numpy as np
from av.audio.resampler import AudioResampler

from app.cal.schemas import AcquisitionStatus, CALResult
from app.preprocessing.audio_schema import (
    AudioPreprocessingIssue,
    AudioPreprocessingResult,
    AudioPreprocessingStatus,
)


class AudioPreprocessor:
    """Decode audio incrementally and write 16 kHz mono signed PCM WAV."""

    def __init__(self, target_sample_rate: int = 16_000) -> None:
        if target_sample_rate < 1:
            raise ValueError("target_sample_rate must be positive")
        self.target_sample_rate = target_sample_rate

    def process(self, content: CALResult) -> AudioPreprocessingResult:
        source = _media_source(content, "audio_path")
        base = {
            "request_id": content.request_id,
            "input_type": content.input_type,
            "source": source,
        }
        if content.acquisition_status != AcquisitionStatus.COMPLETED:
            return self._failure(base, "ACQUISITION_INCOMPLETE", "CAL content was not acquired successfully.")
        if not source or not Path(source).is_file():
            return self._failure(base, "AUDIO_NOT_FOUND", "The acquired audio path does not exist.")

        output_path = _temporary_path("factchecker-audio-", ".wav")
        try:
            with av.open(source) as container:
                audio_stream = next((stream for stream in container.streams if stream.type == "audio"), None)
                if audio_stream is None:
                    return self._failure(base, "AUDIO_STREAM_NOT_FOUND", "No audio stream was found.")

                original_rate = audio_stream.rate
                original_channels = audio_stream.channels
                resampler = AudioResampler(format="s16", layout="mono", rate=self.target_sample_rate)
                sample_count = 0
                with wave.open(output_path, "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(self.target_sample_rate)
                    for frame in container.decode(audio=audio_stream.index):
                        for normalized_frame in _resample(resampler, frame):
                            samples = normalized_frame.to_ndarray()
                            sample_count += int(samples.shape[-1])
                            output.writeframes(np.ascontiguousarray(samples).tobytes())

                duration = sample_count / self.target_sample_rate
                return AudioPreprocessingResult(
                    **base,
                    prepared_audio_path=output_path,
                    sample_rate=self.target_sample_rate,
                    channels=1,
                    sample_format="s16",
                    duration_seconds=duration,
                    metadata={
                        "original_sample_rate": original_rate,
                        "original_channels": original_channels,
                        "normalized_for": "whisper",
                        "source_file_size_bytes": Path(source).stat().st_size,
                    },
                    preprocessing_status=AudioPreprocessingStatus.COMPLETED,
                )
        except (av.error.FFmpegError, OSError, ValueError, TypeError) as error:
            _remove_if_exists(output_path)
            return self._failure(base, "INVALID_AUDIO", f"Audio could not be decoded safely: {error}.")

    @staticmethod
    def _failure(base: Dict[str, Any], code: str, message: str) -> AudioPreprocessingResult:
        return AudioPreprocessingResult(
            **base,
            preprocessing_status=AudioPreprocessingStatus.FAILED,
            errors=[AudioPreprocessingIssue(code=code, message=message)],
        )


def _resample(resampler: AudioResampler, frame: av.AudioFrame) -> List[av.AudioFrame]:
    output = resampler.resample(frame)
    return output if isinstance(output, list) else [output]


def _temporary_path(prefix: str, suffix: str) -> str:
    temporary_file = tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, delete=False)
    path = temporary_file.name
    temporary_file.close()
    return path


def _remove_if_exists(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def _media_source(content: CALResult, path_field: str) -> str:
    direct_path = getattr(content, path_field, None)
    return str(direct_path or content.metadata.get("file_path") or content.source or "")