"""Typed, model-agnostic Unified Semantic Representation structures."""

import math
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class USRModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    OCR = "ocr"
    AUDIO_TRANSCRIPT = "audio_transcript"
    VIDEO_TRANSCRIPT = "video_transcript"
    VIDEO_FRAMES = "video_frames"


class USREmbedding(BaseModel):
    """A finite embedding with an explicitly checked dimension."""

    model_config = ConfigDict(extra="forbid")

    model_name: str
    dimension: int = Field(ge=1)
    values: List[float] = Field(min_length=1)
    normalized: bool = False

    @model_validator(mode="after")
    def validate_values(self) -> "USREmbedding":
        if len(self.values) != self.dimension:
            raise ValueError("embedding dimension does not match values length")
        if not all(math.isfinite(value) for value in self.values):
            raise ValueError("embedding values must be finite")
        return self


class USREmbeddingMetadata(BaseModel):
    model_name: str
    dimension: int = Field(ge=1)
    normalized: bool = False


class USRText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    language: Optional[str] = None
    embedding: Optional[USREmbedding] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_text(self) -> "USRText":
        if not self.text.strip():
            raise ValueError("text representation cannot be empty")
        return self


class USRImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_paths: List[str] = Field(default_factory=list)
    embedding: Optional[USREmbedding] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_image(self) -> "USRImage":
        if not self.image_paths and self.embedding is None:
            raise ValueError("image representation requires a path or embedding")
        return self


class USROCR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extracted_text: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    bounding_boxes: List[List[List[float]]] = Field(default_factory=list)
    ocr_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    language_configuration: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class USRAudioTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str = ""
    raw_transcript: str = ""
    normalized_transcript: str = ""
    language: Optional[str] = None
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class USRVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str = ""
    language: Optional[str] = None
    transcript_segments: List[Dict[str, Any]] = Field(default_factory=list)
    frame_paths: List[str] = Field(default_factory=list)
    frame_embeddings: List[USREmbedding] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnifiedSemanticRepresentation(BaseModel):
    """Intermediate multimodal representation passed to future CMREF code."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    available_modalities: List[USRModality] = Field(min_length=1)
    text: Optional[USRText] = None
    image: Optional[USRImage] = None
    ocr: Optional[USROCR] = None
    audio: Optional[USRAudioTranscript] = None
    video: Optional[USRVideo] = None
    modality_metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding_metadata: Dict[str, USREmbeddingMetadata] = Field(default_factory=dict)
    preprocessing_metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_modalities(self) -> "UnifiedSemanticRepresentation":
        if len(set(self.available_modalities)) != len(self.available_modalities):
            raise ValueError("available_modalities must not contain duplicates")

        present = set()
        if self.text is not None:
            present.add(USRModality.TEXT)
        if self.image is not None:
            present.add(USRModality.IMAGE)
        if self.ocr is not None:
            present.add(USRModality.OCR)
        if self.audio is not None:
            present.add(USRModality.AUDIO_TRANSCRIPT)
        if self.video is not None:
            if self.video.transcript or self.video.transcript_segments:
                present.add(USRModality.VIDEO_TRANSCRIPT)
            if self.video.frame_paths or self.video.frame_embeddings:
                present.add(USRModality.VIDEO_FRAMES)

        if not present:
            raise ValueError("USR requires at least one non-empty modality representation")
        if present != set(self.available_modalities):
            raise ValueError("available_modalities must match supplied representations")
        return self