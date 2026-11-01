"""Contracts for unified foundation-model output assembly."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FoundationIssue(BaseModel):
    code: str
    message: str
    modality: Optional[str] = None
    stage: str = "foundation"


class FoundationAssemblyResult(BaseModel):
    request_id: UUID
    active_modalities: List[str] = Field(default_factory=list)
    successful_modalities: List[str] = Field(default_factory=list)
    omitted_modalities: List[str] = Field(default_factory=list)
    failed_modalities: List[str] = Field(default_factory=list)
    usr: Optional[Any] = None
    cmref_result: Optional[Any] = None
    provenance: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[FoundationIssue] = Field(default_factory=list)
    errors: List[FoundationIssue] = Field(default_factory=list)
