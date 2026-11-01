"""Typed explainability output produced from RR evidence."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CMREAModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModalityWeight(CMREAModel):
    modality: str
    configured_weight: float = Field(ge=0)
    normalized_weight: float = Field(ge=0, le=1)
    interpretation: str


class DiagnosticSignal(CMREAModel):
    signal: str
    measurement: float
    source: str
    interpretation: str


class ReasoningPathEvent(CMREAModel):
    event: str
    source: str
    details: Dict[str, Any] = Field(default_factory=dict)


class CMREAResult(CMREAModel):
    """Explainable result; prediction and confidence remain nullable."""

    request_id: UUID
    prediction: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    confidence_status: str
    modality_weights: List[ModalityWeight] = Field(default_factory=list)
    diagnostic_signals: List[DiagnosticSignal] = Field(default_factory=list)
    reasoning_path: List[ReasoningPathEvent] = Field(default_factory=list)
    explanation: str
    uncertainty_reasons: List[str] = Field(default_factory=list)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)