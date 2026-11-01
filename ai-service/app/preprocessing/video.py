"""Streaming video metadata, audio extraction, and representative frames."""

import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Set

import av

from app.cal.schemas import AcquisitionStatus, CALResult
from app.preprocessing.audio import AudioPreprocessor
from app.preprocessing.video_schema import (
    VideoPreprocessingIssue,
    VideoPreprocessingResult,
    VideoPreprocessingStatus,
)


class VideoPreprocessor:
    """Decode one frame at a time and retain only configured sample outputs."""

    def __init__(self, sample_count: int = 4, extract_audio: bool = True) -> None:
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        self.sample_count = sample_count
        self.extract_audio = extract_audio

    def process(self, content: CALResult) -> VideoPreprocessingResult:
        source = _media_source(content)
        base = {
            "request_id": content.request_id,
            "input_type": content.input_type,
            "source": source,
        }
        if content.acquisition_status != AcquisitionStatus.COMPLETED:
            return self._failure(base, "ACQUISITION_INCOMPLETE", "CAL content was not acquired successfully.")
        if not source or not Path(source).is_file():
            return self._failure(base, "VIDEO_NOT_FOUND", "The acquired video path does not exist.")

        frame_paths: List[str] = []
        warnings: List[VideoPreprocessingIssue] = []
        try:
            with av.open(source) as container:
                video_stream = next((stream for stream in container.streams if stream.type == "video"), None)
                if video_stream is None:
                    return self._failure(base, "VIDEO_STREAM_NOT_FOUND", "No video stream was found.")

                frame_count = video_stream.frames or None
                frame_rate = _float_rate(video_stream.average_rate)
                duration = _duration_seconds(video_stream, container)
                target_indices = _sample_indices(frame_count, self.sample_count)
                target_set: Set[int] = set(target_indices)

                for frame_index, frame in enumerate(container.decode(video=video_stream.index)):
                    if frame_index in target_set:
                        frame_paths.append(_write_frame(frame, frame_index))

                if not frame_paths:
                    warnings.append(
                        VideoPreprocessingIssue(
                            code="NO_FRAMES_EXTRACTED",
                            message="The video contained no decodable video frames.",
                        )
                    )

                extracted_audio_path = None
                if self.extract_audio:
                    audio_result = AudioPreprocessor().process(content)
                    if audio_result.prepared_audio_path:
                        extracted_audio_path = audio_result.prepared_audio_path
                    else:
                        warnings.append(
                            VideoPreprocessingIssue(
                                code="AUDIO_EXTRACTION_UNAVAILABLE",
                                message="No audio representation was extracted from the video.",
                            )
                        )

                return VideoPreprocessingResult(
                    **base,
                    prepared_video_path=source,
                    extracted_audio_path=extracted_audio_path,
                    frame_paths=frame_paths,
                    width=video_stream.width,
                    height=video_stream.height,
                    frame_rate=frame_rate,
                    frame_count=frame_count,
                    duration_seconds=duration,
                    metadata={
                        "sample_count_requested": self.sample_count,
                        "sample_count_returned": len(frame_paths),
                        "source_file_size_bytes": Path(source).stat().st_size,
                    },
                    preprocessing_status=VideoPreprocessingStatus.COMPLETED,
                    warnings=warnings,
                )
        except (av.error.FFmpegError, OSError, ValueError, TypeError) as error:
            return self._failure(base, "INVALID_VIDEO", f"Video could not be decoded safely: {error}.")

    @staticmethod
    def _failure(base: Dict[str, Any], code: str, message: str) -> VideoPreprocessingResult:
        return VideoPreprocessingResult(
            **base,
            preprocessing_status=VideoPreprocessingStatus.FAILED,
            errors=[VideoPreprocessingIssue(code=code, message=message)],
        )


def _sample_indices(frame_count: Any, sample_count: int) -> List[int]:
    if not frame_count:
        return list(range(sample_count))
    if frame_count <= sample_count:
        return list(range(frame_count))
    return sorted({round(index * (frame_count - 1) / (sample_count - 1)) for index in range(sample_count)})


def _write_frame(frame: av.VideoFrame, frame_index: int) -> str:
    temporary_file = tempfile.NamedTemporaryFile(
        prefix=f"factchecker-video-frame-{frame_index}-", suffix=".jpg", delete=False
    )
    path = temporary_file.name
    temporary_file.close()
    frame.to_image().save(path, format="JPEG", quality=85)
    return path


def _float_rate(rate: Any) -> Any:
    if rate is None:
        return None
    return float(rate)


def _duration_seconds(stream: Any, container: Any) -> Any:
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return float(container.duration / 1_000_000)
    return None


def _media_source(content: CALResult) -> str:
    return str(content.video_path or content.metadata.get("file_path") or content.source or "")