"""Structured output for Whisper speech-to-text transcription."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TranscriptionStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionIssue(BaseModel):
    code: str
    message: str


class TranscriptionSegment(BaseModel):
    index: int = Field(ge=0)
    start_seconds: Optional[float] = Field(default=None, ge=0)
    end_seconds: Optional[float] = Field(default=None, ge=0)
    text: str


class TranscriptionResult(BaseModel):
    """Whisper speech-to-text output for later multimodal reasoning."""

    request_id: UUID
    transcript: str = ""
    raw_transcript: str = ""
    normalized_transcript: str = ""
    detected_language: Optional[str] = None
    segments: List[TranscriptionSegment] = Field(default_factory=list)
    model: str
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    transcription_status: TranscriptionStatus
    warnings: List[TranscriptionIssue] = Field(default_factory=list)
    errors: List[TranscriptionIssue] = Field(default_factory=list)
    modality: str = "audio_transcript"