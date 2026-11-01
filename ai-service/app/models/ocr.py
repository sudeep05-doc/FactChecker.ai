"""Lazy EasyOCR extraction with structured evidence and conservative device handling."""

import io
import time
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple
from uuid import uuid4

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.config.settings import Settings, get_settings
from app.models.ocr_schema import OCRDetection, OCRIssue, OCRResult, OCRStatus
from app.preprocessing.image_schema import ImagePreprocessingResult, ImagePreprocessingStatus
from app.preprocessing.text import clean_text
from app.usr.models import USROCR


class EasyOCRTextExtractor:
    """Load one EasyOCR reader lazily and preserve extraction evidence only."""

    def __init__(self, settings: Optional[Settings] = None, reader_factory: Optional[Callable[..., Any]] = None) -> None:
        self.settings = settings or get_settings()
        self.languages = _parse_languages(self.settings.ocr_languages)
        self.requested_device = self.settings.ocr_device
        self.use_gpu = self.settings.ocr_use_gpu
        self.model_directory = self.settings.ocr_model_directory
        self.paragraph_mode = self.settings.ocr_paragraph_mode
        self.reader_factory = reader_factory
        self._reader: Optional[Any] = None
        self._resolved_device: Optional[str] = None
        self._backend: Optional[str] = None
        self._device_fallback_reason: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        return self._reader is not None

    @property
    def resolved_device(self) -> Optional[str]:
        return self._resolved_device

    def extract(self, image: Any) -> OCRResult:
        request_id, source, image_path, failure = self._prepare_input(image)
        if failure is not None:
            return failure
        try:
            reader = self._get_reader()
            started_at = time.perf_counter()
            raw_detections = reader.readtext(source, detail=1, paragraph=self.paragraph_mode)
            detections = [_detection(item, index) for index, item in enumerate(raw_detections or [])]
            raw_text = " ".join(item.raw_text for item in detections if item.raw_text).strip()
            normalized_text = " ".join(item.normalized_text for item in detections if item.normalized_text).strip()
            warnings: List[OCRIssue] = []
            if not detections:
                warnings.append(OCRIssue(code="OCR_NO_TEXT", message="No textual content was extracted from the image."))
            confidence_values = [item.confidence for item in detections]
            return OCRResult(
                request_id=request_id,
                extracted_text=normalized_text,
                raw_text=raw_text,
                detections=detections,
                bounding_boxes=[item.bounding_box for item in detections],
                ocr_confidence=(sum(confidence_values) / len(confidence_values)) if confidence_values else None,
                language_configuration=self.languages,
                processing_metadata={
                    "device": self._resolved_device,
                    "backend": self._backend,
                    "requested_device": self.requested_device,
                    "device_fallback_reason": self._device_fallback_reason,
                    "model_directory": self.model_directory,
                    "paragraph_mode": self.paragraph_mode,
                    "ocr_only": True,
                    "detection_count": len(detections),
                    "text_detected": bool(detections),
                    "ocr_confidence_semantics": "recognition_confidence_only",
                    "ordering_strategy": "reader_output_order",
                    "processing_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
                },
                ocr_status=OCRStatus.COMPLETED,
                warnings=warnings,
            )
        except Exception as error:
            return self._failure(request_id, "OCR_FAILED", f"EasyOCR extraction failed: {error}.", image_path)

    def to_usr_ocr(self, image: Any) -> Optional[USROCR]:
        result = self.extract(image)
        if result.ocr_status != OCRStatus.COMPLETED:
            return None
        return USROCR(
            extracted_text=result.extracted_text,
            raw_text=result.raw_text,
            normalized_text=result.extracted_text,
            detections=[
                {
                    "index": item.index,
                    "text": item.text,
                    "raw_text": item.raw_text,
                    "confidence": item.confidence,
                    "bounding_box": item.bounding_box,
                }
                for item in result.detections
            ],
            bounding_boxes=result.bounding_boxes,
            ocr_confidence=result.ocr_confidence,
            language_configuration=result.language_configuration,
            metadata={
                "modality": result.modality,
                "processing": result.processing_metadata,
                "ocr_confidence_is_truth_confidence": False,
            },
        )

    def _prepare_input(self, image: Any) -> Tuple[Any, Any, Optional[str], Optional[OCRResult]]:
        request_id = image.request_id if isinstance(image, ImagePreprocessingResult) else uuid4()
        image_path = None
        if isinstance(image, ImagePreprocessingResult):
            if image.preprocessing_status != ImagePreprocessingStatus.COMPLETED:
                return request_id, None, None, self._failure(request_id, "IMAGE_PREPROCESSING_FAILED", "The image was not successfully preprocessed.")
            if not image.processed_image_path:
                return request_id, None, None, self._failure(request_id, "IMAGE_PATH_UNAVAILABLE", "No processed image path was provided.")
            image_path = image.processed_image_path
            source: Any = Path(image_path)
        elif isinstance(image, (str, Path)):
            image_path = str(Path(image).expanduser())
            source = Path(image_path)
        elif isinstance(image, bytes):
            if not image:
                return request_id, None, None, self._failure(request_id, "INVALID_IMAGE", "Image bytes are empty.")
            source = image
        elif isinstance(image, Image.Image):
            source = image
        else:
            return request_id, None, None, self._failure(request_id, "UNSUPPORTED_IMAGE_INPUT", "Expected an image preprocessing result, path, bytes, or PIL image.")

        try:
            if isinstance(source, Path):
                if not source.is_file():
                    return request_id, None, image_path, self._failure(request_id, "IMAGE_NOT_FOUND", "The image path does not exist.")
                with Image.open(source) as opened:
                    opened.verify()
                return request_id, str(source), image_path, None
            if isinstance(source, bytes):
                with Image.open(io.BytesIO(source)) as opened:
                    opened.load()
                    return request_id, np.asarray(opened.convert("RGB")), image_path, None
            source.load()
            return request_id, np.asarray(source.convert("RGB")), image_path, None
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
            return request_id, None, image_path, self._failure(request_id, "INVALID_IMAGE", f"Image could not be opened safely: {error}.")

    def _get_reader(self) -> Any:
        if self._reader is not None:
            return self._reader
        self._resolved_device, self._backend = _resolve_ocr_backend(self.requested_device, self.use_gpu)
        factory = self.reader_factory
        try:
            if factory is not None:
                self._reader = factory(self.languages, self._resolved_device)
            else:
                self._reader = _load_easyocr_reader(self.languages, self._resolved_device, self.use_gpu, self.model_directory)
        except Exception as error:
            if self._resolved_device != "cpu":
                self._device_fallback_reason = str(error)
                self._resolved_device, self._backend = "cpu", "cpu"
                if factory is not None:
                    self._reader = factory(self.languages, "cpu")
                else:
                    self._reader = _load_easyocr_reader(self.languages, "cpu", False, self.model_directory)
            else:
                raise
        return self._reader

    def _failure(self, request_id: Any, code: str, message: str, image_path: Optional[str] = None) -> OCRResult:
        return OCRResult(
            request_id=request_id,
            language_configuration=self.languages,
            ocr_status=OCRStatus.FAILED,
            processing_metadata={
                "device": self._resolved_device,
                "backend": self._backend,
                "requested_device": self.requested_device,
                "ocr_confidence_semantics": "recognition_confidence_only",
            },
            errors=[OCRIssue(code=code, message=message)],
        )


def _parse_languages(configuration: str) -> List[str]:
    languages = [language.strip() for language in configuration.split(",") if language.strip()]
    if not languages:
        raise ValueError("ocr_languages must contain at least one language")
    return languages


def _detection(item: Sequence[Any], index: int) -> OCRDetection:
    if len(item) != 3:
        raise ValueError("EasyOCR detection must contain bounding box, text, and confidence")
    box, text, confidence = item
    raw_text = str(text)
    return OCRDetection(
        index=index,
        text=clean_text(raw_text),
        raw_text=raw_text,
        normalized_text=clean_text(raw_text),
        confidence=max(0.0, min(1.0, float(confidence))),
        bounding_box=[[float(point[0]), float(point[1])] for point in box],
    )


def _resolve_ocr_backend(requested_device: str, use_gpu: bool) -> Tuple[str, str]:
    normalized = requested_device.strip().lower()
    if not use_gpu or normalized in {"cpu", "auto", "mps"}:
        return "cpu", "cpu"
    if normalized == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "cuda"
        except ImportError:
            pass
    return "cpu", "cpu_fallback"


def _load_easyocr_reader(languages: List[str], device: str, use_gpu: bool, model_directory: Optional[str]) -> Any:
    import easyocr
    return easyocr.Reader(
        languages,
        gpu=(use_gpu and device == "cuda"),
        model_storage_directory=model_directory,
        verbose=False,
    )
