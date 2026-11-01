"""Fail-closed NLI relationship evaluation for one claim/passage pair."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
import unicodedata
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evidence.schemas import (
    AssessmentStatus,
    ClaimAttribution,
    ClaimAtomicity,
    ClaimGeographicScope,
    ClaimQuantity,
    ClaimRecord,
    ClaimTemporalScope,
    EvidenceRecord,
    EvidenceRelationship,
    EvidenceRelationshipLabel,
    EvidenceScopeComparison,
    EvidenceSpan,
    ExtractionStatus,
    RetrievalStatus,
    ScopeMatchStatus,
)
from app.evidence.trust import (
    _authorized_reasoning_representations,
    _evaluator_results,
    _contains_directional_content,
    _is_authorized_reasoning_representation,
    _is_directional_label,
    _is_evaluator_result,
)
from app.rr.evidence import EvidenceEvaluationRR


class NLIClass(str, Enum):
    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


class NLIScoreKind(str, Enum):
    LOGITS = "logits"
    PROBABILITIES = "probabilities"


class InferenceStatus(str, Enum):
    INFERENCE_SUCCEEDED = "INFERENCE_SUCCEEDED"
    COMPLETED = "COMPLETED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"


class EvaluationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    AMBIGUOUS_MODEL_OUTPUT = "AMBIGUOUS_MODEL_OUTPUT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    LANGUAGE_UNSPECIFIED = "LANGUAGE_UNSPECIFIED"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    MISSING_EVIDENCE_PASSAGE = "MISSING_EVIDENCE_PASSAGE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    SCOPE_UNASSESSED = "SCOPE_UNASSESSED"


class ScopeVerificationState(str, Enum):
    """Trust state of independent scope assessment, separate from NLI labels."""

    VERIFIED_COMPATIBLE = "VERIFIED_COMPATIBLE"
    VERIFIED_MISMATCH = "VERIFIED_MISMATCH"
    UNVERIFIED = "UNVERIFIED"


_SUCCESSFUL_INFERENCE_STATUSES = {
    InferenceStatus.INFERENCE_SUCCEEDED,
    InferenceStatus.COMPLETED,
}


class ScopeDimensionAssessment(BaseModel):
    """Caller-reviewed structured scope comparison, not automatic extraction."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    status: ScopeMatchStatus = ScopeMatchStatus.NOT_ASSESSED
    claim_value: Optional[str] = None
    evidence_value: Optional[str] = None
    evidence_basis: Optional[str] = None
    rationale: str = "No reviewed evidence-side scope annotation was supplied."

    @model_validator(mode="after")
    def validate_assessment(self) -> "ScopeDimensionAssessment":
        if not self.rationale.strip():
            raise ValueError("scope assessment rationale cannot be blank")
        if self.status in {ScopeMatchStatus.MATCH, ScopeMatchStatus.MISMATCH}:
            if not self.claim_value or not self.claim_value.strip():
                raise ValueError("assessed scope requires a claim_value")
            if not self.evidence_value or not self.evidence_value.strip():
                raise ValueError("assessed scope requires an evidence_value")
            if not self.evidence_basis or not self.evidence_basis.strip():
                raise ValueError("assessed scope requires an evidence_basis")
            if self.status == ScopeMatchStatus.MATCH and self.claim_value != self.evidence_value:
                raise ValueError("MATCH requires equal canonical scope values")
            if self.status == ScopeMatchStatus.MISMATCH and self.claim_value == self.evidence_value:
                raise ValueError("MISMATCH requires different canonical scope values")
        elif self.status == ScopeMatchStatus.NOT_APPLICABLE:
            if not self.evidence_basis or not self.evidence_basis.strip():
                raise ValueError("NOT_APPLICABLE requires an explicit evidence_basis")
        return self


class EvidenceScopeAssessment(BaseModel):
    """Explicit scope annotations supplied for the evaluated evidence passage.

    These annotations are assertions from a caller/reviewer. This model does
    not extract values from text or independently prove their semantics.
    Without an independent verifier, their trust state remains UNVERIFIED.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    verification_state: ScopeVerificationState = ScopeVerificationState.UNVERIFIED
    entity: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    quantity: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    unit: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    temporal: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    geographic: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    population: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    attribution: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    polarity: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)
    conditional: ScopeDimensionAssessment = Field(default_factory=ScopeDimensionAssessment)

    @model_validator(mode="after")
    def validate_verification_state(self) -> "EvidenceScopeAssessment":
        if self.verification_state != ScopeVerificationState.UNVERIFIED:
            raise ValueError(
                "scope verification is unavailable; caller annotations must remain UNVERIFIED"
            )
        return self

    def dimensions(self) -> Tuple[ScopeDimensionAssessment, ...]:
        return (
            self.entity,
            self.quantity,
            self.unit,
            self.temporal,
            self.geographic,
            self.population,
            self.attribution,
            self.polarity,
            self.conditional,
        )

    def has_mismatch(self) -> bool:
        return any(
            item.status == ScopeMatchStatus.MISMATCH
            for item in self.dimensions()
        )

    def has_only_compatible_annotations(self) -> bool:
        return all(
            item.status
            in {ScopeMatchStatus.MATCH, ScopeMatchStatus.NOT_APPLICABLE}
            for item in self.dimensions()
        )

    def is_verified_compatible(self) -> bool:
        return (
            self.verification_state == ScopeVerificationState.VERIFIED_COMPATIBLE
            and self.has_only_compatible_annotations()
        )

    def to_contract_comparison(self) -> EvidenceScopeComparison:
        statuses = {
            name: getattr(self, name).status
            for name in ("entity", "temporal", "geographic", "population")
        }
        details = ", ".join(
            f"{name}={getattr(self, name).status.value}"
            for name in (
                "entity",
                "quantity",
                "unit",
                "temporal",
                "geographic",
                "population",
                "attribution",
                "polarity",
                "conditional",
            )
        )
        return EvidenceScopeComparison(
            **statuses,
            rationale=(
                f"Structured scope annotations: {details}. "
                "These caller-supplied annotations are not independently verified."
            ),
        )


class ModelLoadError(RuntimeError):
    """Typed signal that a configured model failed before inference."""

    def __init__(self, model_identity: str, detail: str) -> None:
        super().__init__(detail)
        if not model_identity.strip():
            raise ValueError("model_identity must be non-blank")
        self.model_identity = model_identity


class NLIClassDecoder:
    """Decode raw class scores using a model's explicit configuration maps."""

    _LABELS = {
        "entailment": NLIClass.ENTAILMENT,
        "contradiction": NLIClass.CONTRADICTION,
        "neutral": NLIClass.NEUTRAL,
    }

    def __init__(self, index_to_class: Mapping[int, NLIClass]) -> None:
        _validate_decoder_mapping(index_to_class, len(NLIClass))
        self._index_to_class = dict(index_to_class)

    @classmethod
    def from_model_config(
        cls,
        model_config: object,
        *,
        output_dimensions: int,
    ) -> "NLIClassDecoder":
        if output_dimensions != len(NLIClass):
            raise ValueError("NLI output dimension must be exactly three")
        declared_num_labels = _configuration_value(model_config, "num_labels")
        if declared_num_labels is not None:
            if (
                not isinstance(declared_num_labels, int)
                or isinstance(declared_num_labels, bool)
                or declared_num_labels != output_dimensions
            ):
                raise ValueError(
                    "model configuration num_labels does not match output dimensions"
                )

        id2label = _configuration_value(model_config, "id2label")
        label2id = _configuration_value(model_config, "label2id")
        if id2label is None and label2id is None:
            raise ValueError("model configuration has no NLI label mapping")

        decoded_id2label = _decode_id2label(id2label, output_dimensions) if id2label is not None else None
        decoded_label2id = _decode_label2id(label2id, output_dimensions) if label2id is not None else None
        if (
            decoded_id2label is not None
            and decoded_label2id is not None
            and decoded_id2label != decoded_label2id
        ):
            raise ValueError("id2label and label2id mappings disagree")
        mapping = decoded_id2label or decoded_label2id
        if mapping is None or set(mapping) != set(range(output_dimensions)):
            raise ValueError("NLI label mapping is incomplete")
        if set(mapping.values()) != set(NLIClass):
            raise ValueError("NLI label mapping must identify each class exactly once")
        return cls(mapping)

    def decode(
        self,
        raw_scores: Sequence[float],
        *,
        score_kind: NLIScoreKind,
    ) -> Tuple[NLIScore, ...]:
        score_kind = NLIScoreKind(score_kind)
        if isinstance(raw_scores, (str, bytes)) or len(raw_scores) != len(self._index_to_class):
            raise ValueError("model output dimension does not match configured NLI labels")
        decoded = []
        for index, value in enumerate(raw_scores):
            score = NLIScore(label=self._index_to_class[index], value=value)
            decoded.append(score)
        if score_kind == NLIScoreKind.PROBABILITIES:
            values = [score.value for score in decoded]
            if any(not 0 <= value <= 1 for value in values):
                raise ValueError("probability scores must be in [0, 1]")
            if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-4):
                raise ValueError("probability scores must sum to 1")
        return tuple(decoded)


def _configuration_value(config: object, name: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(name)
    return getattr(config, name, None)


def _class_for_model_label(label: object) -> NLIClass:
    if not isinstance(label, str):
        raise ValueError("model label names must be strings")
    semantic_class = NLIClassDecoder._LABELS.get(label.strip().casefold())
    if semantic_class is None:
        raise ValueError(f"unknown NLI model label: {label!r}")
    return semantic_class


def _decode_id2label(
    mapping: object,
    output_dimensions: int,
) -> dict[int, NLIClass]:
    if not isinstance(mapping, Mapping):
        raise ValueError("id2label must be a mapping")
    result: dict[int, NLIClass] = {}
    for raw_index, raw_label in mapping.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as error:
            raise ValueError("id2label indexes must be integers") from error
        if isinstance(raw_index, bool) or str(index) != str(raw_index):
            raise ValueError("id2label indexes must be canonical integers")
        if index in result:
            raise ValueError("id2label indexes must be unique")
        result[index] = _class_for_model_label(raw_label)
    _validate_decoder_mapping(result, output_dimensions)
    return result


def _decode_label2id(
    mapping: object,
    output_dimensions: int,
) -> dict[int, NLIClass]:
    if not isinstance(mapping, Mapping):
        raise ValueError("label2id must be a mapping")
    result: dict[int, NLIClass] = {}
    seen_classes = set()
    for raw_label, raw_index in mapping.items():
        semantic_class = _class_for_model_label(raw_label)
        if semantic_class in seen_classes:
            raise ValueError("label2id contains duplicate semantic mappings")
        seen_classes.add(semantic_class)
        if not isinstance(raw_index, int) or isinstance(raw_index, bool):
            raise ValueError("label2id indexes must be integers")
        if raw_index in result:
            raise ValueError("label2id indexes must be unique")
        result[raw_index] = semantic_class
    _validate_decoder_mapping(result, output_dimensions)
    return result


def _validate_decoder_mapping(
    mapping: Mapping[int, NLIClass],
    output_dimensions: int,
) -> None:
    if any(not isinstance(index, int) or isinstance(index, bool) for index in mapping):
        raise ValueError("NLI label indexes must be integers")
    if any(not isinstance(label, NLIClass) for label in mapping.values()):
        raise ValueError("NLI label mappings must use canonical NLIClass values")
    if set(mapping) != set(range(output_dimensions)):
        raise ValueError("NLI label mapping is incomplete or has invalid indexes")
    if len(set(mapping.values())) != len(NLIClass):
        raise ValueError("NLI label mapping has duplicate semantic mappings")


class NLIScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: NLIClass
    value: float

    @model_validator(mode="after")
    def validate_finite_score(self) -> "NLIScore":
        if not math.isfinite(self.value):
            raise ValueError("NLI score must be finite")
        return self


class NLIInference(BaseModel):
    """Raw NLI output; scores are model outputs, not factual confidence."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    status: InferenceStatus
    model_identity: Optional[str] = None
    model_version: Optional[str] = None
    scores: Optional[Tuple[NLIScore, ...]] = None
    score_kind: Optional[NLIScoreKind] = None
    detail: Optional[str] = None

    @model_validator(mode="after")
    def validate_inference_payload(self) -> "NLIInference":
        if self.status in _SUCCESSFUL_INFERENCE_STATUSES:
            if not self.model_identity or not self.model_version:
                raise ValueError("completed NLI output requires model identity and version")
            if not self.scores or {score.label for score in self.scores} != set(NLIClass):
                raise ValueError("completed NLI output requires all three class scores")
            if len(self.scores) != len(NLIClass):
                raise ValueError("NLI class scores must be unique")
            if self.score_kind is None:
                raise ValueError("completed NLI output requires score_kind")
            if self.score_kind == NLIScoreKind.PROBABILITIES:
                if any(not 0 <= score.value <= 1 for score in self.scores):
                    raise ValueError("probability scores must be in [0, 1]")
                if not math.isclose(
                    sum(score.value for score in self.scores),
                    1.0,
                    rel_tol=0.0,
                    abs_tol=1e-4,
                ):
                    raise ValueError("probability scores must sum to 1")
            if self.detail is not None:
                raise ValueError("completed NLI output cannot carry failure detail")
        else:
            if self.scores is not None or self.score_kind is not None:
                raise ValueError("failed NLI inference cannot carry class scores")
            if not self.detail or not self.detail.strip():
                raise ValueError("failed NLI inference requires an explicit detail")
            if self.status == InferenceStatus.MODEL_UNAVAILABLE:
                if self.model_identity is not None or self.model_version is not None:
                    raise ValueError("unavailable model cannot claim configured model identity")
            elif self.status == InferenceStatus.MODEL_LOAD_FAILED:
                if not self.model_identity or self.model_version is not None:
                    raise ValueError(
                        "model-load failure requires configured model identity only"
                    )
            elif self.status == InferenceStatus.INFERENCE_FAILED:
                if not self.model_identity or not self.model_version:
                    raise ValueError("inference failure requires loaded model identity and version")
        return self


class NLIBackend(Protocol):
    """Injectable interface; available means an approved model is configured.

    Lazy adapters report loading failures as MODEL_LOAD_FAILED or raise
    ModelLoadError. Ordinary failures after loading are inference failures.
    """

    available: bool
    supported_languages: Tuple[str, ...]
    model_identity: Optional[str]
    model_version: Optional[str]

    def infer(self, premise: str, hypothesis: str) -> NLIInference:
        """Return validated raw NLI outputs for a premise/hypothesis pair."""


class UnavailableNLIBackend:
    """Default backend when no approved local NLI model is configured."""

    available = False
    supported_languages: Tuple[str, ...] = ()
    model_identity: Optional[str] = None
    model_version: Optional[str] = None

    def infer(self, premise: str, hypothesis: str) -> NLIInference:
        del premise, hypothesis
        return NLIInference(
            status=InferenceStatus.MODEL_UNAVAILABLE,
            detail="No licensed, compatible local NLI model is configured.",
        )


class EvidenceRelationshipEvaluation(BaseModel):
    """Auditable one-pair output, including failure states and RR edge."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    evaluation_id: UUID
    claim_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    atomic_proposition_id: Optional[str] = None
    claim_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_extraction_status: ExtractionStatus
    evidence_passage_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    relationship: Optional[EvidenceRelationship] = None
    evaluator_identity: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    model_identity: Optional[str] = None
    model_version: Optional[str] = None
    raw_nli_scores: Optional[Tuple[NLIScore, ...]] = None
    score_kind: Optional[NLIScoreKind] = None
    calibration_status: str = "NOT_EVALUATED"
    inference_status: EvaluationStatus
    scope_assessment: EvidenceScopeAssessment
    provenance_references: Tuple[str, ...] = ()
    evaluated_at: datetime
    failure_detail: Optional[str] = None
    limitations: Tuple[str, ...] = Field(
        default=(
            "Entity, quantity, unit, temporal, geographic, population, attribution, "
            "negation, modality, and conditional scope are not independently assessed.",
            "NLI class scores are uncalibrated model outputs, not factual confidence.",
            "Source reliability and retrieval quality are not combined with NLI scores.",
        )
    )

    @model_validator(mode="after")
    def validate_evaluation_output(self) -> "EvidenceRelationshipEvaluation":
        EvidenceScopeAssessment.model_validate(self.scope_assessment)
        has_scores = self.raw_nli_scores is not None
        if self.evidence_extraction_status == ExtractionStatus.AVAILABLE:
            if self.evidence_passage_sha256 is None:
                raise ValueError("available evidence passage requires its fingerprint")

        if self.inference_status == EvaluationStatus.COMPLETED:
            if self.relationship is None or not has_scores or not self.model_identity or not self.model_version:
                raise ValueError("completed evaluation requires relationship and model output")
            if not self.atomic_proposition_id:
                raise ValueError("completed evaluation requires an atomic proposition identifier")
            if self.score_kind is None or self.failure_detail is not None:
                raise ValueError("completed evaluation has inconsistent inference metadata")
            self._validate_successful_model_output()
            if self.relationship.label not in {
                EvidenceRelationshipLabel.SUPPORTS,
                EvidenceRelationshipLabel.REFUTES,
                EvidenceRelationshipLabel.NEUTRAL,
            }:
                raise ValueError("NLI cannot assign partial, evidence-conflict, or context labels")
            self._validate_relationship_identity()
            if self.relationship.label != _relationship_for(_highest_score(self.raw_nli_scores)):
                raise ValueError("relationship label must match the NLI output mapping")
            if self.scope_assessment.has_mismatch():
                raise ValueError("scope mismatch cannot produce an ordinary relationship")
            if (
                self.relationship.label
                in {EvidenceRelationshipLabel.SUPPORTS, EvidenceRelationshipLabel.REFUTES}
                and not self.scope_assessment.is_verified_compatible()
            ):
                raise ValueError(
                    "directional relationship requires independently verified compatible scope"
                )
            self._validate_relationship_scope()
        elif self.inference_status == EvaluationStatus.MISSING_EVIDENCE_PASSAGE:
            if self.relationship is None or self.relationship.label != EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT:
                raise ValueError("missing passage must be represented as INSUFFICIENT_CONTEXT")
            if (
                has_scores
                or self.model_identity is not None
                or self.model_version is not None
                or self.score_kind is not None
                or not self.failure_detail
                or self.evidence_extraction_status == ExtractionStatus.AVAILABLE
                and self.evidence_passage_sha256 is not None
            ):
                raise ValueError("missing passage cannot carry model inference output")
            self._validate_relationship_identity()
            self._validate_relationship_scope()
        elif self.inference_status == EvaluationStatus.AMBIGUOUS_MODEL_OUTPUT:
            if (
                self.relationship is not None
                or not has_scores
                or not self.model_identity
                or not self.model_version
                or self.score_kind is None
                or not self.failure_detail
            ):
                raise ValueError(
                    "ambiguous model output requires model scores and detail but no relationship"
                )
            self._validate_successful_model_output()
            try:
                _highest_score(self.raw_nli_scores)
            except ValueError:
                pass
            else:
                raise ValueError("ambiguous model output requires tied top scores")
        elif self.inference_status in {
            EvaluationStatus.SCOPE_MISMATCH,
            EvaluationStatus.SCOPE_UNASSESSED,
        }:
            if (
                self.relationship is None
                or self.relationship.label != EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
                or not has_scores
                or not self.model_identity
                or not self.model_version
                or self.score_kind is None
                or not self.failure_detail
                or self.evidence_extraction_status != ExtractionStatus.AVAILABLE
            ):
                raise ValueError(
                    "scope-blocked evaluation requires model output and INSUFFICIENT_CONTEXT"
                )
            self._validate_successful_model_output()
            self._validate_relationship_identity()
            self._validate_relationship_scope()
            if self.inference_status == EvaluationStatus.SCOPE_MISMATCH:
                if (
                    self.scope_assessment.verification_state
                    != ScopeVerificationState.VERIFIED_MISMATCH
                ):
                    raise ValueError(
                        "SCOPE_MISMATCH requires independently verified mismatch"
                    )
            elif self.scope_assessment.verification_state != ScopeVerificationState.UNVERIFIED:
                raise ValueError("SCOPE_UNASSESSED requires unverified scope")
        else:
            self._validate_failure_state(has_scores)
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if self.calibration_status != "NOT_EVALUATED":
            raise ValueError("calibration is not evaluated by this baseline")
        return self

    def _validate_successful_model_output(self) -> None:
        if (
            self.model_identity is None
            or self.model_version is None
            or self.raw_nli_scores is None
            or self.score_kind is None
        ):
            raise ValueError("successful model output metadata is incomplete")
        NLIInference(
            status=InferenceStatus.INFERENCE_SUCCEEDED,
            model_identity=self.model_identity,
            model_version=self.model_version,
            scores=self.raw_nli_scores,
            score_kind=self.score_kind,
        )

    def _validate_relationship_identity(self) -> None:
        if (
            self.relationship is None
            or self.relationship.claim_id != self.claim_id
            or self.relationship.evidence_id != self.evidence_id
        ):
            raise ValueError("relationship identifiers must match evaluation identifiers")

    def _validate_relationship_scope(self) -> None:
        if (
            self.relationship is None
            or self.relationship.scope_comparison
            != self.scope_assessment.to_contract_comparison()
        ):
            raise ValueError("relationship scope must match the recorded evaluation scope")

    def _validate_failure_state(self, has_scores: bool) -> None:
        if self.relationship is not None or has_scores or self.score_kind is not None:
            raise ValueError("failed evaluation cannot carry a relationship or class scores")
        if not self.failure_detail:
            raise ValueError("failed evaluation requires explicit failure detail")
        if self.inference_status == EvaluationStatus.MODEL_UNAVAILABLE:
            if self.model_identity is not None or self.model_version is not None:
                raise ValueError("unavailable model cannot claim model identity")
        elif self.inference_status == EvaluationStatus.MODEL_LOAD_FAILED:
            if not self.model_identity or self.model_version is not None:
                raise ValueError("model-load failure requires configured model identity only")
        elif self.inference_status == EvaluationStatus.INFERENCE_FAILED:
            if self.model_identity is None and self.model_version is not None:
                raise ValueError("model version cannot be present without model identity")
        elif (
            self.model_identity is not None
            or self.model_version is not None
        ):
            raise ValueError("non-model failure cannot claim model identity")


class EvidenceRelationshipEvaluator:
    """Evaluate one atomic claim against one evidence passage; no aggregation."""

    IDENTITY = "factchecker-evidence-nli"
    VERSION = "task55-interface-v1"

    def __init__(self, backend: Optional[NLIBackend] = None) -> None:
        self.backend = backend or UnavailableNLIBackend()

    def evaluate(
        self,
        claim: ClaimRecord,
        evidence: EvidenceRecord,
        *,
        language: Optional[str],
        atomic_claim_id: Optional[str] = None,
        scope_assessment: Optional[EvidenceScopeAssessment] = None,
    ) -> EvidenceRelationshipEvaluation:
        result = self._evaluate(
            claim,
            evidence,
            language=language,
            atomic_claim_id=atomic_claim_id,
            scope_assessment=scope_assessment,
        )
        _evaluator_results.record_evaluator_execution(result)
        return result

    def _evaluate(
        self,
        claim: ClaimRecord,
        evidence: EvidenceRecord,
        *,
        language: Optional[str],
        atomic_claim_id: Optional[str] = None,
        scope_assessment: Optional[EvidenceScopeAssessment] = None,
    ) -> EvidenceRelationshipEvaluation:
        proposition, proposition_id, relationship_atomic_id, unsupported_reason = (
            _select_atomic_proposition(claim, atomic_claim_id)
        )
        reviewed_scope = (
            EvidenceScopeAssessment.model_validate(scope_assessment)
            if scope_assessment is not None
            else _unassessed_scope()
        )
        _validate_scope_annotations(claim, evidence, reviewed_scope)
        common = self._common_fields(
            claim,
            evidence,
            proposition,
            proposition_id,
            reviewed_scope,
        )
        if unsupported_reason is not None:
            return self._result(
                **common,
                inference_status=EvaluationStatus.UNSUPPORTED_CLAIM,
                failure_detail=unsupported_reason,
            )
        if evidence.extraction_status != ExtractionStatus.AVAILABLE or not evidence.extracted_passage:
            relation = EvidenceRelationship(
                relationship_id=str(uuid4()),
                claim_id=claim.claim_id,
                evidence_id=evidence.evidence_id,
                atomic_claim_id=relationship_atomic_id,
                label=EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
                rationale="No complete evidence passage is available for relation evaluation.",
                scope_comparison=reviewed_scope.to_contract_comparison(),
            )
            return self._result(
                **common,
                relationship=relation,
                inference_status=EvaluationStatus.MISSING_EVIDENCE_PASSAGE,
                failure_detail="Evidence passage is missing or extraction is incomplete.",
            )
        if not self.backend.available:
            return self._result(
                **common,
                inference_status=EvaluationStatus.MODEL_UNAVAILABLE,
                failure_detail="No NLI model is available for inference.",
            )
        normalized_language = _normalize_language(language)
        if normalized_language is None:
            return self._result(
                **common,
                inference_status=EvaluationStatus.LANGUAGE_UNSPECIFIED,
                failure_detail="A declared input language is required; language detection is not implemented.",
            )
        supported_languages = {
            _normalize_language(item) for item in self.backend.supported_languages
        }
        if normalized_language not in supported_languages:
            return self._result(
                **common,
                inference_status=EvaluationStatus.UNSUPPORTED_LANGUAGE,
                failure_detail=f"No configured NLI support for language '{normalized_language}'.",
            )

        premise = preprocess_evidence_passage(evidence.extracted_passage)
        hypothesis = preprocess_claim(proposition)
        try:
            inference = NLIInference.model_validate(
                self.backend.infer(premise, hypothesis)
            )
        except ModelLoadError as error:
            return self._result(
                **common,
                inference_status=EvaluationStatus.MODEL_LOAD_FAILED,
                model_identity=error.model_identity,
                failure_detail=f"{type(error).__name__}: {error}",
            )
        except Exception as error:
            return self._result(
                **common,
                inference_status=EvaluationStatus.INFERENCE_FAILED,
                model_identity=getattr(self.backend, "model_identity", None),
                model_version=getattr(self.backend, "model_version", None),
                failure_detail=f"{type(error).__name__}: {error}",
            )
        if inference.status == InferenceStatus.MODEL_UNAVAILABLE:
            return self._result(
                **common,
                inference_status=EvaluationStatus.MODEL_UNAVAILABLE,
                failure_detail=inference.detail,
            )
        if inference.status == InferenceStatus.MODEL_LOAD_FAILED:
            return self._result(
                **common,
                inference_status=EvaluationStatus.MODEL_LOAD_FAILED,
                model_identity=inference.model_identity,
                failure_detail=inference.detail,
            )
        if inference.status == InferenceStatus.INFERENCE_FAILED:
            return self._result(
                **common,
                inference_status=EvaluationStatus.INFERENCE_FAILED,
                model_identity=inference.model_identity,
                model_version=inference.model_version,
                failure_detail=inference.detail,
            )

        assert inference.scores is not None
        try:
            predicted_class = _highest_score(inference.scores)
        except ValueError as error:
            return self._result(
                **common,
                inference_status=EvaluationStatus.AMBIGUOUS_MODEL_OUTPUT,
                model_identity=inference.model_identity,
                model_version=inference.model_version,
                raw_nli_scores=inference.scores,
                score_kind=inference.score_kind,
                failure_detail=str(error),
            )
        directional = predicted_class in {
            NLIClass.ENTAILMENT,
            NLIClass.CONTRADICTION,
        }
        if reviewed_scope.verification_state == ScopeVerificationState.VERIFIED_MISMATCH:
            return self._scope_blocked_result(
                common,
                relationship_atomic_id,
                inference,
                reviewed_scope,
                EvaluationStatus.SCOPE_MISMATCH,
                "Independent scope verification found a material mismatch.",
            )
        if reviewed_scope.has_mismatch():
            return self._scope_blocked_result(
                common,
                relationship_atomic_id,
                inference,
                reviewed_scope,
                EvaluationStatus.SCOPE_UNASSESSED,
                "A caller-supplied mismatch annotation is unverified; the relationship is withheld.",
            )
        if directional and not reviewed_scope.is_verified_compatible():
            return self._scope_blocked_result(
                common,
                relationship_atomic_id,
                inference,
                reviewed_scope,
                EvaluationStatus.SCOPE_UNASSESSED,
                "Directional output is blocked because scope compatibility has not been independently verified.",
            )

        rationale = (
            f"NLI model {inference.model_identity} ({inference.model_version}) "
            f"assigned the highest raw {predicted_class.value} score to this "
            "premise/hypothesis pair. Scores are uncalibrated; structured scope "
            "annotations are caller-supplied and not independently verified."
        )
        relationship = EvidenceRelationship(
            relationship_id=str(uuid4()),
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            atomic_claim_id=relationship_atomic_id,
            label=_relationship_for(predicted_class),
            rationale=rationale,
            supporting_span=EvidenceSpan(
                start_char=0,
                end_char=len(evidence.extracted_passage),
                exact_text=evidence.extracted_passage,
            ),
            scope_comparison=reviewed_scope.to_contract_comparison(),
        )
        result = self._result(
            **common,
            relationship=relationship,
            inference_status=EvaluationStatus.COMPLETED,
            model_identity=inference.model_identity,
            model_version=inference.model_version,
            raw_nli_scores=inference.scores,
            score_kind=inference.score_kind,
        )
        return result

    def _scope_blocked_result(
        self,
        common: dict,
        atomic_claim_id: Optional[str],
        inference: NLIInference,
        scope_assessment: EvidenceScopeAssessment,
        status: EvaluationStatus,
        detail: str,
    ) -> EvidenceRelationshipEvaluation:
        relation = EvidenceRelationship(
            relationship_id=str(uuid4()),
            claim_id=common["claim_id"],
            evidence_id=common["evidence_id"],
            atomic_claim_id=atomic_claim_id,
            label=EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
            rationale=detail,
            scope_comparison=scope_assessment.to_contract_comparison(),
        )
        return self._result(
            **common,
            relationship=relation,
            inference_status=status,
            model_identity=inference.model_identity,
            model_version=inference.model_version,
            raw_nli_scores=inference.scores,
            score_kind=inference.score_kind,
            failure_detail=detail,
        )

    @staticmethod
    def _common_fields(
        claim: ClaimRecord,
        evidence: EvidenceRecord,
        proposition: str,
        proposition_id: str,
        scope_assessment: EvidenceScopeAssessment,
    ) -> dict:
        references = []
        if evidence.provenance.document_reference:
            references.append(evidence.provenance.document_reference)
        if evidence.source_url:
            references.append(str(evidence.source_url))
        if evidence.local_reference:
            references.append(evidence.local_reference)
        return {
            "evaluation_id": uuid4(),
            "claim_id": claim.claim_id,
            "evidence_id": evidence.evidence_id,
            "atomic_proposition_id": proposition_id or None,
            "claim_sha256": _sha256(
                proposition or claim.normalized_text or claim.original_text
            ),
            "evidence_record_sha256": _evidence_record_fingerprint(evidence),
            "evidence_extraction_status": evidence.extraction_status,
            "evidence_passage_sha256": (
                _sha256(evidence.extracted_passage)
                if evidence.extracted_passage is not None
                else None
            ),
            "evaluator_identity": EvidenceRelationshipEvaluator.IDENTITY,
            "evaluator_version": EvidenceRelationshipEvaluator.VERSION,
            "provenance_references": tuple(dict.fromkeys(references)),
            "scope_assessment": scope_assessment,
            "evaluated_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _result(**values: object) -> EvidenceRelationshipEvaluation:
        return EvidenceRelationshipEvaluation.model_validate(values)


def preprocess_claim(text: str) -> str:
    """Normalize whitespace and Unicode for inference without editing source data."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def preprocess_evidence_passage(text: str) -> str:
    """Normalize whitespace and Unicode for inference without editing source data."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def attach_relationship_to_rr(
    rr: EvidenceEvaluationRR,
    evaluation: EvidenceRelationshipEvaluation,
) -> EvidenceEvaluationRR:
    """Append an edge only to the exact validated evidence record evaluated."""
    authorized_input_rr = _is_authorized_reasoning_representation(rr)
    evaluator_authorized = _is_evaluator_result(evaluation)
    if _contains_directional_content(rr) and not authorized_input_rr:
        raise ValueError(
            "untrusted directional RR content cannot enter the evaluator adapter"
        )
    validated_rr = EvidenceEvaluationRR.model_validate(rr)
    validated_evaluation = EvidenceRelationshipEvaluation.model_validate(evaluation)
    if validated_evaluation.relationship is None:
        raise ValueError(
            f"cannot attach an evaluation with status "
            f"{validated_evaluation.inference_status.value}"
        )
    if not evaluator_authorized:
        raise ValueError(
            "caller-created evaluation results cannot be attached to an RR"
        )
    if (
        _is_directional_label(validated_evaluation.relationship.label)
        and not validated_evaluation.scope_assessment.is_verified_compatible()
    ):
        raise ValueError(
            "directional relationship requires independently verified compatible scope"
        )
    if validated_rr.retrieval_status != RetrievalStatus.COMPLETED_WITH_RESULTS:
        raise ValueError("RR integration requires completed retrieval with results")
    if validated_rr.assessment.status != AssessmentStatus.NOT_ASSESSED:
        raise ValueError("relationship integration requires a not-assessed RR")
    if validated_rr.claim.claim_id != validated_evaluation.claim_id:
        raise ValueError("evaluation claim_id does not match RR claim")
    proposition, proposition_id, relationship_atomic_id, unsupported_reason = (
        _select_atomic_proposition(
            validated_rr.claim,
            validated_evaluation.atomic_proposition_id
            if validated_rr.claim.atomicity == ClaimAtomicity.COMPOUND
            else None,
        )
    )
    if unsupported_reason is not None:
        raise ValueError(unsupported_reason)
    if proposition_id != validated_evaluation.atomic_proposition_id:
        raise ValueError("evaluation proposition does not match RR claim")
    if _sha256(proposition) != validated_evaluation.claim_sha256:
        raise ValueError("evaluation claim content does not match RR claim")
    evidence = next(
        (
            item
            for item in validated_rr.evidence
            if item.evidence_id == validated_evaluation.evidence_id
        ),
        None,
    )
    if evidence is None:
        raise ValueError("evaluation evidence_id is not present in RR")
    evidence = EvidenceRecord.model_validate(evidence)
    if evidence.extraction_status != validated_evaluation.evidence_extraction_status:
        raise ValueError("evaluation extraction status does not match RR evidence")
    if _evidence_record_fingerprint(evidence) != validated_evaluation.evidence_record_sha256:
        raise ValueError("evaluation evidence record or provenance does not match RR evidence")
    current_passage_hash = (
        _sha256(evidence.extracted_passage)
        if evidence.extracted_passage is not None
        else None
    )
    if current_passage_hash != validated_evaluation.evidence_passage_sha256:
        raise ValueError("evaluation passage content does not match RR evidence")
    if validated_evaluation.inference_status == EvaluationStatus.MISSING_EVIDENCE_PASSAGE:
        if (
            evidence.extraction_status == ExtractionStatus.AVAILABLE
            and evidence.extracted_passage is not None
        ):
            raise ValueError("missing-passage evaluation cannot attach to available evidence")
    elif (
        evidence.extraction_status != ExtractionStatus.AVAILABLE
        or evidence.extracted_passage is None
    ):
        raise ValueError("evaluated relationship requires the available passage")
    _validate_scope_annotations(
        validated_rr.claim,
        evidence,
        validated_evaluation.scope_assessment,
    )
    relation = validated_evaluation.relationship
    if relation.atomic_claim_id != relationship_atomic_id:
        raise ValueError("evaluation atomic claim reference does not match RR claim")
    payload = validated_rr.model_dump(mode="python", round_trip=True)
    payload["relationships"] = (*payload["relationships"], relation)
    updated_rr = EvidenceEvaluationRR.model_validate(payload)
    if (
        _contains_directional_content(updated_rr)
        and (authorized_input_rr or evaluator_authorized)
    ):
        if not _authorized_reasoning_representations.record_adapter_transition(
            updated_rr,
            rr,
            validated_evaluation,
        ):
            raise ValueError(
                "evaluator transition could not authorize the reasoning representation"
            )
    return updated_rr


def _select_atomic_proposition(
    claim: ClaimRecord,
    requested_atomic_claim_id: Optional[str],
) -> tuple[str, str, Optional[str], Optional[str]]:
    atoms = claim.atomic_claims or ()
    if claim.atomicity == ClaimAtomicity.AMBIGUOUS:
        return "", "", None, "Ambiguous claims are not evaluated."
    if claim.atomicity == ClaimAtomicity.NOT_ASSESSED:
        return "", "", None, "Claim atomicity has not been assessed."
    if claim.atomicity == ClaimAtomicity.COMPOUND:
        atom = next(
            (
                item
                for item in atoms
                if item.atomic_claim_id == requested_atomic_claim_id
            ),
            None,
        )
        if atom is None:
            return "", "", None, "Compound claims require a selected recorded atomic claim."
        return atom.text, atom.atomic_claim_id, atom.atomic_claim_id, None
    if len(atoms) > 1:
        return "", "", None, "An atomic claim cannot contain multiple atomic propositions."
    if requested_atomic_claim_id is not None and (
        not atoms or atoms[0].atomic_claim_id != requested_atomic_claim_id
    ):
        return "", "", None, "Requested atomic claim identifier does not match the claim."
    if atoms:
        atom = atoms[0]
        return atom.text, atom.atomic_claim_id, None, None
    return claim.normalized_text or claim.original_text, claim.claim_id, None, None


def _unassessed_scope() -> EvidenceScopeAssessment:
    return EvidenceScopeAssessment()


def _validate_scope_annotations(
    claim: ClaimRecord,
    evidence: EvidenceRecord,
    assessment: EvidenceScopeAssessment,
) -> None:
    if evidence.extracted_passage is None:
        if any(
            item.status in {ScopeMatchStatus.MATCH, ScopeMatchStatus.MISMATCH}
            for item in assessment.dimensions()
        ):
            raise ValueError("scope assertions require an available evidence passage")
        return

    claim_values = _claim_scope_values(claim)
    normalized_passage = preprocess_evidence_passage(evidence.extracted_passage)
    for dimension, item in zip(
        (
            "entity",
            "quantity",
            "unit",
            "temporal",
            "geographic",
            "population",
            "attribution",
            "polarity",
            "conditional",
        ),
        assessment.dimensions(),
    ):
        structured_values = claim_values[dimension]
        if item.status == ScopeMatchStatus.NOT_APPLICABLE:
            if structured_values:
                raise ValueError(
                    f"{dimension} scope cannot be NOT_APPLICABLE when structured claim values exist"
                )
            continue
        if item.status not in {ScopeMatchStatus.MATCH, ScopeMatchStatus.MISMATCH}:
            continue
        if len(structured_values) != 1:
            raise ValueError(
                f"{dimension} scope requires a single structured claim value for assessment"
            )
        if item.claim_value not in structured_values:
            raise ValueError(
                f"{dimension} scope claim_value is not present in the structured claim"
            )
        normalized_basis = preprocess_evidence_passage(item.evidence_basis or "")
        if not normalized_basis or normalized_basis not in normalized_passage:
            raise ValueError(
                f"{dimension} scope evidence_basis is not an exact passage excerpt"
            )


def _claim_scope_values(claim: ClaimRecord) -> dict[str, set[str]]:
    values = {
        "entity": set(),
        "quantity": set(),
        "unit": set(),
        "temporal": set(),
        "geographic": set(),
        "population": set(),
        "attribution": set(),
        "polarity": set(),
        "conditional": set(),
    }
    for entity in claim.entities or ():
        values["entity"].add(entity.normalized_identity or entity.mention)
    for quantity in claim.quantities or ():
        values["quantity"].add(_quantity_scope_value(quantity))
        if quantity.unit:
            values["unit"].add(quantity.unit)
    if claim.temporal_scope is not None:
        temporal_value = _temporal_scope_value(claim.temporal_scope)
        if temporal_value is not None:
            values["temporal"].add(temporal_value)
    if claim.geographic_scope is not None:
        geographic_value = _geographic_scope_value(claim.geographic_scope)
        if geographic_value:
            values["geographic"].add(geographic_value)
    if claim.population_scope:
        values["population"].add(claim.population_scope)
    if claim.attribution is not None:
        attribution_value = _attribution_scope_value(claim.attribution)
        if attribution_value:
            values["attribution"].add(attribution_value)
    for relation in claim.relations or ():
        if relation.polarity:
            values["polarity"].add(relation.polarity)
        if relation.condition:
            values["conditional"].add(relation.condition)
    return values


def _quantity_scope_value(quantity: ClaimQuantity) -> str:
    if quantity.comparator is None and quantity.denominator is None:
        return quantity.value
    comparator = quantity.comparator or "EXACT"
    denominator = f" per {quantity.denominator}" if quantity.denominator else ""
    return f"{comparator} {quantity.value}{denominator}"


def _temporal_scope_value(temporal: ClaimTemporalScope) -> Optional[str]:
    if not any((temporal.as_of, temporal.end, temporal.reference_text, temporal.start)):
        return None
    return json.dumps(
        {
            "as_of": temporal.as_of.isoformat() if temporal.as_of else None,
            "end": temporal.end.isoformat() if temporal.end else None,
            "reference_text": temporal.reference_text,
            "start": temporal.start.isoformat() if temporal.start else None,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _geographic_scope_value(geographic: ClaimGeographicScope) -> Optional[str]:
    place = geographic.place
    unit = geographic.geographic_unit
    if place and unit:
        return f"{place} ({unit})"
    return place or unit


def _attribution_scope_value(attribution: ClaimAttribution) -> Optional[str]:
    speaker = attribution.speaker
    action = attribution.reporting_action
    if speaker and action:
        return f"{speaker} {action}"
    return speaker or action


def _evidence_record_fingerprint(evidence: EvidenceRecord) -> str:
    validated = EvidenceRecord.model_validate(evidence)
    serialized = json.dumps(
        validated.model_dump(mode="json", round_trip=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _sha256(serialized)


def _highest_score(scores: Tuple[NLIScore, ...]) -> NLIClass:
    maximum = max(score.value for score in scores)
    winners = [score.label for score in scores if score.value == maximum]
    if len(winners) != 1:
        raise ValueError("Top NLI class scores are tied; no relationship is assigned.")
    return winners[0]


def _relationship_for(label: NLIClass) -> EvidenceRelationshipLabel:
    return {
        NLIClass.ENTAILMENT: EvidenceRelationshipLabel.SUPPORTS,
        NLIClass.CONTRADICTION: EvidenceRelationshipLabel.REFUTES,
        NLIClass.NEUTRAL: EvidenceRelationshipLabel.NEUTRAL,
    }[label]


def _normalize_language(language: Optional[str]) -> Optional[str]:
    if language is None or not language.strip():
        return None
    return language.strip().replace("_", "-").split("-", 1)[0].lower()


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
