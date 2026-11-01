"""Structured output contract for image preprocessing."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ImagePreprocessingStatus(str, Enum):
    """Outcome of image validation and normalization."""

    COMPLETED = "completed"
    FAILED = "failed"


class ImagePreprocessingIssue(BaseModel):
    """Warning or error produced during image processing."""

    code: str
    message: str


class ImagePreprocessingResult(BaseModel):
    """Image reference and metadata for future OpenCLIP preprocessing."""

    request_id: UUID
    input_type: str
    processed_image_path: Optional[str] = None
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    format: Optional[str] = None
    original_width: int = Field(default=0, ge=0)
    original_height: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    preprocessing_status: ImagePreprocessingStatus
    warnings: List[ImagePreprocessingIssue] = Field(default_factory=list)
    errors: List[ImagePreprocessingIssue] = Field(default_factory=list)