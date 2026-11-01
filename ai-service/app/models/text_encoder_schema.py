"""Structured output for text representation generation."""

from enum import Enum
from math import isfinite
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TextEncodingStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class TextEncodingResult(BaseModel):
    """SentenceTransformer representation for downstream reasoning layers."""

    model_name: str
    embedding_dimension: Optional[int] = Field(default=None, ge=1)
    embedding: Optional[List[float]] = None
    language: Optional[str] = None
    status: TextEncodingStatus = TextEncodingStatus.AVAILABLE
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    modality: str = "text"
    normalized: bool = False
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_embedding(self) -> "TextEncodingResult":
        if self.status == TextEncodingStatus.AVAILABLE:
            if not self.embedding or self.embedding_dimension != len(self.embedding):
                raise ValueError("available text encoding requires a non-empty embedding")
            if not all(isfinite(value) for value in self.embedding):
                raise ValueError("text embedding values must be finite")
        elif self.embedding is not None or self.embedding_dimension is not None:
            raise ValueError("unavailable text encoding cannot contain an embedding")
        return self