import io
from pathlib import Path

import pytest
from PIL import Image

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.config.settings import Settings
from app.models import EasyOCRTextExtractor, OCRStatus
from app.preprocessing import ImagePreprocessor
from app.rr import build_reasoning_representation
from app.usr import USRImage, USRText, UnifiedSemanticRepresentationBuilder, USREmbedding
from tests.test_image_preprocessing import make_image_result


class FakeReader:
    def __init__(self, detections=None):
        self.detections = detections if detections is not None else [
            ([[4, 4], [90, 4], [90, 24], [4, 24]], "  FactChecker  ", 0.96),
            ([[4, 30], [45, 30], [45, 48], [4, 48]], "AI 2026!", 0.88),
        ]
        self.calls = []

    def readtext(self, source, detail, paragraph):
        self.calls.append((source, detail, paragraph))
        return self.detections


def make_extractor(tmp_path: Path, reader=None, settings=None):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (120, 60), color="white").save(image_path)
    image_result = ImagePreprocessor().process(make_image_result(image_path))
    reader = reader or FakeReader()
    loads = []

    def factory(languages, device):
        loads.append((languages, device))
        return reader

    extractor = EasyOCRTextExtractor(
        settings=settings or Settings(ocr_languages="en", ocr_device="cpu"),
        reader_factory=factory,
    )
    return extractor, image_result, image_path, loads, reader


def test_multiple_detections_preserve_order_boxes_and_raw_normalized_text(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path)

    result = extractor.extract(image_result)

    assert result.ocr_status == OCRStatus.COMPLETED
    assert [item.index for item in result.detections] == [0, 1]
    assert result.raw_text == "FactChecker   AI 2026!"
    assert result.extracted_text == "FactChecker AI 2026!"
    assert result.detections[0].raw_text == "  FactChecker  "
    assert result.detections[0].normalized_text == "FactChecker"
    assert result.detections[1].bounding_box == [[4.0, 30.0], [45.0, 30.0], [45.0, 48.0], [4.0, 48.0]]
    assert result.processing_metadata["ordering_strategy"] == "reader_output_order"


def test_ocr_confidence_is_recognition_metadata_only(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path)

    result = extractor.extract(image_result)

    assert result.ocr_confidence == pytest.approx(0.92)
    assert result.processing_metadata["ocr_confidence_semantics"] == "recognition_confidence_only"
    assert "prediction" not in result.processing_metadata
    assert "fake_probability" not in result.processing_metadata


def test_no_text_is_completed_with_explicit_non_negative_warning(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path, reader=FakeReader([]))

    result = extractor.extract(image_result)

    assert result.ocr_status == OCRStatus.COMPLETED
    assert result.extracted_text == ""
    assert result.ocr_confidence is None
    assert result.warnings[0].code == "OCR_NO_TEXT"
    assert result.processing_metadata["text_detected"] is False


def test_invalid_corrupted_and_missing_images_do_not_load_reader(tmp_path: Path):
    reader_factory = lambda *args: (_ for _ in ()).throw(AssertionError("reader should not load"))
    extractor = EasyOCRTextExtractor(settings=Settings(ocr_device="cpu"), reader_factory=reader_factory)
    corrupted = tmp_path / "corrupt.png"
    corrupted.write_bytes(b"not-an-image")

    missing = extractor.extract(tmp_path / "missing.png")
    empty = extractor.extract(b"")
    invalid = extractor.extract(corrupted)

    assert missing.errors[0].code == "IMAGE_NOT_FOUND"
    assert empty.errors[0].code == "INVALID_IMAGE"
    assert invalid.errors[0].code == "INVALID_IMAGE"
    assert extractor.is_loaded is False


def test_reader_is_lazy_reused_and_languages_are_configured(tmp_path: Path):
    extractor, image_result, _, loads, reader = make_extractor(
        tmp_path, settings=Settings(ocr_languages="en,hi", ocr_device="cpu", ocr_paragraph_mode=True)
    )

    assert extractor.is_loaded is False
    extractor.extract(image_result)
    extractor.extract(image_result)

    assert extractor.is_loaded is True
    assert loads == [(["en", "hi"], "cpu")]
    assert reader.calls[0][2] is True
    assert len(reader.calls) == 2


def test_model_directory_and_cpu_backend_metadata_are_explicit(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(
        tmp_path,
        settings=Settings(ocr_device="mps", ocr_use_gpu=False, ocr_model_directory="/tmp/easyocr-test"),
    )

    result = extractor.extract(image_result)

    assert result.processing_metadata["device"] == "cpu"
    assert result.processing_metadata["backend"] == "cpu"
    assert result.processing_metadata["model_directory"] == "/tmp/easyocr-test"


def test_reader_unavailable_and_processing_failure_are_structured(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path)
    extractor.reader_factory = lambda *args: (_ for _ in ()).throw(RuntimeError("reader unavailable"))
    unavailable = extractor.extract(image_result)

    failing_reader = FakeReader()
    failing_reader.readtext = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("OCR failed"))
    failing, image_result, _, _, _ = make_extractor(tmp_path, reader=failing_reader)
    failed = failing.extract(image_result)

    assert unavailable.ocr_status == OCRStatus.FAILED
    assert unavailable.errors[0].code == "OCR_FAILED"
    assert failed.errors[0].code == "OCR_FAILED"


def test_raw_bytes_and_pil_inputs_are_supported(tmp_path: Path):
    extractor, _, _, _, _ = make_extractor(tmp_path)
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), color="red").save(buffer, format="PNG")

    byte_result = extractor.extract(buffer.getvalue())
    pil_result = extractor.extract(Image.open(io.BytesIO(buffer.getvalue())))

    assert byte_result.ocr_status == OCRStatus.COMPLETED
    assert pil_result.ocr_status == OCRStatus.COMPLETED


def test_ocr_only_usr_evidence_preserves_text_without_inventing_embedding(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path)

    ocr = extractor.to_usr_ocr(image_result)

    assert ocr is not None
    assert ocr.extracted_text == "FactChecker AI 2026!"
    assert ocr.raw_text
    assert ocr.ocr_confidence == pytest.approx(0.92)
    assert "embedding" not in ocr.metadata
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023", ocr=ocr
    )
    assert usr.ocr is not None
    assert not hasattr(usr.ocr, "embedding")


def test_image_ocr_and_text_image_ocr_coexist(tmp_path: Path):
    extractor, image_result, _, _, _ = make_extractor(tmp_path)
    ocr = extractor.to_usr_ocr(image_result)
    image = USRImage(
        image_paths=[str(image_result.processed_image_path)],
        embedding=USREmbedding(model_name="image", dimension=2, values=[1.0, 0.0], normalized=True),
    )
    text = USRText(
        text="A claim",
        embedding=USREmbedding(model_name="text", dimension=2, values=[1.0, 0.0], normalized=True),
    )

    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023", text=text, image=image, ocr=ocr
    )
    rr = build_reasoning_representation(CMREF(ProjectionRegistry(2)).reason(usr))

    assert set(item.value for item in usr.available_modalities) == {"text", "image", "ocr"}
    assert len(rr.pairwise_similarities) == 1
    assert rr.contradiction is None
