"""Evidence-linked RR contract, separate from embedding/consistency RR."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional, Tuple

from pydantic import ConfigDict, Field, model_validator

from app.evidence.schemas import (
    AbstentionReason,
    AssessmentStatus,
    ClaimAssessment,
    ClaimAtomicity,
    ClaimModality,
    ClaimRecord,
    EvidenceRecord,
    EvidenceRelationship,
    EvidenceRelationshipLabel,
    ExtractionStatus,
    ProvenanceStatus,
    RetrievalStatus,
    ScopeMatchStatus,
    SourceAdequacy,
    Verdict,
)
from app.evidence.trust import _is_authorized_reasoning_representation
from app.rr.models import RRModel


_UNAVAILABLE_RETRIEVAL_STATUSES = {
    RetrievalStatus.PARTIAL,
    RetrievalStatus.FAILED,
    RetrievalStatus.UNAVAILABLE,
    RetrievalStatus.BLOCKED,
}


class EvidenceEvaluationRR(RRModel):
    """Validated claim/evidence graph and explicit assessed/processing state.

    Relationships in a structurally valid record remain untrusted descriptions
    unless this exact in-process instance was created by the evaluator adapter.
    Construction performs no retrieval, relation inference, or verdict
    computation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    evaluation_id: str = Field(min_length=1)
    claim: ClaimRecord
    evidence: Tuple[EvidenceRecord, ...] = ()
    retrieval_status: RetrievalStatus = RetrievalStatus.NOT_RECORDED
    relationships: Tuple[EvidenceRelationship, ...] = ()
    assessment: ClaimAssessment
    supported_modalities: Optional[Tuple[ClaimModality, ...]] = None

    def is_evaluator_authorized_for_directional_processing(self) -> bool:
        """Return whether this exact in-process RR came from the evaluator adapter."""
        return _is_authorized_reasoning_representation(self)

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "EvidenceEvaluationRR":
        data = self.model_dump(mode="python", round_trip=True)
        if deep:
            data = deepcopy(data)
        data.update(update or {})
        return self.__class__.model_validate(data)

    @classmethod
    def model_construct(
        cls, _fields_set: Optional[set[str]] = None, **values: Any
    ) -> "EvidenceEvaluationRR":
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

    @model_validator(mode="after")
    def validate_evidence_graph(self) -> "EvidenceEvaluationRR":
        if not self.evaluation_id.strip():
            raise ValueError("evaluation_id cannot be blank")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        if len(evidence_by_id) != len(self.evidence):
            raise ValueError("evidence_id values must be unique")
        if (
            self.retrieval_status == RetrievalStatus.COMPLETED_WITH_RESULTS
            and not self.evidence
        ):
            raise ValueError(
                "COMPLETED_WITH_RESULTS requires at least one evidence record"
            )
        if (
            self.retrieval_status
            in {RetrievalStatus.COMPLETED_EMPTY, RetrievalStatus.NOT_STARTED}
            and self.evidence
        ):
            raise ValueError(
                "COMPLETED_EMPTY and NOT_STARTED cannot contain evidence records"
            )
        if self.assessment.claim_id != self.claim.claim_id:
            raise ValueError("assessment claim_id must match claim.claim_id")

        relationship_ids = [item.relationship_id for item in self.relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("relationship_id values must be unique")

        atomic_ids = {
            item.atomic_claim_id for item in (self.claim.atomic_claims or ())
        }
        for relation in self.relationships:
            if relation.claim_id != self.claim.claim_id:
                raise ValueError("relationship claim_id does not match claim")
            if relation.evidence_id not in evidence_by_id:
                raise ValueError(
                    f"relationship references unknown evidence_id: {relation.evidence_id}"
                )
            if (
                relation.related_evidence_id is not None
                and relation.related_evidence_id not in evidence_by_id
            ):
                raise ValueError(
                    "CONTRADICTS references unknown related_evidence_id: "
                    f"{relation.related_evidence_id}"
                )
            if (
                relation.atomic_claim_id is not None
                and relation.atomic_claim_id not in atomic_ids
            ):
                raise ValueError(
                    "relationship references unknown atomic_claim_id: "
                    f"{relation.atomic_claim_id}"
                )
            if (
                self.claim.atomicity == ClaimAtomicity.COMPOUND
                and relation.label
                in {
                    EvidenceRelationshipLabel.SUPPORTS,
                    EvidenceRelationshipLabel.REFUTES,
                    EvidenceRelationshipLabel.PARTIALLY_SUPPORTS,
                    EvidenceRelationshipLabel.PARTIALLY_REFUTES,
                }
                and relation.atomic_claim_id is None
            ):
                raise ValueError(
                    "compound-claim directional relationships require atomic_claim_id"
                )
            evidence = evidence_by_id[relation.evidence_id]
            if (
                relation.label
                in {
                    EvidenceRelationshipLabel.SUPPORTS,
                    EvidenceRelationshipLabel.REFUTES,
                    EvidenceRelationshipLabel.PARTIALLY_SUPPORTS,
                    EvidenceRelationshipLabel.PARTIALLY_REFUTES,
                }
                and evidence.extraction_status == ExtractionStatus.AVAILABLE
                and relation.supporting_span is None
            ):
                raise ValueError(
                    "directional relationship to an available passage requires supporting_span"
                )
            if relation.supporting_span is not None:
                if evidence.extracted_passage is None:
                    raise ValueError(
                        "supporting_span requires an available extracted_passage"
                    )
                if relation.supporting_span.end_char > len(evidence.extracted_passage):
                    raise ValueError(
                        "supporting_span exceeds extracted_passage length"
                    )
                if relation.supporting_span.exact_text is not None:
                    observed = evidence.extracted_passage[
                        relation.supporting_span.start_char:
                        relation.supporting_span.end_char
                    ]
                    if observed != relation.supporting_span.exact_text:
                        raise ValueError(
                            "supporting_span exact_text does not match extracted_passage"
                        )
        self._validate_processing_state(evidence_by_id)
        if self.assessment.status == AssessmentStatus.ASSESSED:
            self._validate_abstention_reasons(evidence_by_id)
            self._validate_verdict(evidence_by_id)
        return self

    def _validate_processing_state(
        self, evidence_by_id: dict[str, EvidenceRecord]
    ) -> None:
        assessment = self.assessment
        if assessment.status == AssessmentStatus.NOT_ASSESSED:
            if assessment.abstention_reasons:
                raise ValueError(
                    "NOT_ASSESSED cannot carry active abstention reasons"
                )
        elif assessment.status == AssessmentStatus.EVIDENCE_UNAVAILABLE:
            if self.retrieval_status not in _UNAVAILABLE_RETRIEVAL_STATUSES:
                raise ValueError(
                    "EVIDENCE_UNAVAILABLE requires partial, failed, unavailable, "
                    "or blocked retrieval"
                )
            if any(
                reason
                not in {
                    AbstentionReason.UNSUPPORTED_MODALITY,
                }
                for reason in assessment.abstention_reasons
            ):
                raise ValueError(
                    "EVIDENCE_UNAVAILABLE cannot carry an assessed-evidence "
                    "abstention reason"
                )
            if AbstentionReason.UNSUPPORTED_MODALITY in assessment.abstention_reasons:
                self._validate_unsupported_modality_reason()
        elif assessment.status == AssessmentStatus.EVALUATION_FAILED:
            if assessment.abstention_reasons != (
                AbstentionReason.EVALUATION_FAILURE,
            ):
                raise ValueError(
                    "EVALUATION_FAILED requires only the EVALUATION_FAILURE reason"
                )
        elif assessment.status == AssessmentStatus.ASSESSED and (
            self.retrieval_status
            not in {
                RetrievalStatus.COMPLETED_WITH_RESULTS,
                RetrievalStatus.COMPLETED_EMPTY,
            }
        ):
            raise ValueError(
                "assessed verdicts require completed results or completed-empty retrieval"
            )

        if (
            self.retrieval_status == RetrievalStatus.COMPLETED_EMPTY
            and evidence_by_id
        ):
            raise ValueError("COMPLETED_EMPTY cannot contain evidence records")

    def _validate_abstention_reasons(
        self, evidence_by_id: dict[str, EvidenceRecord]
    ) -> None:
        assessment = self.assessment
        reasons = set(assessment.abstention_reasons)
        verdict = assessment.verdict
        if verdict in {Verdict.SUPPORTED, Verdict.REFUTED} and reasons:
            raise ValueError(
                "directional verdicts cannot carry active abstention reasons"
            )
        if (
            AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE in reasons
            and verdict != Verdict.CONFLICTING_EVIDENCE
        ):
            raise ValueError(
                "CONFLICTING_CREDIBLE_EVIDENCE requires CONFLICTING_EVIDENCE"
            )
        if (
            AbstentionReason.EVALUATION_FAILURE in reasons
            or verdict == Verdict.CONFLICTING_EVIDENCE
            and reasons != {AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE}
        ):
            raise ValueError(
                "assessed verdict has an incompatible abstention reason"
            )
        if AbstentionReason.NO_EVIDENCE_RETRIEVED in reasons and (
            verdict != Verdict.INSUFFICIENT_EVIDENCE
            or self.retrieval_status != RetrievalStatus.COMPLETED_EMPTY
            or evidence_by_id
        ):
            raise ValueError(
                "NO_EVIDENCE_RETRIEVED requires assessed insufficient evidence "
                "after empty completed retrieval"
            )
        if AbstentionReason.AMBIGUOUS_CLAIM in reasons and (
            verdict != Verdict.INSUFFICIENT_EVIDENCE
            or self.claim.atomicity != ClaimAtomicity.AMBIGUOUS
        ):
            raise ValueError(
                "AMBIGUOUS_CLAIM requires an ambiguous claim and "
                "INSUFFICIENT_EVIDENCE"
            )
        if AbstentionReason.PROVENANCE_UNVERIFIABLE in reasons and not any(
            evidence.provenance.status
            in {
                ProvenanceStatus.INCOMPLETE,
                ProvenanceStatus.UNVERIFIABLE,
                ProvenanceStatus.NOT_RECORDED,
            }
            for evidence in evidence_by_id.values()
        ):
            raise ValueError(
                "PROVENANCE_UNVERIFIABLE requires incomplete or unverified "
                "evidence provenance"
            )
        if AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY in reasons and not any(
            evidence.source_reliability_assessment.adequacy
            in {
                SourceAdequacy.INADEQUATE,
                SourceAdequacy.UNKNOWN,
                SourceAdequacy.NOT_ASSESSED,
            }
            or evidence.extraction_status != ExtractionStatus.AVAILABLE
            for evidence in evidence_by_id.values()
        ):
            raise ValueError(
                "INSUFFICIENT_EVIDENCE_QUALITY requires inadequate, unknown, "
                "or unavailable evidence"
            )
        if AbstentionReason.MISSING_CONTEXT in reasons and not (
            any(
                item.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
                for item in self.relationships
            )
            or self.claim.context is None
            or self.claim.attribution is None
        ):
            raise ValueError(
                "MISSING_CONTEXT requires a context-limited relation or missing "
                "claim context/attribution"
            )
        if AbstentionReason.UNSUPPORTED_MODALITY in reasons:
            self._validate_unsupported_modality_reason()

    def _validate_unsupported_modality_reason(self) -> None:
        if (
            not self.claim.modality
            or not self.supported_modalities
            or not set(self.claim.modality).difference(self.supported_modalities)
        ):
            raise ValueError(
                "UNSUPPORTED_MODALITY requires a claim modality outside the "
                "explicit supported_modalities set"
            )

    def _validate_verdict(
        self,
        evidence_by_id: dict[str, EvidenceRecord],
    ) -> None:
        relations = self.relationships
        support = [
            item for item in relations
            if item.label == EvidenceRelationshipLabel.SUPPORTS
        ]
        refute = [
            item for item in relations
            if item.label == EvidenceRelationshipLabel.REFUTES
        ]
        verdict = self.assessment.verdict

        if verdict in {Verdict.SUPPORTED, Verdict.REFUTED, Verdict.CONFLICTING_EVIDENCE}:
            if self.retrieval_status != RetrievalStatus.COMPLETED_WITH_RESULTS:
                raise ValueError(
                    f"{verdict.value} requires COMPLETED_WITH_RESULTS retrieval"
                )
        if verdict == Verdict.SUPPORTED:
            if not support or refute:
                raise ValueError(
                    "SUPPORTED requires supporting relations and no refuting relations"
                )
            self._require_decisive_evidence(support, evidence_by_id)
            self._require_claim_coverage(support)
        elif verdict == Verdict.REFUTED:
            if not refute or support:
                raise ValueError(
                    "REFUTED requires refuting relations and no supporting relations"
                )
            self._require_decisive_evidence(refute, evidence_by_id)
            self._require_claim_coverage(refute)
        elif verdict == Verdict.CONFLICTING_EVIDENCE:
            self._validate_conflicting_verdict(
                support,
                refute,
                relations,
                evidence_by_id,
            )
        elif verdict == Verdict.INSUFFICIENT_EVIDENCE:
            if not self.assessment.abstention_reasons:
                raise ValueError(
                    "INSUFFICIENT_EVIDENCE requires an explicit abstention reason"
                )
            if (
                not self.evidence
                and (
                    self.retrieval_status != RetrievalStatus.COMPLETED_EMPTY
                    or AbstentionReason.NO_EVIDENCE_RETRIEVED
                    not in self.assessment.abstention_reasons
                )
            ):
                raise ValueError(
                    "empty-evidence INSUFFICIENT_EVIDENCE requires "
                    "NO_EVIDENCE_RETRIEVED and COMPLETED_EMPTY"
                )
            if self.retrieval_status in _UNAVAILABLE_RETRIEVAL_STATUSES:
                raise ValueError(
                    "failed, partial, unavailable, or blocked retrieval cannot "
                    "be represented as INSUFFICIENT_EVIDENCE"
                )
            if any(
                item.label in {
                    EvidenceRelationshipLabel.SUPPORTS,
                    EvidenceRelationshipLabel.REFUTES,
                }
                and item.evidence_id in evidence_by_id
                and self._is_decisive(evidence_by_id[item.evidence_id])
                for item in relations
            ):
                raise ValueError(
                    "INSUFFICIENT_EVIDENCE conflicts with decisive "
                    "SUPPORTS/REFUTES annotations"
                )

    def _validate_conflicting_verdict(
        self,
        support: Tuple[EvidenceRelationship, ...] | list[EvidenceRelationship],
        refute: Tuple[EvidenceRelationship, ...] | list[EvidenceRelationship],
        relations: Tuple[EvidenceRelationship, ...],
        evidence_by_id: dict[str, EvidenceRecord],
    ) -> None:
        if self.claim.atomicity == ClaimAtomicity.AMBIGUOUS:
            raise ValueError("ambiguous claims cannot receive a conflict verdict")
        if not support or not refute:
            raise ValueError(
                "CONFLICTING_EVIDENCE requires both supporting and refuting relations"
            )
        self._require_decisive_evidence(tuple(support) + tuple(refute), evidence_by_id)
        for relation in tuple(support) + tuple(refute):
            self._require_comparable_scope(relation)

        support_pairs = [
            (positive, negative)
            for positive in support
            for negative in refute
            if positive.evidence_id != negative.evidence_id
            and positive.atomic_claim_id == negative.atomic_claim_id
        ]
        if not support_pairs:
            raise ValueError(
                "conflicting evidence requires support and refutation for the "
                "same proposition"
            )
        if self.claim.atomicity == ClaimAtomicity.COMPOUND:
            expected_atoms = {
                atom.atomic_claim_id for atom in (self.claim.atomic_claims or ())
            }
            if not expected_atoms or {
                positive.atomic_claim_id
                for positive in support
                if any(
                    negative.atomic_claim_id == positive.atomic_claim_id
                    for negative in refute
                )
            } != expected_atoms:
                raise ValueError(
                    "compound-claim conflict requires comparable supporting and "
                    "refuting evidence for every atomic claim"
                )
        elif self.claim.atomicity == ClaimAtomicity.ATOMIC:
            if any(
                item.atomic_claim_id is not None for item in tuple(support) + tuple(refute)
            ):
                raise ValueError(
                    "atomic-claim conflict must use the claim itself, not unrelated atoms"
                )
        elif any(
            item.atomic_claim_id is None for item in tuple(support) + tuple(refute)
        ):
            raise ValueError(
                "conflict requires an assessed atomic claim or explicit comparable proposition"
            )

        contradiction_edges = [
            item for item in relations
            if item.label == EvidenceRelationshipLabel.CONTRADICTS
        ]
        expected_edge_keys = {
            (
                frozenset((positive.evidence_id, negative.evidence_id)),
                positive.atomic_claim_id,
            )
            for positive, negative in support_pairs
        }
        actual_edge_keys = [
            (
                frozenset((edge.evidence_id, edge.related_evidence_id)),
                edge.atomic_claim_id,
            )
            for edge in contradiction_edges
        ]
        if (
            len(actual_edge_keys) != len(set(actual_edge_keys))
            or set(actual_edge_keys) != expected_edge_keys
        ):
            raise ValueError(
                "CONTRADICTS edges must exactly link every opposing evidence "
                "pair for the same proposition"
            )

        matched_atoms = set()
        for positive, negative in support_pairs:
            for edge in contradiction_edges:
                if (
                    frozenset((edge.evidence_id, edge.related_evidence_id))
                    == frozenset((positive.evidence_id, negative.evidence_id))
                    and edge.atomic_claim_id == positive.atomic_claim_id
                ):
                    self._require_comparable_scope(edge)
                    matched_atoms.add(positive.atomic_claim_id)
        if self.claim.atomicity == ClaimAtomicity.COMPOUND:
            expected_atoms = {
                atom.atomic_claim_id for atom in (self.claim.atomic_claims or ())
            }
            if matched_atoms != expected_atoms:
                raise ValueError(
                    "CONFLICTING_EVIDENCE requires a comparable CONTRADICTS link "
                    "for every atomic proposition"
                )
        elif not matched_atoms:
            raise ValueError(
                "CONFLICTING_EVIDENCE requires a CONTRADICTS edge linking opposing "
                "annotations for the same proposition"
            )

    def _require_comparable_scope(self, relation: EvidenceRelationship) -> None:
        comparison = relation.scope_comparison
        if comparison is None or not comparison.is_comparable():
            raise ValueError(
                "conflicting evidence requires explicit matching entity, temporal, "
                "geographic, and population scope assessments"
            )
        required_scope_matches = (
            (self.claim.entities, comparison.entity, "entity"),
            (self.claim.temporal_scope, comparison.temporal, "temporal"),
            (self.claim.geographic_scope, comparison.geographic, "geographic"),
            (self.claim.population_scope, comparison.population, "population"),
        )
        for claim_scope, match_status, scope_name in required_scope_matches:
            if claim_scope is not None and match_status != ScopeMatchStatus.MATCH:
                raise ValueError(
                    f"conflicting evidence requires MATCH for declared {scope_name} scope"
                )

    def _require_claim_coverage(
        self, relations: Tuple[EvidenceRelationship, ...] | list[EvidenceRelationship]
    ) -> None:
        if self.claim.atomicity == ClaimAtomicity.AMBIGUOUS:
            raise ValueError("ambiguous claims cannot receive a directional verdict")
        if self.claim.atomicity == ClaimAtomicity.NOT_ASSESSED:
            raise ValueError(
                "directional verdict requires assessed claim atomicity"
            )
        if self.claim.atomicity == ClaimAtomicity.COMPOUND:
            atomic_ids = {
                item.atomic_claim_id for item in (self.claim.atomic_claims or ())
            }
            covered = {item.atomic_claim_id for item in relations}
            if not atomic_ids or not atomic_ids.issubset(covered):
                raise ValueError(
                    "directional verdict requires relation coverage for every "
                    "atomic claim"
                )

    def _require_decisive_evidence(
        self,
        relations: Tuple[EvidenceRelationship, ...] | list[EvidenceRelationship],
        evidence_by_id: dict[str, EvidenceRecord],
    ) -> None:
        for relation in relations:
            self._require_decisive_record(evidence_by_id[relation.evidence_id])

    @staticmethod
    def _is_decisive(evidence: EvidenceRecord) -> bool:
        return (
            evidence.extraction_status == ExtractionStatus.AVAILABLE
            and evidence.provenance.status == ProvenanceStatus.VERIFIED
            and evidence.source_reliability_assessment.adequacy
            == SourceAdequacy.ADEQUATE
            and evidence.retrieval_method is not None
            and evidence.retrieval_method.status
            == RetrievalStatus.COMPLETED_WITH_RESULTS
            and evidence.acquisition_timestamp is not None
        )

    def _require_decisive_record(self, evidence: EvidenceRecord) -> None:
        if not self._is_decisive(evidence):
            raise ValueError(
                "directional verdict requires available passage, verified "
                "provenance, adequate source assessment, and completed retrieval"
            )
