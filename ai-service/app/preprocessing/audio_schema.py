"""Structured output contract for audio preprocessing."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AudioPreprocessingStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class AudioPreprocessingIssue(BaseModel):
    code: str
    message: str


class AudioPreprocessingResult(BaseModel):
    request_id: UUID
    input_type: str
    source: str
    prepared_audio_path: Optional[str] = None
    sample_rate: Optional[int] = Field(default=None, ge=1)
    channels: Optional[int] = Field(default=None, ge=1)
    sample_format: Optional[str] = None
    duration_seconds: Optional[float] = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    preprocessing_status: AudioPreprocessingStatus
    warnings: List[AudioPreprocessingIssue] = Field(default_factory=list)
    errors: List[AudioPreprocessingIssue] = Field(default_factory=list)