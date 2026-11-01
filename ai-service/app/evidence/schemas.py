"""Strict, model-independent claim and evidence records.

These contracts validate supplied annotations and provenance. They do not
retrieve evidence, infer relationships, or determine factual verdicts.
"""

from datetime import date, datetime
from enum import Enum
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


def _validate_nonblank_values(value: object, path: str = "value") -> None:
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{path} cannot be blank")
    if isinstance(value, dict):
        for key, nested_value in value.items():
            _validate_nonblank_values(nested_value, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested_value in enumerate(value):
            _validate_nonblank_values(nested_value, f"{path}[{index}]")


def _require_timezone_aware(value: Optional[datetime], field_name: str) -> None:
    if value is None:
        return
    try:
        has_timezone = value.tzinfo is not None and value.utcoffset() is not None
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} has invalid timezone metadata") from error
    if not has_timezone:
        raise ValueError(f"{field_name} must include a valid timezone")


class EvidenceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_blank_strings(cls, value: object) -> object:
        _validate_nonblank_values(value)
        return value

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "EvidenceModel":
        data = self.model_dump(mode="python", round_trip=True)
        if deep:
            data = deepcopy(data)
        data.update(update or {})
        return self.__class__.model_validate(data)

    @classmethod
    def model_construct(
        cls, _fields_set: Optional[set[str]] = None, **values: Any
    ) -> "EvidenceModel":
        supplied_fields = len(values) + int(_fields_set is not None)
        raise TypeError(
            "model_construct() is disabled for evidence contracts; "
            f"use model_validate() instead ({supplied_fields} supplied fields)"
        )

    def model_dump(self, **kwargs: Any) -> Any:
        self.__class__.model_validate(self)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs: Any) -> str:
        self.__class__.model_validate(self)
        return super().model_dump_json(**kwargs)


class ClaimAtomicity(str, Enum):
    ATOMIC = "ATOMIC"
    COMPOUND = "COMPOUND"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_ASSESSED = "NOT_ASSESSED"


class ClaimModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    MULTIMODAL = "multimodal"
    UNKNOWN = "unknown"


class ClaimEntity(EvidenceModel):
    mention: str = Field(min_length=1)
    entity_type: Optional[str] = None
    normalized_identity: Optional[str] = None
    source_span: Optional[str] = None


class ClaimRelation(EvidenceModel):
    subject: Optional[str] = None
    predicate: str = Field(min_length=1)
    object: Optional[str] = None
    polarity: Optional[str] = None
    modality: Optional[str] = None
    condition: Optional[str] = None


class ClaimQuantity(EvidenceModel):
    value: str = Field(min_length=1)
    unit: Optional[str] = None
    comparator: Optional[str] = None
    denominator: Optional[str] = None
    source_span: Optional[str] = None


class ClaimTemporalScope(EvidenceModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    reference_text: Optional[str] = None
    as_of: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_interval(self) -> "ClaimTemporalScope":
        _require_timezone_aware(self.start, "start")
        _require_timezone_aware(self.end, "end")
        _require_timezone_aware(self.as_of, "as_of")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("temporal scope start cannot be after end")
        return self


class ClaimGeographicScope(EvidenceModel):
    place: Optional[str] = None
    geographic_unit: Optional[str] = None
    resolution_status: Optional[str] = None


class ClaimAttribution(EvidenceModel):
    speaker: Optional[str] = None
    reporting_action: Optional[str] = None
    source_span: Optional[str] = None


class AtomicClaim(EvidenceModel):
    atomic_claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_span: Optional[str] = None


class ExtractionProvenanceStatus(str, Enum):
    RECORDED = "RECORDED"
    NOT_RECORDED = "NOT_RECORDED"


class ExtractionProvenance(EvidenceModel):
    status: ExtractionProvenanceStatus = ExtractionProvenanceStatus.NOT_RECORDED
    input_reference: Optional[str] = None
    method: Optional[str] = None
    method_version: Optional[str] = None
    extracted_at: Optional[datetime] = None
    annotator_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_recorded_provenance(self) -> "ExtractionProvenance":
        if self.status == ExtractionProvenanceStatus.RECORDED and not self.method:
            raise ValueError("recorded extraction provenance requires a method")
        _require_timezone_aware(self.extracted_at, "extracted_at")
        return self


class ClaimRecord(EvidenceModel):
    claim_id: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    normalized_text: Optional[str] = None
    atomicity: ClaimAtomicity = ClaimAtomicity.NOT_ASSESSED
    atomic_claims: Optional[Tuple[AtomicClaim, ...]] = None
    entities: Optional[Tuple[ClaimEntity, ...]] = None
    relations: Optional[Tuple[ClaimRelation, ...]] = None
    quantities: Optional[Tuple[ClaimQuantity, ...]] = None
    temporal_scope: Optional[ClaimTemporalScope] = None
    geographic_scope: Optional[ClaimGeographicScope] = None
    attribution: Optional[ClaimAttribution] = None
    context: Optional[str] = None
    population_scope: Optional[str] = None
    modality: Optional[Tuple[ClaimModality, ...]] = None
    extraction_provenance: ExtractionProvenance = Field(
        default_factory=ExtractionProvenance
    )

    @model_validator(mode="after")
    def validate_claim_structure(self) -> "ClaimRecord":
        if not self.original_text.strip():
            raise ValueError("original_text cannot be blank")
        if self.normalized_text is not None and not self.normalized_text.strip():
            raise ValueError("normalized_text must be null or non-blank")
        if self.atomic_claims is not None:
            identifiers = [item.atomic_claim_id for item in self.atomic_claims]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("atomic_claim_id values must be unique")
        if self.atomicity == ClaimAtomicity.COMPOUND and not self.atomic_claims:
            raise ValueError("compound claims require recorded atomic_claims")
        return self


class EvidenceModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    STRUCTURED_DATA = "structured_data"
    MULTIMODAL = "multimodal"
    UNKNOWN = "unknown"


class ProvenanceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIABLE = "UNVERIFIABLE"
    NOT_RECORDED = "NOT_RECORDED"


class EvidenceProvenance(EvidenceModel):
    status: ProvenanceStatus = ProvenanceStatus.NOT_RECORDED
    document_reference: Optional[str] = None
    document_version: Optional[str] = None
    content_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )
    passage_locator: Optional[str] = None
    notes: Optional[str] = None


class RetrievalStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    COMPLETED_WITH_RESULTS = "COMPLETED_WITH_RESULTS"
    COMPLETED_EMPTY = "COMPLETED_EMPTY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"
    NOT_RECORDED = "NOT_RECORDED"


class RetrievalMethod(EvidenceModel):
    method: str = Field(min_length=1)
    status: RetrievalStatus = RetrievalStatus.NOT_RECORDED
    connector_version: Optional[str] = None
    query_reference: Optional[str] = None
    notes: Optional[str] = None


class SourceAdequacy(str, Enum):
    ADEQUATE = "ADEQUATE"
    INADEQUATE = "INADEQUATE"
    UNKNOWN = "UNKNOWN"
    NOT_ASSESSED = "NOT_ASSESSED"


class SourceReliabilityAssessment(EvidenceModel):
    """Qualitative, claim-specific assessment; deliberately has no score."""

    adequacy: SourceAdequacy = SourceAdequacy.NOT_ASSESSED
    source_kind: Optional[str] = None
    directness: Optional[str] = None
    identity_review: Optional[str] = None
    temporal_fit: Optional[str] = None
    independence: Optional[str] = None
    methodology_review: Optional[str] = None
    correction_status: Optional[str] = None
    limitations: Optional[str] = None
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def require_assessment_rationale(self) -> "SourceReliabilityAssessment":
        if (
            self.adequacy in {SourceAdequacy.ADEQUATE, SourceAdequacy.INADEQUATE}
            and not self.rationale
        ):
            raise ValueError("assessed source adequacy requires a rationale")
        return self


class ExtractionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    MISSING_PASSAGE = "MISSING_PASSAGE"
    NOT_EXTRACTED = "NOT_EXTRACTED"
    FAILED = "FAILED"


class EvidenceSpan(EvidenceModel):
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    exact_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_span(self) -> "EvidenceSpan":
        if self.end_char <= self.start_char:
            raise ValueError("evidence span end_char must be greater than start_char")
        return self


class EvidenceRecord(EvidenceModel):
    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_title: Optional[str] = None
    source_url: Optional[AnyHttpUrl] = None
    local_reference: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[date] = None
    acquisition_timestamp: Optional[datetime] = None
    extracted_passage: Optional[str] = None
    source_modality: EvidenceModality = EvidenceModality.UNKNOWN
    retrieval_method: Optional[RetrievalMethod] = None
    provenance: EvidenceProvenance = Field(default_factory=EvidenceProvenance)
    source_reliability_assessment: SourceReliabilityAssessment = Field(
        default_factory=SourceReliabilityAssessment
    )
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_EXTRACTED
    extraction_method: Optional[str] = None

    @model_validator(mode="after")
    def validate_evidence_record(self) -> "EvidenceRecord":
        if self.local_reference is not None and not self.local_reference.strip():
            raise ValueError("local_reference must be null or non-blank")
        _require_timezone_aware(
            self.acquisition_timestamp, "acquisition_timestamp"
        )
        if self.provenance.status == ProvenanceStatus.VERIFIED:
            if not (self.source_url or self.local_reference):
                raise ValueError(
                    "verified provenance requires source_url or local_reference"
                )
            if not self.provenance.document_reference:
                raise ValueError(
                    "verified provenance requires a document_reference"
                )
            if self.acquisition_timestamp is None:
                raise ValueError(
                    "verified provenance requires acquisition_timestamp"
                )
            if self.acquisition_timestamp.tzinfo is None:
                raise ValueError("acquisition_timestamp must include a timezone")
        if self.extraction_status == ExtractionStatus.AVAILABLE:
            if self.extracted_passage is None or not self.extracted_passage.strip():
                raise ValueError(
                    "AVAILABLE extraction_status requires extracted_passage"
                )
        elif self.extracted_passage is not None:
            if self.extraction_status in {
                ExtractionStatus.MISSING_PASSAGE,
                ExtractionStatus.NOT_EXTRACTED,
                ExtractionStatus.FAILED,
            }:
                raise ValueError(
                    "missing, unextracted, or failed passage status cannot contain extracted_passage"
                )
        return self


class EvidenceRelationshipLabel(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    PARTIALLY_SUPPORTS = "PARTIALLY_SUPPORTS"
    PARTIALLY_REFUTES = "PARTIALLY_REFUTES"
    NEUTRAL = "NEUTRAL"
    CONTRADICTS = "CONTRADICTS"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ScopeMatchStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ASSESSED = "NOT_ASSESSED"


class EvidenceScopeComparison(EvidenceModel):
    """Explicit claim-to-passage scope annotations; never inferred here."""

    entity: ScopeMatchStatus = ScopeMatchStatus.NOT_ASSESSED
    temporal: ScopeMatchStatus = ScopeMatchStatus.NOT_ASSESSED
    geographic: ScopeMatchStatus = ScopeMatchStatus.NOT_ASSESSED
    population: ScopeMatchStatus = ScopeMatchStatus.NOT_ASSESSED
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rationale(self) -> "EvidenceScopeComparison":
        if not self.rationale.strip():
            raise ValueError("scope comparison rationale cannot be blank")
        return self

    def is_comparable(self) -> bool:
        return all(
            status in {ScopeMatchStatus.MATCH, ScopeMatchStatus.NOT_APPLICABLE}
            for status in (
                self.entity,
                self.temporal,
                self.geographic,
                self.population,
            )
        )


class EvidenceRelationship(EvidenceModel):
    relationship_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    label: EvidenceRelationshipLabel
    rationale: str = Field(min_length=1)
    atomic_claim_id: Optional[str] = None
    related_evidence_id: Optional[str] = None
    supporting_span: Optional[EvidenceSpan] = None
    scope_comparison: Optional[EvidenceScopeComparison] = None

    @model_validator(mode="after")
    def validate_relationship_shape(self) -> "EvidenceRelationship":
        if not self.rationale.strip():
            raise ValueError("relationship rationale cannot be blank")
        if self.label == EvidenceRelationshipLabel.CONTRADICTS:
            if not self.related_evidence_id:
                raise ValueError(
                    "CONTRADICTS requires a related_evidence_id"
                )
            if self.related_evidence_id == self.evidence_id:
                raise ValueError("CONTRADICTS must reference two distinct evidence records")
        elif self.related_evidence_id is not None:
            raise ValueError(
                "related_evidence_id is only valid for CONTRADICTS"
            )
        return self


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class AssessmentStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    ASSESSED = "ASSESSED"


class AbstentionReason(str, Enum):
    NO_EVIDENCE_RETRIEVED = "NO_EVIDENCE_RETRIEVED"
    INSUFFICIENT_EVIDENCE_QUALITY = "INSUFFICIENT_EVIDENCE_QUALITY"
    CONFLICTING_CREDIBLE_EVIDENCE = "CONFLICTING_CREDIBLE_EVIDENCE"
    AMBIGUOUS_CLAIM = "AMBIGUOUS_CLAIM"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    UNSUPPORTED_MODALITY = "UNSUPPORTED_MODALITY"
    PROVENANCE_UNVERIFIABLE = "PROVENANCE_UNVERIFIABLE"
    EVALUATION_FAILURE = "EVALUATION_FAILURE"


class ClaimAssessment(EvidenceModel):
    claim_id: str = Field(min_length=1)
    status: AssessmentStatus = AssessmentStatus.NOT_ASSESSED
    verdict: Optional[Verdict] = None
    abstention_reasons: Tuple[AbstentionReason, ...] = Field(default_factory=tuple)
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def validate_assessment_state(self) -> "ClaimAssessment":
        if len(set(self.abstention_reasons)) != len(self.abstention_reasons):
            raise ValueError("abstention_reasons must not contain duplicates")
        if self.status == AssessmentStatus.ASSESSED:
            if self.verdict is None or not self.rationale or not self.rationale.strip():
                raise ValueError("ASSESSED requires a verdict and non-blank rationale")
            if (
                self.verdict == Verdict.INSUFFICIENT_EVIDENCE
                and not self.abstention_reasons
            ):
                raise ValueError(
                    "INSUFFICIENT_EVIDENCE requires at least one abstention reason"
                )
            if (
                self.verdict == Verdict.CONFLICTING_EVIDENCE
                and AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE
                not in self.abstention_reasons
            ):
                raise ValueError(
                    "CONFLICTING_EVIDENCE requires CONFLICTING_CREDIBLE_EVIDENCE"
                )
            if AbstentionReason.EVALUATION_FAILURE in self.abstention_reasons:
                raise ValueError(
                    "EVALUATION_FAILURE is a processing state, not an assessed verdict reason"
                )
        else:
            if self.verdict is not None:
                raise ValueError(
                    "processing states cannot be represented as factual verdicts"
                )
            if (
                self.status == AssessmentStatus.NOT_ASSESSED
                and self.abstention_reasons
            ):
                raise ValueError(
                    "NOT_ASSESSED cannot carry active abstention reasons"
                )
            if self.status == AssessmentStatus.EVALUATION_FAILED:
                if self.abstention_reasons != (
                    AbstentionReason.EVALUATION_FAILURE,
                ):
                    raise ValueError(
                        "EVALUATION_FAILED requires only the EVALUATION_FAILURE reason"
                    )
            elif AbstentionReason.EVALUATION_FAILURE in self.abstention_reasons:
                raise ValueError(
                    "EVALUATION_FAILURE requires EVALUATION_FAILED status"
                )
        return self
