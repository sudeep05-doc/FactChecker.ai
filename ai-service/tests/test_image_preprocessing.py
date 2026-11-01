from pathlib import Path

from PIL import Image

from app.cal import AcquisitionStatus, CALResult
from app.preprocessing import ImagePreprocessingStatus, ImagePreprocessor


def make_image_result(path: Path) -> CALResult:
    return CALResult(
        request_id="00000000-0000-4000-8000-000000000002",
        input_type="image",
        source=str(path),
        image_paths=[str(path)],
        acquisition_status=AcquisitionStatus.COMPLETED,
    )


def test_small_png_keeps_path_when_already_normalized(tmp_path: Path) -> None:
    image_path = tmp_path / "small.png"
    Image.new("RGB", (40, 20), color=(20, 40, 60)).save(image_path, format="PNG")

    result = ImagePreprocessor(max_dimension=224).process(make_image_result(image_path))

    assert result.preprocessing_status == ImagePreprocessingStatus.COMPLETED
    assert result.processed_image_path == str(image_path)
    assert (result.width, result.height) == (40, 20)
    assert result.format == "PNG"
    assert result.metadata["original_mode"] == "RGB"


def test_large_image_is_resized_with_aspect_ratio(tmp_path: Path) -> None:
    image_path = tmp_path / "large.webp"
    Image.new("RGB", (800, 400), color=(100, 120, 140)).save(image_path, format="WEBP")

    result = ImagePreprocessor(max_dimension=224).process(make_image_result(image_path))

    assert result.preprocessing_status == ImagePreprocessingStatus.COMPLETED
    assert result.processed_image_path != str(image_path)
    assert (result.width, result.height) == (224, 112)
    assert result.format == "PNG"
    assert Path(result.processed_image_path).is_file()


def test_corrupted_image_is_reported(tmp_path: Path) -> None:
    image_path = tmp_path / "corrupted.png"
    image_path.write_bytes(b"not an image")

    result = ImagePreprocessor().process(make_image_result(image_path))

    assert result.preprocessing_status == ImagePreprocessingStatus.FAILED
    assert result.errors[0].code == "CORRUPTED_IMAGE"


def test_unsupported_image_format_is_reported(tmp_path: Path) -> None:
    image_path = tmp_path / "image.bmp"
    Image.new("RGB", (10, 10), color="red").save(image_path, format="BMP")

    result = ImagePreprocessor().process(make_image_result(image_path))

    assert result.preprocessing_status == ImagePreprocessingStatus.FAILED
    assert result.errors[0].code == "UNSUPPORTED_IMAGE_FORMAT"