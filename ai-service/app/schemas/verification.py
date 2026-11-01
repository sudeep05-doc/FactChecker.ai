"""Pydantic contract for the future verification API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class InputType(str, Enum):
    """Supported content modalities and URL sources."""

    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    AUDIO = "audio"
    VIDEO = "video"
    NEWS_URL = "news_url"
    YOUTUBE_URL = "youtube_url"


class ContentMetadata(BaseModel):
    """Normalized content or a reference to content held by the gateway."""

    model_config = ConfigDict(extra="forbid")

    text: Optional[str] = None
    url: Optional[AnyHttpUrl] = None
    file_reference: Optional[str] = Field(
        default=None,
        description="Opaque reference resolvable by the service or gateway; not a local path.",
    )
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = Field(default=None, ge=0)
    sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProcessingOptions(BaseModel):
    """Optional processing requests; values do not select or load models yet."""

    model_config = ConfigDict(extra="forbid")

    extract_text: bool = True
    transcribe_audio: bool = True
    include_explanation: bool = True
    include_modality_weights: bool = True
    include_diagnostic_signals: bool = True
    include_reasoning: bool = True
    max_processing_seconds: Optional[int] = Field(default=None, ge=1)


class VerificationRequest(BaseModel):
    """Backend-to-AI request for normalized content and processing preferences."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    input_type: InputType
    content: ContentMetadata
    processing_options: ProcessingOptions = Field(default_factory=ProcessingOptions)

    @model_validator(mode="after")
    def validate_content_source(self) -> "VerificationRequest":
        content = self.content

        if self.input_type == InputType.TEXT and not content.text:
            raise ValueError("text input requires content.text")

        if self.input_type in {InputType.NEWS_URL, InputType.YOUTUBE_URL} and not content.url:
            raise ValueError(f"{self.input_type.value} input requires content.url")

        if self.input_type in {
            InputType.IMAGE,
            InputType.PDF,
            InputType.AUDIO,
            InputType.VIDEO,
        } and not content.file_reference:
            raise ValueError(f"{self.input_type.value} input requires content.file_reference")

        return self


class ResponseStatus(str, Enum):
    """Lifecycle state of a verification request."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class Prediction(str, Enum):
    """Legacy classifier label; distinct from a factual evidence verdict."""

    LIKELY_FAKE = "LIKELY_FAKE"
    LIKELY_REAL = "LIKELY_REAL"


class PredictionType(str, Enum):
    """Identifies dataset classification versus evidence verification."""

    EVIDENCE_VERIFICATION = "evidence_verification"
    DATASET_CLASSIFICATION = "dataset_classification"


class EvidenceStatus(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    EVALUATED = "evaluated"
    FAILED = "failed"


class EvidenceVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    CHERRY_PICKING = "CHERRY_PICKING"


class ReasoningRepresentation(BaseModel):
    """Structured RR payload produced between CMREF and CMREA."""

    signals: list[str] = Field(default_factory=list)
    modality_features: dict[str, Any] = Field(default_factory=dict)
    consistency_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Consistency measurement from a defined evaluator; null when unavailable.",
    )
    consistency_status: Literal[
        "available", "unavailable", "not_run", "failed", "not_validated"
    ] = "unavailable"
    consistency_evaluator_version: Optional[str] = None
    consistency_unavailable_reason: Optional[str] = "CONSISTENCY_EVALUATOR_UNAVAILABLE"
    contradiction_detected: Optional[bool] = None
    alignment_summary: Optional[str] = None
    decision_factors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency_contract(self) -> "ReasoningRepresentation":
        if self.consistency_status == "available":
            if self.consistency_score is None or not self.consistency_evaluator_version:
                raise ValueError(
                    "available consistency requires a score and evaluator version"
                )
            if self.consistency_unavailable_reason is not None:
                raise ValueError("available consistency cannot have an unavailable reason")
        elif self.consistency_score is not None:
            raise ValueError("consistency score requires an available evaluator")
        elif not self.consistency_unavailable_reason:
            raise ValueError("unavailable consistency requires an explicit reason")
        return self


class ErrorDetail(BaseModel):
    """Machine-readable error information returned by the AI service."""

    code: str
    message: str
    field: Optional[str] = None


class VerificationResponse(BaseModel):
    """Response populated by the verification pipeline and CMREA."""

    request_id: UUID
    status: ResponseStatus
    is_mock: bool = False
    prediction_type: PredictionType = PredictionType.EVIDENCE_VERIFICATION
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_IMPLEMENTED
    verdict: Optional[EvidenceVerdict] = None
    dataset_prediction: Optional[str] = None
    model_identity: Optional[str] = None
    dataset_identity: Optional[str] = None
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="A dataset score or calibrated class probability only when its semantics are explicit; never a factual-truth score.",
    )
    confidence_semantics: Literal[
        "calibrated_class_probability",
        "uncalibrated_dataset_score",
        "not_available",
    ] = "not_available"
    explanation_provenance: Literal[
        "mock_notice",
        "evidence_evaluator",
        "dataset_classifier",
    ] = "mock_notice"
    modality_weights: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_signals: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    errors: list[ErrorDetail] = Field(default_factory=list)

    @property
    def prediction(self) -> Optional[Prediction]:
        """Return the legacy classifier label without aliasing a verdict."""
        if self.dataset_prediction is None:
            return None
        return {
            "FAKE": Prediction.LIKELY_FAKE,
            "REAL": Prediction.LIKELY_REAL,
        }[self.dataset_prediction]

    @model_validator(mode="after")
    def validate_prediction_semantics(self) -> "VerificationResponse":
        if self.is_mock:
            if (
                self.status != ResponseStatus.UNAVAILABLE
                or self.verdict is not None
                or self.dataset_prediction is not None
                or self.confidence is not None
                or self.confidence_semantics != "not_available"
                or self.evidence_status != EvidenceStatus.NOT_IMPLEMENTED
                or self.explanation_provenance != "mock_notice"
            ):
                raise ValueError(
                    "mock responses must be unavailable and contain no prediction or confidence"
                )

        if self.verdict is not None and (
            self.prediction_type != PredictionType.EVIDENCE_VERIFICATION
            or self.evidence_status != EvidenceStatus.EVALUATED
        ):
            raise ValueError(
                "an evidence verdict requires evaluated evidence verification"
            )

        if self.evidence_status == EvidenceStatus.EVALUATED and (
            self.verdict is None
            or self.is_mock
            or self.explanation_provenance != "evidence_evaluator"
        ):
            raise ValueError(
                "evaluated evidence requires a non-mock verdict and evaluator explanation provenance"
            )

        if self.dataset_prediction is not None and (
            self.prediction_type != PredictionType.DATASET_CLASSIFICATION
            or not self.dataset_identity
            or not self.model_identity
            or self.explanation_provenance != "dataset_classifier"
            or self.evidence_status != EvidenceStatus.NOT_APPLICABLE
            or self.verdict is not None
            or self.is_mock
        ):
            raise ValueError(
                "dataset predictions require classifier provenance, model identity, and dataset identity"
            )
        if self.dataset_prediction not in {None, "FAKE", "REAL"}:
            raise ValueError(
                "dataset_prediction must use the canonical FAKE or REAL label"
            )

        if self.confidence is not None and self.confidence_semantics == "not_available":
            raise ValueError("a confidence value requires explicit semantics")

        return self
