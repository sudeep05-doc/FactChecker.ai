import wave
from pathlib import Path

import av
import numpy as np

from app.cal import AcquisitionStatus, CALResult
from app.preprocessing import (
    AudioPreprocessor,
    AudioPreprocessingStatus,
    VideoPreprocessor,
    VideoPreprocessingStatus,
)


def make_media_result(path: Path, input_type: str) -> CALResult:
    return CALResult(
        request_id="00000000-0000-4000-8000-000000000004",
        input_type=input_type,
        source=str(path),
        metadata={"file_path": str(path)},
        acquisition_status=AcquisitionStatus.COMPLETED,
        audio_path=str(path) if input_type == "audio" else None,
        video_path=str(path) if input_type == "video" else None,
    )


def make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(np.zeros(800, dtype=np.int16).tobytes())


def make_video(path: Path, frame_count: int = 8) -> None:
    with av.open(str(path), mode="w", format="mp4") as container:
        stream = container.add_stream("mpeg4", rate=8)
        stream.width = 32
        stream.height = 24
        stream.pix_fmt = "yuv420p"
        for index in range(frame_count):
            pixels = np.zeros((24, 32, 3), dtype=np.uint8)
            pixels[:, :, 0] = index * 20
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def test_valid_audio_is_normalized_for_whisper(tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.wav"
    make_wav(audio_path)

    result = AudioPreprocessor().process(make_media_result(audio_path, "audio"))

    assert result.preprocessing_status == AudioPreprocessingStatus.COMPLETED
    assert result.prepared_audio_path is not None
    assert Path(result.prepared_audio_path).is_file()
    assert result.sample_rate == 16000
    assert result.channels == 1
    assert result.metadata["original_sample_rate"] == 8000


def test_invalid_audio_is_reported(tmp_path: Path) -> None:
    audio_path = tmp_path / "invalid.wav"
    audio_path.write_bytes(b"not audio")

    result = AudioPreprocessor().process(make_media_result(audio_path, "audio"))

    assert result.preprocessing_status == AudioPreprocessingStatus.FAILED
    assert result.errors[0].code == "INVALID_AUDIO"


def test_valid_video_extracts_representative_frames(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    make_video(video_path)

    result = VideoPreprocessor(sample_count=3, extract_audio=False).process(
        make_media_result(video_path, "video")
    )

    assert result.preprocessing_status == VideoPreprocessingStatus.COMPLETED
    assert len(result.frame_paths) == 3
    assert result.metadata["sample_count_requested"] == 3
    assert result.width == 32
    assert result.height == 24


def test_invalid_video_is_reported(tmp_path: Path) -> None:
    video_path = tmp_path / "invalid.mp4"
    video_path.write_bytes(b"not video")

    result = VideoPreprocessor().process(make_media_result(video_path, "video"))

    assert result.preprocessing_status == VideoPreprocessingStatus.FAILED
    assert result.errors[0].code == "INVALID_VIDEO"


def test_video_sampling_is_configurable(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    make_video(video_path, frame_count=10)

    result = VideoPreprocessor(sample_count=2, extract_audio=False).process(
        make_media_result(video_path, "video")
    )

    assert len(result.frame_paths) == 2
    assert result.metadata["sample_count_returned"] == 2