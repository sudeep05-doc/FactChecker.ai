"""Structured output contract for text preprocessing."""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PreprocessingStatus(str, Enum):
    """Outcome of preprocessing normalized CAL content."""

    COMPLETED = "completed"
    FAILED = "failed"


class PreprocessingIssue(BaseModel):
    """Warning or error that does not contain fabricated content."""

    code: str
    message: str


class TextPreprocessingResult(BaseModel):
    """Deterministic text output for downstream representation building."""

    request_id: UUID
    input_type: str
    cleaned_text: str = ""
    original_text_length: int = Field(default=0, ge=0)
    cleaned_text_length: int = Field(default=0, ge=0)
    detected_language: Optional[str] = None
    preprocessing_status: PreprocessingStatus
    warnings: List[PreprocessingIssue] = Field(default_factory=list)
    errors: List[PreprocessingIssue] = Field(default_factory=list)