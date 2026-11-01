"""Structured output for OpenCLIP image representation generation."""

from enum import Enum
from math import isfinite
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ImageEncodingStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class ImageEncodingIssue(BaseModel):
    code: str
    message: str


class ImageEncodingResult(BaseModel):
    """OpenCLIP image representation kept internal to the AI service."""

    request_id: UUID
    model_name: str
    checkpoint: str
    embedding_dimension: Optional[int] = Field(default=None, ge=1)
    embedding: Optional[List[float]] = None
    image_path: Optional[str] = None
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    encoding_status: ImageEncodingStatus
    errors: List[ImageEncodingIssue] = Field(default_factory=list)
    modality: str = "image"
    normalized: bool = False

    @model_validator(mode="after")
    def validate_embedding(self) -> "ImageEncodingResult":
        if self.encoding_status == ImageEncodingStatus.COMPLETED:
            if not self.embedding or self.embedding_dimension != len(self.embedding):
                raise ValueError("completed image encoding requires a non-empty embedding")
            if not all(isfinite(value) for value in self.embedding):
                raise ValueError("image embedding values must be finite")
        elif self.embedding is not None or self.embedding_dimension is not None:
            raise ValueError("failed image encoding cannot contain an embedding")
        return self

    @classmethod
    def available(cls, **kwargs: Any) -> "ImageEncodingResult":
        return cls(encoding_status=ImageEncodingStatus.COMPLETED, **kwargs)

    @classmethod
    def unavailable(cls, **kwargs: Any) -> "ImageEncodingResult":
        return cls(encoding_status=ImageEncodingStatus.FAILED, **kwargs)