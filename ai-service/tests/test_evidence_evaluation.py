from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import pytest
from pydantic import BaseModel, ValidationError

from app.cmrea.evidence import CMREAEvidenceContext, build_cmrea_evidence_context
from app.evidence.schemas import (
    AbstentionReason,
    AssessmentStatus,
    AtomicClaim,
    ClaimAssessment,
    ClaimAtomicity,
    ClaimAttribution,
    ClaimEntity,
    ClaimGeographicScope,
    ClaimModality,
    ClaimQuantity,
    ClaimRecord,
    ClaimRelation,
    ClaimTemporalScope,
    EvidenceModality,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceScopeComparison,
    EvidenceRelationship,
    EvidenceRelationshipLabel,
    EvidenceSpan,
    ExtractionStatus,
    ProvenanceStatus,
    RetrievalMethod,
    RetrievalStatus,
    SourceAdequacy,
    SourceReliabilityAssessment,
    ScopeMatchStatus,
    Verdict,
)
from app.rr.evidence import EvidenceEvaluationRR


FIXTURE_TIME = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def make_claim(
    text: str = "The fictional Alder council recorded 12 test markers in 2024.",
    **overrides,
) -> ClaimRecord:
    values = {
        "claim_id": "claim-1",
        "original_text": text,
        "normalized_text": None,
        "atomicity": ClaimAtomicity.ATOMIC,
        "atomic_claims": None,
        "entities": [
            ClaimEntity(mention="fictional Alder council", entity_type="organization")
        ],
        "relations": [
            ClaimRelation(
                subject="fictional Alder council",
                predicate="recorded",
                object="test markers",
            )
        ],
        "quantities": [
            ClaimQuantity(value="12", unit="markers", comparator="exactly")
        ],
        "temporal_scope": ClaimTemporalScope(
            reference_text="in 2024",
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc),
        ),
        "geographic_scope": ClaimGeographicScope(
            place="fictional Alder district", geographic_unit="district"
        ),
        "attribution": ClaimAttribution(
            speaker="fictional Alder council", reporting_action="recorded"
        ),
        "context": "Original, manually authored closed-world test fixture.",
        "modality": [ClaimModality.TEXT],
        "extraction_provenance": {
            "status": "RECORDED",
            "input_reference": "fixture://task54/claim-1",
            "method": "manual_fixture_authoring",
            "method_version": "1",
            "extracted_at": FIXTURE_TIME,
        },
    }
    values.update(overrides)
    return ClaimRecord(**values)


def make_evidence(
    evidence_id: str = "evidence-1",
    passage: str = "The fictional Alder council recorded 12 test markers in 2024.",
    *,
    provenance_status: ProvenanceStatus = ProvenanceStatus.VERIFIED,
    extraction_status: ExtractionStatus = ExtractionStatus.AVAILABLE,
    adequacy: SourceAdequacy = SourceAdequacy.ADEQUATE,
    reliability_rationale: str = "Manual closed-world fixture annotation only.",
    local_reference: str | None = None,
) -> EvidenceRecord:
    record = {
        "evidence_id": evidence_id,
        "source_id": f"fixture-source-{evidence_id}",
        "source_title": "Original local test fixture",
        "local_reference": local_reference or f"fixture://task54/{evidence_id}",
        "publisher": None,
        "author": None,
        "publication_date": date(2024, 12, 1),
        "acquisition_timestamp": FIXTURE_TIME,
        "extracted_passage": (
            passage if extraction_status == ExtractionStatus.AVAILABLE else None
        ),
        "source_modality": EvidenceModality.TEXT,
        "retrieval_method": {
            "method": "manual_fixture",
            "status": RetrievalStatus.COMPLETED_WITH_RESULTS,
        },
        "provenance": {
            "status": provenance_status,
            "document_reference": f"fixture-document-{evidence_id}",
            "document_version": "fixture-v1",
            "passage_locator": "fixture-paragraph-1",
        },
        "source_reliability_assessment": {
            "adequacy": adequacy,
            "source_kind": "TEST_FIXTURE",
            "directness": "DIRECT",
            "identity_review": "FIXTURE_ONLY",
            "temporal_fit": "FIXTURE_ONLY",
            "independence": "FIXTURE_ONLY",
            "methodology_review": "FIXTURE_ONLY",
            "correction_status": "NOT_APPLICABLE",
            "limitations": "Not a real-world source or factual assertion.",
            "rationale": reliability_rationale if adequacy in {
                SourceAdequacy.ADEQUATE,
                SourceAdequacy.INADEQUATE,
            } else None,
        },
        "extraction_status": extraction_status,
        "extraction_method": (
            "manual_fixture_authoring"
            if extraction_status == ExtractionStatus.AVAILABLE
            else None
        ),
    }
    if provenance_status != ProvenanceStatus.VERIFIED:
        record["local_reference"] = local_reference
        record["acquisition_timestamp"] = None
    return EvidenceRecord(**record)


def make_relationship(
    label: EvidenceRelationshipLabel,
    *,
    evidence_id: str = "evidence-1",
    relationship_id: str = "relationship-1",
    related_evidence_id: str | None = None,
    atomic_claim_id: str | None = None,
    passage: str | None = None,
    rationale: str = "Manual fixture annotation for contract testing.",
    scope_comparison: EvidenceScopeComparison | None = None,
) -> EvidenceRelationship:
    span = None
    if passage is not None and label in {
        EvidenceRelationshipLabel.SUPPORTS,
        EvidenceRelationshipLabel.REFUTES,
        EvidenceRelationshipLabel.PARTIALLY_SUPPORTS,
        EvidenceRelationshipLabel.PARTIALLY_REFUTES,
    }:
        span = EvidenceSpan(
            start_char=0,
            end_char=len(passage),
            exact_text=passage,
        )
    return EvidenceRelationship(
        relationship_id=relationship_id,
        claim_id="claim-1",
        evidence_id=evidence_id,
        label=label,
        rationale=rationale,
        atomic_claim_id=atomic_claim_id,
        related_evidence_id=related_evidence_id,
        supporting_span=span,
        scope_comparison=scope_comparison,
    )


def matching_scope_comparison() -> EvidenceScopeComparison:
    return EvidenceScopeComparison(
        entity=ScopeMatchStatus.MATCH,
        temporal=ScopeMatchStatus.MATCH,
        geographic=ScopeMatchStatus.MATCH,
        population=ScopeMatchStatus.NOT_APPLICABLE,
        rationale="Manually annotated scope match for this fictional fixture.",
    )


def make_assessment(
    verdict: Verdict | None,
    *,
    status: AssessmentStatus = AssessmentStatus.ASSESSED,
    reasons: list[AbstentionReason] | None = None,
    rationale: str | None = "Manual fixture expected outcome; not a model result.",
) -> ClaimAssessment:
    return ClaimAssessment(
        claim_id="claim-1",
        status=status,
        verdict=verdict,
        abstention_reasons=reasons or [],
        rationale=rationale,
    )


def make_rr(
    *,
    claim: ClaimRecord | None = None,
    evidence: list[EvidenceRecord] | None = None,
    relationships: list[EvidenceRelationship] | None = None,
    assessment: ClaimAssessment | None = None,
    retrieval_status: RetrievalStatus = RetrievalStatus.COMPLETED_WITH_RESULTS,
    supported_modalities=None,
) -> EvidenceEvaluationRR:
    records = evidence if evidence is not None else [make_evidence()]
    if assessment is None:
        assessment = make_assessment(Verdict.SUPPORTED)
    return EvidenceEvaluationRR(
        evaluation_id="fixture-evaluation-1",
        claim=claim or make_claim(),
        evidence=records,
        retrieval_status=retrieval_status,
        relationships=(
            relationships
            if relationships is not None
            else [
                make_relationship(
                    EvidenceRelationshipLabel.SUPPORTS,
                    passage=records[0].extracted_passage,
                )
            ]
        ),
        assessment=assessment,
        supported_modalities=supported_modalities,
    )


def make_nondirectional_rr() -> EvidenceEvaluationRR:
    evidence = make_evidence()
    return make_rr(
        evidence=[evidence],
        relationships=[
            make_relationship(
                EvidenceRelationshipLabel.NEUTRAL,
                evidence_id=evidence.evidence_id,
                rationale="Manual fixture relationship without directional content.",
            )
        ],
        assessment=make_assessment(
            None,
            status=AssessmentStatus.NOT_ASSESSED,
            rationale=None,
        ),
    )


def make_conflict_rr(
    *,
    claim: ClaimRecord | None = None,
    support_atomic_claim_id: str | None = None,
    refute_atomic_claim_id: str | None = None,
    contradiction_atomic_claim_id: str | None = None,
    support_scope: EvidenceScopeComparison | None = None,
    refute_scope: EvidenceScopeComparison | None = None,
    contradiction_scope: EvidenceScopeComparison | None = None,
    contradiction_evidence_id: str = "evidence-supports",
    contradiction_related_evidence_id: str = "evidence-refutes",
) -> EvidenceEvaluationRR:
    support_passage = (
        "The fictional Alder council recorded 12 test markers in 2024."
    )
    refute_passage = (
        "The fictional Alder council recorded 9 test markers in 2024."
    )
    return make_rr(
        evidence=[
            make_evidence("evidence-supports", support_passage),
            make_evidence("evidence-refutes", refute_passage),
            *(
                [make_evidence("evidence-unrelated", "Unrelated fixture passage.")]
                if contradiction_evidence_id == "evidence-unrelated"
                or contradiction_related_evidence_id == "evidence-unrelated"
                else []
            ),
        ],
        relationships=[
            make_relationship(
                EvidenceRelationshipLabel.SUPPORTS,
                evidence_id="evidence-supports",
                relationship_id="relationship-supports",
                passage=support_passage,
                atomic_claim_id=support_atomic_claim_id,
                scope_comparison=support_scope or matching_scope_comparison(),
            ),
            make_relationship(
                EvidenceRelationshipLabel.REFUTES,
                evidence_id="evidence-refutes",
                relationship_id="relationship-refutes",
                passage=refute_passage,
                atomic_claim_id=refute_atomic_claim_id,
                scope_comparison=refute_scope or matching_scope_comparison(),
            ),
            make_relationship(
                EvidenceRelationshipLabel.CONTRADICTS,
                evidence_id=contradiction_evidence_id,
                relationship_id="relationship-conflict",
                related_evidence_id=contradiction_related_evidence_id,
                atomic_claim_id=contradiction_atomic_claim_id,
                rationale="The fixture passages assert incompatible counts for the same scope.",
                scope_comparison=contradiction_scope or matching_scope_comparison(),
            ),
        ],
        assessment=make_assessment(
            Verdict.CONFLICTING_EVIDENCE,
            reasons=[AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE],
        ),
        claim=claim,
    )


def make_insufficient_rr(
    reason: AbstentionReason,
    *,
    claim: ClaimRecord | None = None,
    evidence: list[EvidenceRecord] | None = None,
    relationship: EvidenceRelationship | None = None,
    retrieval_status: RetrievalStatus = RetrievalStatus.COMPLETED_WITH_RESULTS,
) -> EvidenceEvaluationRR:
    if evidence is None and reason == AbstentionReason.NO_EVIDENCE_RETRIEVED:
        evidence = []
        retrieval_status = RetrievalStatus.COMPLETED_EMPTY
    elif evidence is None:
        evidence = [make_evidence()]
    relationships = [relationship] if relationship is not None else []
    return make_rr(
        claim=claim,
        evidence=evidence,
        relationships=relationships,
        assessment=make_assessment(
            Verdict.INSUFFICIENT_EVIDENCE,
            reasons=[reason],
            rationale="The manually annotated fixture deliberately withholds a decisive match.",
        ),
        retrieval_status=retrieval_status,
    )


def make_off_scope_fixture(
    name: str,
    *,
    claim: ClaimRecord,
    passage: str,
) -> EvidenceEvaluationRR:
    evidence = make_evidence(
        f"evidence-{name}",
        passage,
        adequacy=SourceAdequacy.INADEQUATE,
        reliability_rationale=f"Fixture is out of the claim's {name} scope.",
    )
    relationship = make_relationship(
        EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
        evidence_id=evidence.evidence_id,
        rationale=f"The fixture passage does not match the claim's {name} scope.",
    )
    return make_insufficient_rr(
        AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
        claim=claim,
        evidence=[evidence],
        relationship=relationship,
    )


@pytest.fixture
def original_offline_cases() -> list[tuple[str, EvidenceEvaluationRR, Verdict, AbstentionReason | None]]:
    support_passage = "The fictional Alder council recorded 12 test markers in 2024."
    refute_passage = "The fictional Alder council recorded 9 test markers in 2024."
    cases: list[
        tuple[str, EvidenceEvaluationRR, Verdict, AbstentionReason | None]
    ] = [
        (
            "direct support",
            make_rr(
                evidence=[make_evidence("support", support_passage)],
                relationships=[
                    make_relationship(
                        EvidenceRelationshipLabel.SUPPORTS,
                        evidence_id="support",
                        passage=support_passage,
                    )
                ],
            ),
            Verdict.SUPPORTED,
            None,
        ),
        (
            "direct refutation",
            make_rr(
                evidence=[make_evidence("refute", refute_passage)],
                relationships=[
                    make_relationship(
                        EvidenceRelationshipLabel.REFUTES,
                        evidence_id="refute",
                        passage=refute_passage,
                    )
                ],
                assessment=make_assessment(Verdict.REFUTED),
            ),
            Verdict.REFUTED,
            None,
        ),
        (
            "no evidence retrieved",
            make_insufficient_rr(AbstentionReason.NO_EVIDENCE_RETRIEVED),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.NO_EVIDENCE_RETRIEVED,
        ),
        (
            "contradictory evidence",
            make_conflict_rr(),
            Verdict.CONFLICTING_EVIDENCE,
            AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE,
        ),
        (
            "temporal mismatch",
            make_off_scope_fixture(
                "temporal",
                claim=make_claim(
                    temporal_scope=ClaimTemporalScope(
                        reference_text="in 2024",
                        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                        end=datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc),
                    )
                ),
                passage="The fictional Alder council recorded 12 test markers in 2022.",
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
        ),
        (
            "numerical and denominator mismatch",
            make_off_scope_fixture(
                "numerical",
                claim=make_claim(
                    quantities=[
                        ClaimQuantity(
                            value="12", unit="markers per 100 residents",
                            denominator="100 residents",
                        )
                    ]
                ),
                passage="The fictional Alder council recorded 12 markers per 1,000 residents.",
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
        ),
        (
            "geographic mismatch",
            make_off_scope_fixture(
                "geographic",
                claim=make_claim(
                    geographic_scope=ClaimGeographicScope(
                        place="fictional Alder district", geographic_unit="district"
                    )
                ),
                passage="The fictional Birch district recorded 12 test markers in 2024.",
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
        ),
        (
            "population mismatch",
            make_off_scope_fixture(
                "population",
                claim=make_claim(context="Claim concerns all registered residents."),
                passage="The fictional survey counted 12 markers among club members only.",
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
        ),
        (
            "missing attribution",
            make_insufficient_rr(
                AbstentionReason.MISSING_CONTEXT,
                claim=make_claim(
                    text="Someone reported that the fictional Alder hall closed in May.",
                    attribution=None,
                ),
                relationship=make_relationship(
                    EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
                    rationale="The fixture omits who made the report.",
                ),
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.MISSING_CONTEXT,
        ),
        (
            "ambiguous compound claim",
            make_insufficient_rr(
                AbstentionReason.AMBIGUOUS_CLAIM,
                claim=make_claim(
                    text="The fictional report says the count increased and it stayed open.",
                    atomicity=ClaimAtomicity.AMBIGUOUS,
                    atomic_claims=[
                        AtomicClaim(
                            atomic_claim_id="atom-1",
                            text="The fictional report says the count increased.",
                        ),
                        AtomicClaim(
                            atomic_claim_id="atom-2",
                            text="The fictional report says it stayed open.",
                        ),
                    ],
                    context=None,
                ),
                evidence=[make_evidence("ambiguous-claim-context")],
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.AMBIGUOUS_CLAIM,
        ),
        (
            "unverifiable source provenance",
            make_insufficient_rr(
                AbstentionReason.PROVENANCE_UNVERIFIABLE,
                evidence=[
                    make_evidence(
                        "unverifiable",
                        "The fictional Alder council recorded 12 test markers in 2024.",
                        provenance_status=ProvenanceStatus.UNVERIFIABLE,
                        adequacy=SourceAdequacy.UNKNOWN,
                        local_reference=None,
                    )
                ],
                relationship=make_relationship(
                    EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
                    evidence_id="unverifiable",
                    rationale="The fixture passage has no verifiable source reference.",
                ),
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.PROVENANCE_UNVERIFIABLE,
        ),
        (
            "missing evidence passage",
            make_insufficient_rr(
                AbstentionReason.MISSING_CONTEXT,
                evidence=[
                    make_evidence(
                        "missing-passage",
                        extraction_status=ExtractionStatus.MISSING_PASSAGE,
                    )
                ],
                relationship=make_relationship(
                    EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT,
                    evidence_id="missing-passage",
                    rationale="The fixture source is recorded but no passage was extracted.",
                ),
            ),
            Verdict.INSUFFICIENT_EVIDENCE,
            AbstentionReason.MISSING_CONTEXT,
        ),
    ]
    return cases


def test_original_offline_fixture_cases_validate_expected_schema_outcomes(
    original_offline_cases,
) -> None:
    assert len(original_offline_cases) == 12
    for _, record, expected_verdict, expected_reason in original_offline_cases:
        restored = EvidenceEvaluationRR.model_validate(
            record.model_dump(mode="json")
        )
        assert restored.assessment.status == AssessmentStatus.ASSESSED
        assert restored.assessment.verdict == expected_verdict
        assert restored.assessment.abstention_reasons == (
            (expected_reason,) if expected_reason is not None else ()
        )


def test_valid_claim_preserves_missing_fields_explicitly() -> None:
    claim = make_claim(
        entities=None,
        relations=None,
        quantities=None,
        temporal_scope=None,
        geographic_scope=None,
        attribution=None,
        context=None,
        modality=None,
        normalized_text=None,
        atomic_claims=None,
    )

    assert claim.original_text.startswith("The fictional")
    assert claim.entities is None
    assert claim.temporal_scope is None
    assert claim.extraction_provenance.status.value == "RECORDED"


@pytest.mark.parametrize(
    ("verdict", "label"),
    [
        (Verdict.SUPPORTED, EvidenceRelationshipLabel.SUPPORTS),
        (Verdict.REFUTED, EvidenceRelationshipLabel.REFUTES),
    ],
)
@pytest.mark.parametrize(
    "retrieval_status",
    [
        RetrievalStatus.FAILED,
        RetrievalStatus.PARTIAL,
        RetrievalStatus.NOT_STARTED,
        RetrievalStatus.UNAVAILABLE,
        RetrievalStatus.COMPLETED_EMPTY,
    ],
)
def test_directional_verdict_requires_completed_results(
    verdict, label, retrieval_status
) -> None:
    passage = "A manually authored decisive fixture passage."
    evidence = make_evidence("retrieval-evidence", passage)
    with pytest.raises(ValidationError, match="retrieval|evidence records"):
        make_rr(
            evidence=[evidence],
            relationships=[
                make_relationship(
                    label,
                    evidence_id=evidence.evidence_id,
                    passage=passage,
                )
            ],
            assessment=make_assessment(verdict),
            retrieval_status=retrieval_status,
        )


def test_failed_retrieval_cannot_become_insufficient_evidence() -> None:
    with pytest.raises(ValidationError, match="completed results"):
        make_insufficient_rr(
            AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY,
            retrieval_status=RetrievalStatus.FAILED,
        )


def test_completed_empty_retrieval_is_an_assessed_insufficient_outcome() -> None:
    result = make_insufficient_rr(AbstentionReason.NO_EVIDENCE_RETRIEVED)

    assert result.retrieval_status == RetrievalStatus.COMPLETED_EMPTY
    assert result.assessment.status == AssessmentStatus.ASSESSED
    assert result.assessment.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.evidence == ()
    assert result.assessment.abstention_reasons == (
        AbstentionReason.NO_EVIDENCE_RETRIEVED,
    )


def test_unavailable_retrieval_cannot_claim_completed_empty() -> None:
    with pytest.raises(ValidationError, match="assessed-evidence abstention"):
        make_rr(
            evidence=[],
            relationships=[],
            retrieval_status=RetrievalStatus.UNAVAILABLE,
            assessment=make_assessment(
                None,
                status=AssessmentStatus.EVIDENCE_UNAVAILABLE,
                reasons=[AbstentionReason.NO_EVIDENCE_RETRIEVED],
                rationale=None,
            ),
        )


@pytest.mark.parametrize(
    "scope_name",
    ["entity", "temporal", "geographic", "population"],
)
def test_conflict_requires_matching_declared_scope(scope_name) -> None:
    claim_overrides = {
        "entity": {"entities": (ClaimEntity(mention="Fictional Alder"),)},
        "temporal": {
            "temporal_scope": ClaimTemporalScope(
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            )
        },
        "geographic": {
            "geographic_scope": ClaimGeographicScope(place="Fictional Alder")
        },
        "population": {"population_scope": "registered residents"},
    }
    bad_scope = EvidenceScopeComparison(
        entity=ScopeMatchStatus.MISMATCH if scope_name == "entity" else ScopeMatchStatus.MATCH,
        temporal=ScopeMatchStatus.MISMATCH if scope_name == "temporal" else ScopeMatchStatus.MATCH,
        geographic=ScopeMatchStatus.MISMATCH if scope_name == "geographic" else ScopeMatchStatus.MATCH,
        population=ScopeMatchStatus.MISMATCH if scope_name == "population" else ScopeMatchStatus.NOT_APPLICABLE,
        rationale=f"Fixture marks {scope_name} as mismatched.",
    )

    with pytest.raises(ValidationError, match="scope assessments|MATCH"):
        make_conflict_rr(
            claim=make_claim(**claim_overrides[scope_name]),
            support_scope=bad_scope,
        )


def test_conflict_requires_same_atomic_proposition() -> None:
    claim = make_claim(
        atomicity=ClaimAtomicity.COMPOUND,
        atomic_claims=(
            AtomicClaim(atomic_claim_id="atom-a", text="First proposition."),
            AtomicClaim(atomic_claim_id="atom-b", text="Second proposition."),
        ),
    )

    with pytest.raises(ValidationError, match="same proposition"):
        make_conflict_rr(
            claim=claim,
            support_atomic_claim_id="atom-a",
            refute_atomic_claim_id="atom-b",
            contradiction_atomic_claim_id="atom-a",
        )


def test_ambiguous_claim_cannot_receive_conflict_verdict() -> None:
    with pytest.raises(ValidationError, match="ambiguous"):
        make_conflict_rr(claim=make_claim(atomicity=ClaimAtomicity.AMBIGUOUS))


def test_contradiction_edge_must_link_the_opposing_evidence_pair() -> None:
    with pytest.raises(ValidationError, match="same proposition"):
        make_conflict_rr(contradiction_evidence_id="evidence-unrelated")


def test_conflict_rejects_unrelated_extra_contradiction_edge() -> None:
    conflict = make_conflict_rr()
    extra_a = make_evidence("unrelated-a", "An unrelated fictional passage.")
    extra_b = make_evidence("unrelated-b", "A different unrelated passage.")
    unrelated_edge = make_relationship(
        EvidenceRelationshipLabel.CONTRADICTS,
        evidence_id=extra_a.evidence_id,
        relationship_id="unrelated-contradiction",
        related_evidence_id=extra_b.evidence_id,
        rationale="This edge concerns a different proposition.",
        scope_comparison=matching_scope_comparison(),
    )

    with pytest.raises(ValidationError, match="same proposition"):
        EvidenceEvaluationRR(
            evaluation_id=conflict.evaluation_id,
            claim=conflict.claim,
            evidence=conflict.evidence + (extra_a, extra_b),
            retrieval_status=conflict.retrieval_status,
            relationships=conflict.relationships + (unrelated_edge,),
            assessment=conflict.assessment,
        )


def test_conflict_requires_an_edge_for_each_opposing_evidence_pair() -> None:
    conflict = make_conflict_rr()
    extra_support_passage = "A second fictional source reports 12 markers."
    extra_support = make_evidence("second-support", extra_support_passage)
    extra_support_relation = make_relationship(
        EvidenceRelationshipLabel.SUPPORTS,
        evidence_id=extra_support.evidence_id,
        relationship_id="second-support-relation",
        passage=extra_support_passage,
        scope_comparison=matching_scope_comparison(),
    )

    with pytest.raises(ValidationError, match="every opposing evidence pair"):
        EvidenceEvaluationRR(
            evaluation_id=conflict.evaluation_id,
            claim=conflict.claim,
            evidence=conflict.evidence + (extra_support,),
            retrieval_status=conflict.retrieval_status,
            relationships=conflict.relationships + (extra_support_relation,),
            assessment=conflict.assessment,
        )


@pytest.mark.parametrize(
    ("edge_evidence_id", "edge_related_id", "edge_atomic_claim_id"),
    [
        ("evidence-supports", "evidence-unrelated", None),
        ("evidence-supports", "evidence-refutes", "unrelated-atom"),
    ],
)
def test_conflict_rejects_orphaned_or_wrong_proposition_contradiction_edges(
    edge_evidence_id, edge_related_id, edge_atomic_claim_id
) -> None:
    conflict = make_conflict_rr()
    relation = make_relationship(
        EvidenceRelationshipLabel.CONTRADICTS,
        evidence_id=edge_evidence_id,
        relationship_id="bad-edge",
        related_evidence_id=edge_related_id,
        atomic_claim_id=edge_atomic_claim_id,
        scope_comparison=matching_scope_comparison(),
    )

    with pytest.raises(ValidationError):
        EvidenceEvaluationRR(
            evaluation_id=conflict.evaluation_id,
            claim=conflict.claim,
            evidence=conflict.evidence,
            retrieval_status=conflict.retrieval_status,
            relationships=conflict.relationships + (relation,),
            assessment=conflict.assessment,
        )


def test_conflict_requires_scope_comparison_annotations() -> None:
    unassessed_scope = EvidenceScopeComparison(
        rationale="No scope comparison was completed."
    )
    with pytest.raises(ValidationError, match="scope assessments"):
        make_conflict_rr(support_scope=unassessed_scope)


def test_supported_verdict_rejects_active_abstention_reason() -> None:
    with pytest.raises(ValidationError, match="abstention"):
        make_rr(
            assessment=make_assessment(
                Verdict.SUPPORTED,
                reasons=[AbstentionReason.UNSUPPORTED_MODALITY],
            ),
            supported_modalities=(ClaimModality.TEXT,),
        )


def test_unsupported_modality_requires_explicit_capability_mismatch() -> None:
    image_claim = make_claim(modality=(ClaimModality.IMAGE,))
    evidence = [make_evidence()]
    relationships = [
        make_relationship(EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT)
    ]
    assessment = make_assessment(
        Verdict.INSUFFICIENT_EVIDENCE,
        reasons=[AbstentionReason.UNSUPPORTED_MODALITY],
    )
    with pytest.raises(ValidationError, match="supported_modalities"):
        make_rr(
            claim=image_claim,
            evidence=evidence,
            relationships=relationships,
            assessment=assessment,
        )

    accepted = make_rr(
        claim=image_claim,
        evidence=evidence,
        relationships=relationships,
        assessment=assessment,
        supported_modalities=(ClaimModality.TEXT,),
    )
    assert accepted.assessment.verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_post_validation_mutation_is_rejected_and_serialization_stays_valid() -> None:
    record = make_rr()

    with pytest.raises(ValidationError, match="frozen"):
        record.assessment.verdict = Verdict.REFUTED
    with pytest.raises(ValidationError, match="frozen"):
        record.relationships[0].label = EvidenceRelationshipLabel.NEUTRAL
    with pytest.raises(ValidationError, match="frozen"):
        record.retrieval_status = RetrievalStatus.FAILED
    with pytest.raises(AttributeError):
        record.relationships.append(
            make_relationship(EvidenceRelationshipLabel.NEUTRAL)
        )
    with pytest.raises(AttributeError):
        record.claim.entities.append(ClaimEntity(mention="new entity"))
    with pytest.raises(AttributeError):
        record.assessment.abstention_reasons.append(
            AbstentionReason.UNSUPPORTED_MODALITY
        )
    with pytest.raises(ValidationError):
        record.model_copy(update={"retrieval_status": RetrievalStatus.FAILED})
    with pytest.raises(ValidationError):
        record.model_copy(
            update={
                "assessment": record.assessment.model_copy(
                    update={"verdict": Verdict.REFUTED}
                )
            }
        )

    restored = EvidenceEvaluationRR.model_validate(
        record.model_dump(mode="json")
    )
    assert restored.assessment.verdict == Verdict.SUPPORTED
    assert restored.relationships[0].label == EvidenceRelationshipLabel.SUPPORTS
    assert restored.retrieval_status == RetrievalStatus.COMPLETED_WITH_RESULTS


def test_model_construct_bypass_is_disabled_and_serialization_revalidates() -> None:
    record = make_rr()
    values = record.model_dump(mode="python")
    values["retrieval_status"] = RetrievalStatus.FAILED

    with pytest.raises(TypeError, match="disabled"):
        EvidenceEvaluationRR.model_construct(**values)

    # Exercise a deliberate bypass of the class-level guard. Application code
    # must still validate before using or serializing such a forged instance.
    forged = BaseModel.model_construct.__func__(EvidenceEvaluationRR, **values)
    with pytest.raises(ValidationError, match="completed results"):
        EvidenceEvaluationRR.model_validate(forged)
    with pytest.raises(ValidationError, match="completed results"):
        forged.model_dump()
    with pytest.raises(ValidationError, match="completed results"):
        forged.model_dump_json()
    with pytest.raises(ValidationError, match="completed results"):
        build_cmrea_evidence_context(forged)

    invalid_json = record.model_dump_json().replace(
        RetrievalStatus.COMPLETED_WITH_RESULTS.value,
        RetrievalStatus.FAILED.value,
    )
    with pytest.raises(ValidationError, match="completed results"):
        EvidenceEvaluationRR.model_validate_json(invalid_json)


def test_nested_record_model_construct_is_disabled() -> None:
    with pytest.raises(TypeError, match="disabled"):
        EvidenceRecord.model_construct(evidence_id="e", source_id="s")


def test_whitespace_only_identifiers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        ClaimRecord(claim_id="   ", original_text="A claim.")
    with pytest.raises(ValidationError, match="cannot be blank"):
        EvidenceRecord(evidence_id="e", source_id="  ")
    with pytest.raises(ValidationError, match="cannot be blank"):
        make_rr().model_copy(update={"evaluation_id": "   "})


def test_whitespace_only_metadata_and_rationales_are_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        RetrievalMethod(method="   ")
    with pytest.raises(ValidationError, match="cannot be blank"):
        EvidenceProvenance(
            status=ProvenanceStatus.VERIFIED,
            document_reference=" ",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            publisher=" ",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            extraction_method=" ",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        SourceReliabilityAssessment(
            adequacy=SourceAdequacy.ADEQUATE,
            rationale=" ",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        EvidenceRelationship(
            relationship_id="r",
            claim_id="c",
            evidence_id="e",
            label=EvidenceRelationshipLabel.NEUTRAL,
            rationale="  ",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        ClaimRecord(claim_id="c", original_text=" ")

    preserved = ClaimRecord(claim_id=" claim ", original_text="Original claim.")
    assert preserved.claim_id == " claim "


def test_temporal_interval_requires_aware_ordered_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        ClaimTemporalScope(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
        )
    with pytest.raises(ValidationError, match="timezone"):
        ClaimTemporalScope(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    with pytest.raises(ValidationError, match="start cannot be after end"):
        ClaimTemporalScope(
            start=datetime(2024, 1, 2, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    equal = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert ClaimTemporalScope(start=equal, end=equal).start == equal


def test_timestamp_fields_reject_naive_and_invalid_timezone_metadata() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            acquisition_timestamp=datetime(2024, 1, 1),
        )
    with pytest.raises(ValidationError):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            acquisition_timestamp="2024-01-01T00:00:00+25:00",
        )


@pytest.mark.parametrize(
    "values",
    [
        {"claim_id": "", "original_text": "A claim."},
        {"claim_id": "c", "original_text": "  "},
        {
            "claim_id": "c",
            "original_text": "A compound claim.",
            "atomicity": ClaimAtomicity.COMPOUND,
            "atomic_claims": [],
        },
        {
            "claim_id": "c",
            "original_text": "A duplicate atom claim.",
            "atomic_claims": [
                {"atomic_claim_id": "same", "text": "first"},
                {"atomic_claim_id": "same", "text": "second"},
            ],
        },
    ],
)
def test_invalid_claim_records_are_rejected(values) -> None:
    with pytest.raises(ValidationError):
        ClaimRecord(**values)


def test_valid_evidence_record_and_explicit_missing_provenance() -> None:
    evidence = make_evidence()
    missing = EvidenceRecord(
        evidence_id="unknown",
        source_id="source-unknown",
        provenance={"status": ProvenanceStatus.NOT_RECORDED},
        extraction_status=ExtractionStatus.NOT_EXTRACTED,
    )

    assert evidence.provenance.status == ProvenanceStatus.VERIFIED
    assert missing.source_url is None
    assert missing.local_reference is None
    assert missing.acquisition_timestamp is None
    assert missing.publication_date is None
    assert missing.extracted_passage is None
    assert missing.provenance.status == ProvenanceStatus.NOT_RECORDED


def test_verified_evidence_requires_complete_provenance_and_passage() -> None:
    with pytest.raises(ValidationError, match="document_reference"):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            local_reference="fixture://source/e",
            acquisition_timestamp=FIXTURE_TIME,
            provenance={"status": ProvenanceStatus.VERIFIED},
        )
    with pytest.raises(ValidationError, match="requires extracted_passage"):
        EvidenceRecord(
            evidence_id="e",
            source_id="s",
            extraction_status=ExtractionStatus.AVAILABLE,
        )


@pytest.mark.parametrize(
    "label",
    list(EvidenceRelationshipLabel),
)
def test_every_evidence_relationship_label_is_validated(label) -> None:
    first_passage = "A manually authored fixture passage."
    evidence = [
        make_evidence("evidence-1", first_passage),
        make_evidence("evidence-2", "A second manually authored fixture passage."),
    ]
    relation = make_relationship(
        label,
        evidence_id="evidence-1",
        related_evidence_id="evidence-2" if label == EvidenceRelationshipLabel.CONTRADICTS else None,
        passage=first_passage,
    )

    record = make_rr(
        evidence=evidence,
        relationships=[relation],
        assessment=make_assessment(None, status=AssessmentStatus.NOT_ASSESSED, rationale=None),
    )
    assert record.relationships[0].label == label


def test_relationship_references_and_spans_fail_closed() -> None:
    with pytest.raises(ValidationError, match="unknown evidence_id"):
        make_rr(
            relationships=[
                make_relationship(
                    EvidenceRelationshipLabel.NEUTRAL,
                    evidence_id="does-not-exist",
                )
            ]
        )
    with pytest.raises(ValidationError, match="exact_text does not match"):
        make_rr(
            relationships=[
                EvidenceRelationship(
                    relationship_id="r",
                    claim_id="claim-1",
                    evidence_id="evidence-1",
                    label=EvidenceRelationshipLabel.SUPPORTS,
                    rationale="Fixture mismatch.",
                    supporting_span=EvidenceSpan(
                        start_char=0,
                        end_char=5,
                        exact_text="wrong",
                    ),
                )
            ]
        )


@pytest.mark.parametrize(
    ("verdict", "relations"),
    [
        (
            Verdict.SUPPORTED,
            [EvidenceRelationshipLabel.SUPPORTS],
        ),
        (
            Verdict.REFUTED,
            [EvidenceRelationshipLabel.REFUTES],
        ),
        (
            Verdict.INSUFFICIENT_EVIDENCE,
            [],
        ),
    ],
)
def test_each_non_conflict_verdict_requires_matching_contract(
    verdict, relations
) -> None:
    if verdict == Verdict.INSUFFICIENT_EVIDENCE:
        record = make_insufficient_rr(AbstentionReason.NO_EVIDENCE_RETRIEVED)
    else:
        label = relations[0]
        passage = "A manually authored fixture passage."
        evidence = make_evidence("decision-evidence", passage)
        record = make_rr(
            evidence=[evidence],
            relationships=[
                make_relationship(
                    label,
                    evidence_id=evidence.evidence_id,
                    passage=passage,
                )
            ],
            assessment=make_assessment(verdict),
        )

    assert record.assessment.verdict == verdict


def test_all_four_verdicts_are_representable_without_collapsing_states() -> None:
    supported = make_rr()
    refuted_passage = "A manually authored refuting fixture passage."
    refuted = make_rr(
        evidence=[make_evidence("refute", refuted_passage)],
        relationships=[
            make_relationship(
                EvidenceRelationshipLabel.REFUTES,
                evidence_id="refute",
                passage=refuted_passage,
            )
        ],
        assessment=make_assessment(Verdict.REFUTED),
    )
    insufficient = make_insufficient_rr(AbstentionReason.NO_EVIDENCE_RETRIEVED)
    conflicting = make_conflict_rr()

    assert {
        supported.assessment.verdict,
        refuted.assessment.verdict,
        insufficient.assessment.verdict,
        conflicting.assessment.verdict,
    } == set(Verdict)


@pytest.mark.parametrize("reason", list(AbstentionReason))
def test_every_abstention_reason_is_representable(reason) -> None:
    if reason == AbstentionReason.EVALUATION_FAILURE:
        assessment = make_assessment(
            None,
            status=AssessmentStatus.EVALUATION_FAILED,
            reasons=[reason],
            rationale=None,
        )
        record = make_rr(
            evidence=[],
            relationships=[],
            assessment=assessment,
            retrieval_status=RetrievalStatus.NOT_STARTED,
        )
    elif reason == AbstentionReason.NO_EVIDENCE_RETRIEVED:
        record = make_insufficient_rr(reason)
    elif reason == AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE:
        record = make_conflict_rr()
    elif reason == AbstentionReason.INSUFFICIENT_EVIDENCE_QUALITY:
        evidence = make_evidence(
            adequacy=SourceAdequacy.UNKNOWN,
            reliability_rationale="Fixture source quality is unknown.",
        )
        record = make_insufficient_rr(
            reason,
            evidence=[evidence],
            relationship=make_relationship(
                EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
            ),
        )
    elif reason == AbstentionReason.AMBIGUOUS_CLAIM:
        record = make_insufficient_rr(
            reason,
            claim=make_claim(atomicity=ClaimAtomicity.AMBIGUOUS),
            relationship=make_relationship(
                EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
            ),
        )
    elif reason == AbstentionReason.PROVENANCE_UNVERIFIABLE:
        record = make_insufficient_rr(
            reason,
            evidence=[
                make_evidence(
                    provenance_status=ProvenanceStatus.UNVERIFIABLE,
                    local_reference=None,
                )
            ],
            relationship=make_relationship(
                EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
            ),
        )
    elif reason == AbstentionReason.UNSUPPORTED_MODALITY:
        record = make_rr(
            claim=make_claim(modality=[ClaimModality.IMAGE]),
            evidence=[make_evidence()],
            relationships=[
                make_relationship(
                    EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
                )
            ],
            assessment=make_assessment(
                Verdict.INSUFFICIENT_EVIDENCE,
                reasons=[reason],
            ),
            supported_modalities=(ClaimModality.TEXT,),
        )
    else:
        record = make_insufficient_rr(
            reason,
            relationship=make_relationship(
                EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
            ),
        )

    assert record.assessment.abstention_reasons == (reason,)


def test_processing_states_are_not_factual_verdicts() -> None:
    not_assessed = make_rr(
        evidence=[],
        relationships=[],
        assessment=make_assessment(
            None,
            status=AssessmentStatus.NOT_ASSESSED,
            rationale=None,
        ),
        retrieval_status=RetrievalStatus.NOT_STARTED,
    )
    unavailable = make_rr(
        evidence=[],
        relationships=[],
        assessment=make_assessment(
            None,
            status=AssessmentStatus.EVIDENCE_UNAVAILABLE,
            rationale=None,
        ),
        retrieval_status=RetrievalStatus.UNAVAILABLE,
    )
    failed = make_rr(
        evidence=[],
        relationships=[],
        assessment=make_assessment(
            None,
            status=AssessmentStatus.EVALUATION_FAILED,
            reasons=[AbstentionReason.EVALUATION_FAILURE],
            rationale=None,
        ),
        retrieval_status=RetrievalStatus.NOT_STARTED,
    )

    assert not_assessed.assessment.verdict is None
    assert unavailable.assessment.verdict is None
    assert failed.assessment.verdict is None


def test_missing_evidence_is_not_silently_mapped_to_gold_insufficient() -> None:
    with pytest.raises(ValidationError, match="completed-empty"):
        make_rr(
            evidence=[],
            relationships=[],
            assessment=make_assessment(
                Verdict.INSUFFICIENT_EVIDENCE,
                reasons=[AbstentionReason.NO_EVIDENCE_RETRIEVED],
            ),
            retrieval_status=RetrievalStatus.NOT_RECORDED,
        )


def test_conflicting_evidence_requires_both_sides_and_linked_contradiction() -> None:
    conflict = make_conflict_rr()
    assert conflict.assessment.verdict == Verdict.CONFLICTING_EVIDENCE

    with pytest.raises(ValidationError, match="CONTRADICTS"):
        make_rr(
            evidence=[
                make_evidence("positive", "A fictional count is 12."),
                make_evidence("negative", "A fictional count is 9."),
            ],
            relationships=[
                make_relationship(
                    EvidenceRelationshipLabel.SUPPORTS,
                    evidence_id="positive",
                    passage="A fictional count is 12.",
                    scope_comparison=matching_scope_comparison(),
                ),
                make_relationship(
                    EvidenceRelationshipLabel.REFUTES,
                    evidence_id="negative",
                    relationship_id="r-negative",
                    passage="A fictional count is 9.",
                    scope_comparison=matching_scope_comparison(),
                ),
            ],
            assessment=make_assessment(
                Verdict.CONFLICTING_EVIDENCE,
                reasons=[AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE],
            ),
        )


def test_temporal_and_numerical_scope_mismatches_are_retained() -> None:
    temporal = make_claim(
        temporal_scope=ClaimTemporalScope(
            reference_text="2024",
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
    )
    number = make_claim(
        quantities=[
            ClaimQuantity(value="12", unit="per 100", denominator="100 residents")
        ]
    )
    temporal_record = make_off_scope_fixture(
        "temporal",
        claim=temporal,
        passage="The fictional council recorded 12 markers in 2022.",
    )
    numerical_record = make_off_scope_fixture(
        "numerical",
        claim=number,
        passage="The fictional council recorded 12 markers per 1,000 residents.",
    )

    assert temporal_record.claim.temporal_scope.reference_text == "2024"
    assert temporal_record.relationships[0].label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert numerical_record.claim.quantities[0].denominator == "100 residents"
    assert numerical_record.assessment.verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_compound_directional_verdict_requires_every_atomic_claim() -> None:
    claim = make_claim(
        atomicity=ClaimAtomicity.COMPOUND,
        atomic_claims=[
            AtomicClaim(atomic_claim_id="a1", text="The council recorded 12 markers."),
            AtomicClaim(atomic_claim_id="a2", text="The council recorded them in 2024."),
        ],
    )
    passage = "The fictional Alder council recorded 12 test markers in 2024."

    with pytest.raises(ValidationError, match="atomic_claim_id"):
        make_rr(
            claim=claim,
            relationships=[
                make_relationship(
                    EvidenceRelationshipLabel.SUPPORTS,
                    passage=passage,
                )
            ],
        )


def test_serialization_round_trip_and_cmrea_traceability() -> None:
    record = make_nondirectional_rr()
    payload = record.model_dump(mode="json")
    restored = EvidenceEvaluationRR.model_validate(payload)
    context = build_cmrea_evidence_context(restored)

    assert restored == record
    assert context.retrieval_status == record.retrieval_status
    assert context.claim.original_text == record.claim.original_text
    assert context.claim.claim_id == record.claim.claim_id
    assert context.evidence[0].evidence_id == record.evidence[0].evidence_id
    assert context.evidence[0].extracted_passage == record.evidence[0].extracted_passage
    assert (
        context.evidence[0].provenance.document_reference
        == record.evidence[0].provenance.document_reference
    )
    assert context.relationships[0].label == record.relationships[0].label
    assert context.relationships[0].rationale == record.relationships[0].rationale
    assert context.assessment.status == record.assessment.status
    assert context.assessment.verdict is None
    assert context.assessment.abstention_reasons == ()
    assert not hasattr(context, "natural_language_explanation")
    assert context.explanation_constraints


def test_cmrea_context_preserves_failed_retrieval_without_factual_verdict() -> None:
    record = make_rr(
        evidence=[],
        relationships=[],
        retrieval_status=RetrievalStatus.FAILED,
        assessment=make_assessment(
            None,
            status=AssessmentStatus.EVIDENCE_UNAVAILABLE,
            rationale=None,
        ),
    )
    context = build_cmrea_evidence_context(record)

    assert context.retrieval_status == RetrievalStatus.FAILED
    assert context.assessment.status == AssessmentStatus.EVIDENCE_UNAVAILABLE
    assert context.assessment.verdict is None


def test_cmrea_direct_construction_validates_rr_invariants() -> None:
    record = make_nondirectional_rr()
    context = build_cmrea_evidence_context(record)
    values = context.model_dump(mode="python")
    values["retrieval_status"] = RetrievalStatus.COMPLETED_EMPTY

    with pytest.raises(ValidationError, match="cannot contain evidence"):
        type(context).model_validate(values)

    bad_relationships = (
        make_relationship(
            EvidenceRelationshipLabel.NEUTRAL,
            evidence_id="missing-evidence",
        ),
    )
    with pytest.raises(ValidationError, match="unknown evidence_id"):
        type(context).model_validate(
            {
                **context.model_dump(mode="python"),
                "relationships": bad_relationships,
            }
        )


def test_cmrea_model_construct_and_json_reconstruction_validate() -> None:
    context = build_cmrea_evidence_context(make_nondirectional_rr())
    with pytest.raises(TypeError, match="disabled"):
        type(context).model_construct(**context.model_dump(mode="python"))

    restored = type(context).model_validate_json(context.model_dump_json())
    assert restored == context


@pytest.mark.parametrize(
    ("label", "verdict"),
    [
        (EvidenceRelationshipLabel.SUPPORTS, Verdict.SUPPORTED),
        (EvidenceRelationshipLabel.REFUTES, Verdict.REFUTED),
    ],
)
def test_direct_directional_rr_cannot_enter_cmrea(
    label: EvidenceRelationshipLabel,
    verdict: Verdict,
) -> None:
    claim = make_claim(
        text="13 people attended the event.",
        quantities=[ClaimQuantity(value="13", unit="people")],
    )
    passage = "12 people attended the event."
    evidence = make_evidence("task55g-mismatch-" + label.value.lower(), passage)
    relation = make_relationship(
        label,
        evidence_id=evidence.evidence_id,
        passage=passage,
    )
    rr = make_rr(
        claim=claim,
        evidence=[evidence],
        relationships=[relation],
        assessment=make_assessment(verdict),
    )
    assert not rr.is_evaluator_authorized_for_directional_processing()
    import app.evidence.trust as trust
    from app.evidence.trust import _issue_cmrea_capability

    assert _issue_cmrea_capability(rr) is None
    assert not trust._authorized_reasoning_representations.add(rr)
    assert not trust._IdentityRegistry._register_snapshot(
        trust._authorized_reasoning_representations,
        rr,
    )
    assert not trust._authorized_cmrea_contexts.add(rr)

    with pytest.raises(ValueError, match="caller-created directional RR content"):
        build_cmrea_evidence_context(rr)
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(rr.model_dump(mode="python"))
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate_json(rr.model_dump_json())

    reconstructed = EvidenceEvaluationRR.model_validate_json(rr.model_dump_json())
    with pytest.raises(ValueError, match="caller-created directional RR content"):
        build_cmrea_evidence_context(reconstructed)
    copied = rr.model_copy(deep=True)
    assert not copied.is_evaluator_authorized_for_directional_processing()
    with pytest.raises(ValueError, match="caller-created directional RR content"):
        build_cmrea_evidence_context(copied)
    with pytest.raises(ValueError, match="caller-created directional RR content"):
        build_cmrea_evidence_context(deepcopy(rr))


@pytest.fixture
def authorize_directional_rr_test_only(monkeypatch):
    """Seed private trust for mutation tests without changing evaluator scope."""
    import app.evidence.trust as trust

    registry = trust._IdentityRegistry()
    monkeypatch.setattr(
        trust,
        "_authorized_reasoning_representations",
        registry,
    )

    def authorize(record: EvidenceEvaluationRR) -> None:
        assert registry.add(record)

    return authorize


def test_generic_reasoning_representation_issuer_is_not_available() -> None:
    import app.evidence.trust as trust

    assert not hasattr(trust, "_authorize_reasoning_representation")
    assert "_authorize_reasoning_representation" not in getattr(
        trust, "__all__", ()
    )
    with pytest.raises(ImportError):
        exec(
            "from app.evidence.trust import _authorize_reasoning_representation",
            {},
        )
    public_exports: dict[str, object] = {}
    exec("from app.evidence.trust import *", public_exports)
    assert "_authorize_reasoning_representation" not in public_exports


def test_identity_registry_uses_identity_and_weak_reference_lifecycle() -> None:
    from concurrent.futures import ThreadPoolExecutor
    import gc
    import weakref

    from app.evidence.trust import _IdentityRegistry

    registry = _IdentityRegistry()
    record = make_nondirectional_rr()
    copied = record.model_copy(deep=True)
    assert copied == record
    assert registry.add(record)
    assert registry.contains(record)
    assert not registry.contains(copied)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(registry.contains, [record] * 32))
    assert all(results)

    identity = id(record)
    record_reference = weakref.ref(record)
    del record
    gc.collect()

    assert record_reference() is None
    assert identity not in registry._items


@pytest.mark.parametrize(
    "field",
    [
        "relationship_label",
        "relationship_rationale",
        "assessment_verdict",
        "claim_text",
        "claim_id",
        "claim_nested_entity",
        "evidence_title",
        "evidence_passage",
        "evidence_fingerprint",
        "evidence_nested_provenance",
        "relationship_collection_replaced",
        "relationship_collection_extended",
    ],
)
def test_rr_content_mutation_permanently_revokes_authorization(
    field: str,
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    relationship = record.relationships[0]
    original_value = None

    if field == "relationship_label":
        target = relationship
        attribute = "label"
        original_value = relationship.label
        changed_value = EvidenceRelationshipLabel.NEUTRAL
        target.__dict__[attribute] = changed_value
    elif field == "relationship_rationale":
        target = relationship
        attribute = "rationale"
        original_value = relationship.rationale
        changed_value = "Changed after authorization."
        target.__dict__[attribute] = changed_value
    elif field == "assessment_verdict":
        target = record.assessment
        attribute = "verdict"
        original_value = record.assessment.verdict
        changed_value = Verdict.REFUTED
        target.__dict__[attribute] = changed_value
    elif field == "claim_text":
        target = record.claim
        attribute = "original_text"
        original_value = record.claim.original_text
        changed_value = "Changed claim after authorization."
        target.__dict__[attribute] = changed_value
    elif field == "claim_id":
        target = record.claim
        attribute = "claim_id"
        original_value = record.claim.claim_id
        changed_value = "different-claim"
        target.__dict__[attribute] = changed_value
    elif field == "claim_nested_entity":
        target = record.claim.entities[0]
        attribute = "mention"
        original_value = target.mention
        changed_value = "different entity"
        target.__dict__[attribute] = changed_value
    elif field == "evidence_title":
        target = record.evidence[0]
        attribute = "source_title"
        original_value = target.source_title
        changed_value = "Changed source title."
        target.__dict__[attribute] = changed_value
    elif field == "evidence_passage":
        target = record.evidence[0]
        attribute = "extracted_passage"
        original_value = target.extracted_passage
        changed_value = "Changed evidence passage."
        target.__dict__[attribute] = changed_value
    elif field == "evidence_fingerprint":
        target = record.evidence[0].provenance
        attribute = "content_sha256"
        original_value = target.content_sha256
        changed_value = "a" * 64
        target.__dict__[attribute] = changed_value
    elif field == "evidence_nested_provenance":
        target = record.evidence[0].provenance
        attribute = "notes"
        original_value = target.notes
        changed_value = "Changed provenance."
        target.__dict__[attribute] = changed_value
    elif field == "relationship_collection_replaced":
        target = record
        attribute = "relationships"
        original_value = record.relationships
        changed_value = ()
        object.__setattr__(target, attribute, changed_value)
    else:
        target = record
        attribute = "relationships"
        original_value = record.relationships
        changed_value = (*record.relationships, relationship)
        object.__setattr__(target, attribute, changed_value)

    assert not record.is_evaluator_authorized_for_directional_processing()
    if field in {"relationship_collection_replaced", "relationship_collection_extended"}:
        object.__setattr__(target, attribute, original_value)
    else:
        target.__dict__[attribute] = original_value
    assert not record.is_evaluator_authorized_for_directional_processing()
    with pytest.raises((ValueError, ValidationError)):
        build_cmrea_evidence_context(record)


def test_rr_snapshot_failure_revokes_authorization_permanently(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    original_value = record.evidence[0].provenance.content_sha256

    record.evidence[0].provenance.__dict__["content_sha256"] = object()
    assert not record.is_evaluator_authorized_for_directional_processing()

    record.evidence[0].provenance.__dict__["content_sha256"] = original_value
    assert not record.is_evaluator_authorized_for_directional_processing()


def test_rr_model_copy_with_updated_claim_does_not_transfer_authorization(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)

    copied = record.model_copy(
        update={"claim": make_claim(original_text="A copied claim.")},
        deep=True,
    )

    assert copied is not record
    assert not copied.is_evaluator_authorized_for_directional_processing()


@pytest.mark.parametrize("field", ["claim", "evidence"])
def test_rr_context_substitution_revokes_authorization(
    field: str,
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)

    if field == "claim":
        object.__setattr__(
            record,
            "claim",
            make_claim(text="A different claim with the same identifier."),
        )
    else:
        original = record.evidence[0]
        replacement = make_evidence(
            original.evidence_id,
            original.extracted_passage,
            local_reference="fixture://different-evidence-source",
        )
        object.__setattr__(record, "evidence", (replacement,))

    assert not record.is_evaluator_authorized_for_directional_processing()
    with pytest.raises((ValueError, ValidationError)):
        build_cmrea_evidence_context(record)


@pytest.mark.parametrize(
    "field",
    [
        "relationship_label",
        "assessment_verdict",
        "claim_text",
        "evidence_passage",
        "relationship_collection",
        "explanation_constraints",
    ],
)
def test_cmrea_content_mutation_revokes_serialization_authorization(
    field: str,
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    context = build_cmrea_evidence_context(record)
    context_fields = object.__getattribute__(context, "__dict__")

    if field == "relationship_label":
        context_fields["relationships"][0].__dict__[
            "label"
        ] = EvidenceRelationshipLabel.REFUTES
    elif field == "assessment_verdict":
        context_fields["assessment"].__dict__["verdict"] = Verdict.REFUTED
    elif field == "claim_text":
        context_fields["claim"].__dict__["original_text"] = "Changed context claim."
    elif field == "evidence_passage":
        context_fields["evidence"][0].__dict__[
            "extracted_passage"
        ] = "Changed context evidence."
    elif field == "relationship_collection":
        object.__setattr__(context, "relationships", ())
    else:
        object.__setattr__(
            context,
            "explanation_constraints",
            (*context.explanation_constraints, "Changed explanation instruction."),
        )

    from app.evidence.trust import _is_authorized_cmrea_context

    assert not _is_authorized_cmrea_context(context)
    with pytest.raises(ValueError, match="authorized directional CMREA context was modified"):
        context.model_dump()


def test_authorized_cmrea_context_copy_and_json_reconstruction_do_not_restore_trust(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    context = build_cmrea_evidence_context(record)

    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        type(context).model_validate_json(context.model_dump_json())
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        context.model_copy(deep=True)


def test_cmrea_builder_detaches_nested_objects_from_authorized_rr(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    context = build_cmrea_evidence_context(record)

    assert context.claim is not record.claim
    assert context.evidence[0] is not record.evidence[0]
    assert context.relationships[0] is not record.relationships[0]
    context.relationships[0].__dict__["rationale"] = "Context-only mutation."
    assert context.relationships[0].rationale == record.relationships[0].rationale
    assert record.relationships[0].rationale != "Context-only mutation."
    assert record.is_evaluator_authorized_for_directional_processing()


def test_cmrea_serialization_consumes_snapshot_after_source_mutation(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    context = build_cmrea_evidence_context(record)

    record.relationships[0].__dict__["label"] = EvidenceRelationshipLabel.REFUTES
    record.assessment.__dict__["verdict"] = Verdict.REFUTED
    record.claim.__dict__["original_text"] = "Changed source claim."
    record.evidence[0].__dict__["extracted_passage"] = "Changed source passage."

    payload = context.model_dump(mode="python")
    assert payload["relationships"][0]["label"] == EvidenceRelationshipLabel.SUPPORTS
    assert payload["assessment"]["verdict"] == Verdict.SUPPORTED
    assert payload["claim"]["original_text"] != "Changed source claim."
    assert payload["evidence"][0]["extracted_passage"] != "Changed source passage."


def test_cmrea_serialization_race_uses_the_captured_snapshot(
    authorize_directional_rr_test_only,
    monkeypatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import app.evidence.trust as trust

    record = make_rr()
    authorize_directional_rr_test_only(record)
    context = build_cmrea_evidence_context(record)
    snapshot_captured = Event()
    mutation_complete = Event()
    registry = trust._authorized_cmrea_contexts
    snapshot_if_authorized = registry.snapshot_if_authorized

    def pause_after_snapshot(item):
        snapshot = snapshot_if_authorized(item)
        if item is context:
            snapshot_captured.set()
            if not mutation_complete.wait(timeout=5):
                raise TimeoutError("concurrent mutation was not released")
        return snapshot

    monkeypatch.setattr(registry, "snapshot_if_authorized", pause_after_snapshot)
    with ThreadPoolExecutor(max_workers=1) as executor:
        serialized = executor.submit(context.model_dump, mode="python")
        assert snapshot_captured.wait(timeout=5)
        context_fields = object.__getattribute__(context, "__dict__")
        context_fields["relationships"][0].__dict__[
            "label"
        ] = EvidenceRelationshipLabel.REFUTES
        context_fields["assessment"].__dict__["verdict"] = Verdict.REFUTED
        mutation_complete.set()
        payload = serialized.result(timeout=5)

    assert payload["relationships"][0]["label"] == EvidenceRelationshipLabel.SUPPORTS
    assert payload["assessment"]["verdict"] == Verdict.SUPPORTED
    from app.evidence.trust import _is_authorized_cmrea_context

    assert not _is_authorized_cmrea_context(context)


def test_mutation_before_snapshot_creation_fails_closed(
    authorize_directional_rr_test_only,
) -> None:
    record = make_rr()
    authorize_directional_rr_test_only(record)
    record.relationships[0].__dict__["rationale"] = "Changed before snapshot."

    with pytest.raises(ValueError, match="caller-created directional RR content"):
        build_cmrea_evidence_context(record)


def test_mutation_during_snapshot_creation_consumes_captured_content(
    authorize_directional_rr_test_only,
    monkeypatch,
) -> None:
    import app.evidence.trust as trust

    record = make_rr()
    authorize_directional_rr_test_only(record)
    content_snapshot = trust._content_snapshot
    changed = False

    def capture_then_mutate(value):
        nonlocal changed
        snapshot = content_snapshot(value)
        if value is record and not changed:
            changed = True
            record.relationships[0].__dict__[
                "label"
            ] = EvidenceRelationshipLabel.REFUTES
            record.assessment.__dict__["verdict"] = Verdict.REFUTED
        return snapshot

    monkeypatch.setattr(trust, "_content_snapshot", capture_then_mutate)
    context = build_cmrea_evidence_context(record)

    payload = context.model_dump(mode="python")
    assert payload["relationships"][0]["label"] == EvidenceRelationshipLabel.SUPPORTS
    assert payload["assessment"]["verdict"] == Verdict.SUPPORTED


def test_concurrent_cmrea_builders_use_separate_immutable_snapshots(
    authorize_directional_rr_test_only,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    record = make_rr()
    authorize_directional_rr_test_only(record)
    with ThreadPoolExecutor(max_workers=4) as executor:
        contexts = list(
            executor.map(build_cmrea_evidence_context, [record] * 8)
        )

    assert len(contexts) == 8
    assert all(
        context.model_dump(mode="python")["relationships"][0]["label"]
        == EvidenceRelationshipLabel.SUPPORTS
        for context in contexts
    )


def test_cmrea_capability_is_bound_and_consumed_once(
    authorize_directional_rr_test_only,
) -> None:
    import copy
    import pickle

    from app.evidence.trust import (
        _issue_cmrea_capability,
    )

    record = make_rr()
    other_record = record.model_copy(
        update={"evaluation_id": "different-evaluation"},
        deep=True,
    )
    authorize_directional_rr_test_only(record)
    transfer_issuance = _issue_cmrea_capability(record)
    assert transfer_issuance is not None
    transfer_capability, _ = transfer_issuance

    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(
            other_record.model_dump(mode="json"),
            context=transfer_capability,
        )

    altered_context_issuance = _issue_cmrea_capability(record)
    assert altered_context_issuance is not None
    altered_context_capability, _ = altered_context_issuance
    altered_payload = record.model_dump(mode="json")
    altered_payload["explanation_constraints"] = [
        "A caller-controlled explanation instruction."
    ]
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(
            altered_payload,
            context=altered_context_capability,
        )

    issuance = _issue_cmrea_capability(record)
    assert issuance is not None
    capability, _ = issuance
    copied_capability = copy.copy(capability)
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(
            record.model_dump(mode="json"),
            context=copied_capability,
        )
    serialized_capability = pickle.dumps(capability)
    reconstructed_capability = pickle.loads(serialized_capability)
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(
            record.model_dump(mode="json"),
            context=reconstructed_capability,
        )
    context = CMREAEvidenceContext.model_validate(
        record.model_dump(mode="json"),
        context=capability,
    )
    assert context.relationships[0].label == EvidenceRelationshipLabel.SUPPORTS
    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext.model_validate(
            record.model_dump(mode="json"),
            context=capability,
        )


def test_cmrea_capability_concurrent_consumption_is_one_use(
    authorize_directional_rr_test_only,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.evidence.trust import (
        _issue_cmrea_capability,
    )

    record = make_rr()
    authorize_directional_rr_test_only(record)
    issuance = _issue_cmrea_capability(record)
    assert issuance is not None
    capability, _ = issuance
    payload = record.model_dump(mode="json")

    def attempt() -> bool:
        try:
            CMREAEvidenceContext.model_validate(payload, context=capability)
        except ValidationError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [False, True]


@pytest.mark.parametrize(
    "label",
    [
        EvidenceRelationshipLabel.SUPPORTS,
        EvidenceRelationshipLabel.REFUTES,
        EvidenceRelationshipLabel.PARTIALLY_SUPPORTS,
        EvidenceRelationshipLabel.PARTIALLY_REFUTES,
    ],
)
def test_direct_cmrea_construction_rejects_untrusted_directional_relationships(
    label: EvidenceRelationshipLabel,
) -> None:
    evidence = make_evidence("cmrea-untrusted-" + label.value.lower())
    rr = make_rr(
        evidence=[evidence],
        relationships=[
            make_relationship(
                label,
                evidence_id=evidence.evidence_id,
                passage=evidence.extracted_passage,
            )
        ],
        assessment=make_assessment(
            None,
            status=AssessmentStatus.NOT_ASSESSED,
            rationale=None,
        ),
    )
    payload = rr.model_dump(mode="python")

    with pytest.raises(ValidationError, match="evaluator-authorized RR provenance"):
        CMREAEvidenceContext(**payload)

    constructed = BaseModel.model_construct.__func__(
        CMREAEvidenceContext,
        **payload,
    )
    with pytest.raises((ValueError, ValidationError)):
        constructed.model_dump()
    with pytest.raises(ValidationError):
        CMREAEvidenceContext.model_validate(constructed)


def test_directional_assessment_cannot_authorize_cmrea_without_rr_relationship() -> None:
    payload = make_nondirectional_rr().model_dump(mode="python")
    payload["assessment"] = make_assessment(Verdict.SUPPORTED)

    with pytest.raises(ValidationError):
        CMREAEvidenceContext.model_validate(payload)


@pytest.mark.parametrize(
    ("status", "verdict", "reasons"),
    [
        (AssessmentStatus.ASSESSED, Verdict.SUPPORTED, []),
        (AssessmentStatus.ASSESSED, Verdict.REFUTED, []),
        (
            AssessmentStatus.ASSESSED,
            Verdict.INSUFFICIENT_EVIDENCE,
            [AbstentionReason.NO_EVIDENCE_RETRIEVED],
        ),
        (
            AssessmentStatus.ASSESSED,
            Verdict.CONFLICTING_EVIDENCE,
            [AbstentionReason.CONFLICTING_CREDIBLE_EVIDENCE],
        ),
    ],
)
def test_assessment_schema_preserves_each_verdict(status, verdict, reasons) -> None:
    assessment = make_assessment(verdict, status=status, reasons=reasons)
    assert assessment.verdict == verdict


def test_contradiction_relation_requires_a_distinct_related_evidence_id() -> None:
    with pytest.raises(ValidationError, match="related_evidence_id"):
        EvidenceRelationship(
            relationship_id="bad",
            claim_id="claim-1",
            evidence_id="evidence-1",
            label=EvidenceRelationshipLabel.CONTRADICTS,
            rationale="No other evidence is linked.",
        )
