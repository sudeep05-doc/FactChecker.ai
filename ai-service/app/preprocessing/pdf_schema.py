"""Structured output contract for PDF preprocessing."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PDFPreprocessingStatus(str, Enum):
    """Outcome of PDF validation and extraction."""

    COMPLETED = "completed"
    FAILED = "failed"


class PDFPreprocessingIssue(BaseModel):
    """Warning or error produced during PDF processing."""

    code: str
    message: str


class PDFPageText(BaseModel):
    """Text extracted from one PDF page."""

    page_number: int = Field(ge=1)
    text: str = ""


class PDFPreprocessingResult(BaseModel):
    """Normalized textual and optional image references from a PDF."""

    request_id: UUID
    input_type: str
    source: str
    extracted_text: str = ""
    page_count: int = Field(default=0, ge=0)
    pages: List[PDFPageText] = Field(default_factory=list)
    extracted_image_paths: List[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    preprocessing_status: PDFPreprocessingStatus
    warnings: List[PDFPreprocessingIssue] = Field(default_factory=list)
    errors: List[PDFPreprocessingIssue] = Field(default_factory=list)