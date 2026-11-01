"""Normalized output contract for the Content Acquisition Layer."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AcquisitionStatus(str, Enum):
    """Outcome of attempting to acquire submitted content."""

    COMPLETED = "completed"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class AcquisitionError(BaseModel):
    """Non-fabricated error information produced during acquisition."""

    code: str
    message: str
    field: Optional[str] = None


class CALResult(BaseModel):
    """Common normalized content shape consumed by preprocessing later."""

    request_id: UUID
    input_type: str
    source: str
    text_content: Optional[str] = None
    image_paths: List[str] = Field(default_factory=list)
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    acquisition_status: AcquisitionStatus
    errors: List[AcquisitionError] = Field(default_factory=list)