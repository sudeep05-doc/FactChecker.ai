"""Structured output contract for video preprocessing."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VideoPreprocessingStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class VideoPreprocessingIssue(BaseModel):
    code: str
    message: str


class VideoPreprocessingResult(BaseModel):
    request_id: UUID
    input_type: str
    source: str
    prepared_video_path: Optional[str] = None
    extracted_audio_path: Optional[str] = None
    frame_paths: List[str] = Field(default_factory=list)
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    frame_rate: Optional[float] = Field(default=None, ge=0)
    frame_count: Optional[int] = Field(default=None, ge=0)
    duration_seconds: Optional[float] = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    preprocessing_status: VideoPreprocessingStatus
    warnings: List[VideoPreprocessingIssue] = Field(default_factory=list)
    errors: List[VideoPreprocessingIssue] = Field(default_factory=list)