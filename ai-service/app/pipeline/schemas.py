"""Typed orchestration and decision-boundary schemas."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class PipelineIssue(BaseModel):
    code: str
    message: str
    modality: Optional[str] = None
    stage: Optional[str] = None


class DecisionCalibrationResult(BaseModel):
    """Decision boundary output; absent calibration remains explicitly null."""

    model_config = ConfigDict(extra="forbid")

    prediction: Optional[str] = None
    raw_probability: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Uncalibrated probability of FAKE; probability of REAL is 1 minus this value.",
    )
    calibrated_probability: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Calibrated probability of FAKE; probability of REAL is 1 minus this value.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Calibrated probability of the predicted class, not a factual truth score; null when calibration is unavailable.",
    )
    status: str = "unavailable"
    reason: str = "CALIBRATION_UNAVAILABLE"
    feature_schema_version: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerificationPipelineResult(BaseModel):
    """Internal/future gateway result assembled from every pipeline stage."""

    request_id: UUID
    status: PipelineStatus
    available_modalities: List[str] = Field(default_factory=list)
    omitted_modalities: List[str] = Field(default_factory=list)
    prediction: Optional[str] = None
    calibrated_confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Calibrated probability of the predicted class, not factual truth confidence.",
    )
    reasoning_score: Optional[float] = None
    modality_weights: List[Dict[str, Any]] = Field(default_factory=list)
    diagnostic_signals: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_path: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: Optional[str] = None
    uncertainty: List[str] = Field(default_factory=list)
    evidence: Optional[Dict[str, Any]] = None
    errors: List[PipelineIssue] = Field(default_factory=list)
    warnings: List[PipelineIssue] = Field(default_factory=list)
    model_versions: Dict[str, str] = Field(default_factory=dict)
    configuration_versions: Dict[str, str] = Field(default_factory=dict)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)