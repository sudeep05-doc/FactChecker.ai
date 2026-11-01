from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.config.settings import Settings
from app.models import EasyOCRTextExtractor, OCRStatus
from app.preprocessing import ImagePreprocessor
from tests.test_image_preprocessing import make_image_result


class FakeOCRReader:
    def readtext(self, path: str, detail: int, paragraph: bool):
        assert Path(path).is_file()
        assert detail == 1
        assert paragraph is False
        return [
            ([[4, 4], [90, 4], [90, 24], [4, 24]], "FactChecker", 0.96),
            ([[4, 30], [45, 30], [45, 48], [4, 48]], "AI", 0.88),
        ]


def test_ocr_is_lazy_and_preserves_text_boxes_and_confidence(tmp_path: Path) -> None:
    image_path = tmp_path / "text.png"
    image = Image.new("RGB", (120, 60), color="white")
    ImageDraw.Draw(image).text((4, 4), "FactChecker AI", fill="black")
    image.save(image_path)
    image_result = ImagePreprocessor().process(make_image_result(image_path))
    load_count = 0

    def factory(languages, device):
        nonlocal load_count
        load_count += 1
        assert languages == ["en"]
        assert device == "cpu"
        return FakeOCRReader()

    extractor = EasyOCRTextExtractor(
        settings=Settings(ocr_languages="en", ocr_device="cpu"),
        reader_factory=factory,
    )

    assert extractor.is_loaded is False
    result = extractor.extract(image_result)

    assert extractor.is_loaded is True
    assert load_count == 1
    assert result.ocr_status == OCRStatus.COMPLETED
    assert result.extracted_text == "FactChecker AI"
    assert result.detections[0].text == "FactChecker"
    assert result.detections[0].confidence == 0.96
    assert result.bounding_boxes[1] == [[4.0, 30.0], [45.0, 30.0], [45.0, 48.0], [4.0, 48.0]]
    assert result.ocr_confidence == pytest.approx(0.92)
    assert result.language_configuration == ["en"]
    assert result.processing_metadata["ocr_only"] is True


def test_ocr_supports_additional_configured_languages(tmp_path: Path) -> None:
    image_path = tmp_path / "text.png"
    Image.new("RGB", (20, 20), color="white").save(image_path)
    image_result = ImagePreprocessor().process(make_image_result(image_path))
    observed = {}

    def factory(languages, device):
        observed["languages"] = languages
        return FakeOCRReader()

    result = EasyOCRTextExtractor(
        settings=Settings(ocr_languages="en,hi", ocr_device="cpu"),
        reader_factory=factory,
    ).extract(image_result)

    assert result.ocr_status == OCRStatus.COMPLETED
    assert observed["languages"] == ["en", "hi"]
    assert result.language_configuration == ["en", "hi"]


def test_invalid_image_does_not_load_ocr_reader() -> None:
    image_result = ImagePreprocessor().process(make_image_result(Path("/missing.png")))
    extractor = EasyOCRTextExtractor(
        settings=Settings(ocr_device="cpu"),
        reader_factory=lambda *args: (_ for _ in ()).throw(
            AssertionError("reader should not load")
        ),
    )

    result = extractor.extract(image_result)

    assert result.ocr_status == OCRStatus.FAILED
    assert result.errors[0].code == "IMAGE_PREPROCESSING_FAILED"