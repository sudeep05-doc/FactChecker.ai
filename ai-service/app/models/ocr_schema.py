"""Structured output for EasyOCR image text extraction."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OCRStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class OCRIssue(BaseModel):
    code: str
    message: str


class OCRDetection(BaseModel):
    index: int = Field(ge=0)
    text: str
    raw_text: str
    normalized_text: str
    confidence: float = Field(ge=0, le=1)
    bounding_box: List[List[float]] = Field(default_factory=list)


class OCRResult(BaseModel):
    """OCR output kept separate from fake-news confidence and prediction."""

    request_id: UUID
    extracted_text: str = ""
    raw_text: str = ""
    detections: List[OCRDetection] = Field(default_factory=list)
    bounding_boxes: List[List[List[float]]] = Field(default_factory=list)
    ocr_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    language_configuration: List[str] = Field(default_factory=list)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    ocr_status: OCRStatus
    warnings: List[OCRIssue] = Field(default_factory=list)
    errors: List[OCRIssue] = Field(default_factory=list)
    modality: str = "ocr"