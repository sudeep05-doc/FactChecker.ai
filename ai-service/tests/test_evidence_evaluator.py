"""Original offline contract and mapping tests, not NLI accuracy evaluation."""

from datetime import date, datetime, timezone
import json
from typing import Optional, Tuple

import pytest
from pydantic import ValidationError

from app.cmrea.evidence import build_cmrea_evidence_context
from app.evidence.evaluator import (
    EvaluationStatus,
    EvidenceScopeAssessment,
    EvidenceRelationshipEvaluator,
    InferenceStatus,
    ModelLoadError,
    NLIBackend,
    NLIClassDecoder,
    NLIClass,
    NLIInference,
    NLIScore,
    NLIScoreKind,
    ScopeVerificationState,
    ScopeDimensionAssessment,
    UnavailableNLIBackend,
    attach_relationship_to_rr,
)
from app.evidence.schemas import (
    AssessmentStatus,
    ClaimAssessment,
    ClaimAtomicity,
    ClaimAttribution,
    ClaimEntity,
    ClaimGeographicScope,
    ClaimQuantity,
    ClaimRelation,
    ClaimRecord,
    ClaimTemporalScope,
    EvidenceModality,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceRelationship,
    EvidenceRelationshipLabel,
    EvidenceSpan,
    ExtractionStatus,
    RetrievalMethod,
    RetrievalStatus,
    ScopeMatchStatus,
)
from app.rr.evidence import EvidenceEvaluationRR


FIXTURE_TIME = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
PASSAGE = (
    "The fictional Alder council recorded 12 test markers in the fictional "
    "Alder district among all residents in 2024."
)
CLAIM_TEXT = (
    "The fictional Alder council recorded 12 test markers in the fictional "
    "Alder district in 2024."
)


class FixtureNLIBackend:
    available = True
    supported_languages = ("en",)
    model_identity = "test-only-fixture-nli"
    model_version = "fixture-v1"

    def __init__(
        self,
        label: NLIClass = NLIClass.ENTAILMENT,
        *,
        failure: Optional[Exception] = None,
        tie: bool = False,
    ) -> None:
        self.label = label
        self.failure = failure
        self.tie = tie
        self.received: Optional[Tuple[str, str]] = None

    def infer(self, premise: str, hypothesis: str) -> NLIInference:
        self.received = (premise, hypothesis)
        if self.failure is not None:
            raise self.failure
        scores = (
            {
                NLIClass.ENTAILMENT: 0.45,
                NLIClass.CONTRADICTION: 0.45,
                NLIClass.NEUTRAL: 0.1,
            }
            if self.tie
            else {
                label: (0.8 if label == self.label else 0.1)
                for label in NLIClass
            }
        )
        return NLIInference(
            status=InferenceStatus.INFERENCE_SUCCEEDED,
            model_identity=self.model_identity,
            model_version=self.model_version,
            scores=tuple(NLIScore(label=key, value=value) for key, value in scores.items()),
            score_kind=NLIScoreKind.PROBABILITIES,
        )


def make_claim(**overrides) -> ClaimRecord:
    values = {
        "claim_id": "claim-fixture",
        "original_text": CLAIM_TEXT,
        "atomicity": ClaimAtomicity.ATOMIC,
        "entities": (ClaimEntity(mention="fictional Alder council"),),
        "quantities": (ClaimQuantity(value="12", unit="test markers"),),
        "temporal_scope": ClaimTemporalScope(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc),
            reference_text="2024",
        ),
        "geographic_scope": ClaimGeographicScope(place="fictional Alder district"),
        "attribution": ClaimAttribution(
            speaker="fictional Alder council",
            reporting_action="recorded",
        ),
        "relations": (
            ClaimRelation(
                subject="fictional Alder council",
                predicate="recorded",
                object="12 test markers",
                polarity="affirmative",
            ),
        ),
        "extraction_provenance": {
            "status": "RECORDED",
            "input_reference": "fixture://task55/claim",
            "method": "manual_fixture_authoring",
            "extracted_at": FIXTURE_TIME,
        },
    }
    values.update(overrides)
    return ClaimRecord(**values)


def make_evidence(
    *,
    passage: Optional[str] = PASSAGE,
    extraction_status: ExtractionStatus = ExtractionStatus.AVAILABLE,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="evidence-fixture",
        source_id="fixture-source",
        source_title="Original local test fixture",
        local_reference="fixture://task55/evidence",
        publication_date=date(2024, 12, 1),
        acquisition_timestamp=FIXTURE_TIME,
        extracted_passage=passage,
        source_modality=EvidenceModality.TEXT,
        retrieval_method=RetrievalMethod(
            method="manual_fixture",
            status=RetrievalStatus.COMPLETED_WITH_RESULTS,
        ),
        provenance=EvidenceProvenance(
            status="VERIFIED",
            document_reference="fixture-document-v1",
        ),
        source_reliability_assessment={
            "adequacy": "ADEQUATE",
            "rationale": "Manual fixture annotation only.",
        },
        extraction_status=extraction_status,
        extraction_method=(
            "manual_fixture_authoring"
            if extraction_status == ExtractionStatus.AVAILABLE
            else None
        ),
    )


def evaluate(
    label: NLIClass = NLIClass.ENTAILMENT,
    *,
    claim: Optional[ClaimRecord] = None,
    evidence: Optional[EvidenceRecord] = None,
    language: Optional[str] = "en",
    backend: Optional[NLIBackend] = None,
    atomic_claim_id: Optional[str] = None,
    scope_assessment: Optional[EvidenceScopeAssessment] = None,
):
    selected_backend = backend or FixtureNLIBackend(label)
    result = EvidenceRelationshipEvaluator(selected_backend).evaluate(
        claim or make_claim(),
        evidence or make_evidence(),
        language=language,
        atomic_claim_id=atomic_claim_id,
        scope_assessment=scope_assessment,
    )
    return result, selected_backend


def scope_item(
    status: ScopeMatchStatus,
    claim_value: Optional[str] = None,
    evidence_value: Optional[str] = None,
    evidence_basis: Optional[str] = None,
) -> ScopeDimensionAssessment:
    return ScopeDimensionAssessment(
        status=status,
        claim_value=claim_value,
        evidence_value=evidence_value,
        evidence_basis=evidence_basis,
        rationale="Manually reviewed fictional fixture scope annotation.",
    )


def matching_scope_assessment(
    claim: Optional[ClaimRecord] = None,
) -> EvidenceScopeAssessment:
    record = claim or make_claim()

    def canonical_temporal_value(claim_record: ClaimRecord) -> str:
        temporal = claim_record.temporal_scope
        return json.dumps(
            {
                "as_of": temporal.as_of.isoformat() if temporal and temporal.as_of else None,
                "end": temporal.end.isoformat() if temporal and temporal.end else None,
                "reference_text": temporal.reference_text if temporal else None,
                "start": temporal.start.isoformat() if temporal and temporal.start else None,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def comparison(
        claim_value: str,
        evidence_value: str,
        evidence_basis: str,
    ) -> ScopeDimensionAssessment:
        return scope_item(
            ScopeMatchStatus.MATCH
            if claim_value == evidence_value
            else ScopeMatchStatus.MISMATCH,
            claim_value,
            evidence_value,
            evidence_basis,
        )

    entity_value = record.entities[0].mention
    quantity_value = record.quantities[0].value
    unit_value = record.quantities[0].unit
    temporal_value = canonical_temporal_value(record)
    geographic_value = (
        record.geographic_scope.place
        if record.geographic_scope and record.geographic_scope.place
        else None
    )
    attribution_value = (
        f"{record.attribution.speaker} {record.attribution.reporting_action}"
        if record.attribution
        and record.attribution.speaker
        and record.attribution.reporting_action
        else None
    )
    polarity_value = (
        record.relations[0].polarity
        if record.relations and record.relations[0].polarity
        else None
    )
    return EvidenceScopeAssessment(
        entity=comparison(entity_value, "fictional Alder council", "fictional Alder council"),
        quantity=comparison(quantity_value, "12", "12"),
        unit=comparison(unit_value or "unspecified unit", "test markers", "test markers"),
        temporal=comparison(
            temporal_value,
            canonical_temporal_value(make_claim()),
            "in 2024",
        ),
        geographic=comparison(
            geographic_value or "unspecified geography",
            "fictional Alder district",
            "fictional Alder district",
        ),
        population=scope_item(
            ScopeMatchStatus.NOT_APPLICABLE,
            evidence_basis="The claim has no structured population scope.",
        ),
        attribution=comparison(
            attribution_value or "unspecified attribution",
            "fictional Alder council recorded",
            "fictional Alder council recorded",
        ),
        polarity=comparison(
            polarity_value or "unspecified polarity",
            "affirmative",
            "fictional Alder council recorded 12 test markers",
        ),
        conditional=scope_item(
            ScopeMatchStatus.NOT_APPLICABLE,
            evidence_basis="The claim has no recorded conditional clause.",
        ),
    )


def scope_with(
    base: EvidenceScopeAssessment,
    **updates: ScopeDimensionAssessment,
) -> EvidenceScopeAssessment:
    values = base.model_dump(mode="python")
    values.update(updates)
    return EvidenceScopeAssessment.model_validate(values)


def make_rr(
    claim: ClaimRecord,
    evidence: EvidenceRecord,
) -> EvidenceEvaluationRR:
    return EvidenceEvaluationRR(
        evaluation_id="task55-fixture-evaluation",
        claim=claim,
        evidence=(evidence,),
        retrieval_status=RetrievalStatus.COMPLETED_WITH_RESULTS,
        assessment=ClaimAssessment(
            claim_id=claim.claim_id,
            status=AssessmentStatus.NOT_ASSESSED,
        ),
    )


def test_scope_unverified_evaluator_result_has_provenance_but_no_directional_trust() -> None:
    import app.evidence.trust as trust
    from app.evidence.trust import _is_evaluator_result

    result, _ = evaluate()
    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship is not None
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert _is_evaluator_result(result)
    assert not result.scope_assessment.is_verified_compatible()
    assert not trust._evaluator_results.add(result)
    assert not hasattr(trust, "_authorize_evaluator_result")


@pytest.mark.parametrize(
    ("nli_class", "expected_label"),
    [
        (NLIClass.ENTAILMENT, EvidenceRelationshipLabel.SUPPORTS),
        (NLIClass.CONTRADICTION, EvidenceRelationshipLabel.REFUTES),
        (NLIClass.NEUTRAL, EvidenceRelationshipLabel.NEUTRAL),
    ],
)
def test_explicit_nli_class_mapping(nli_class, expected_label) -> None:
    result, backend = evaluate(
        nli_class,
        scope_assessment=matching_scope_assessment(),
    )

    assert result.relationship is not None
    assert result.relationship.label != EvidenceRelationshipLabel.CONTRADICTS
    assert result.raw_nli_scores is not None
    assert backend.received == (PASSAGE, CLAIM_TEXT)
    assert result.calibration_status == "NOT_EVALUATED"
    assert result.scope_assessment.temporal.status == ScopeMatchStatus.MATCH
    if expected_label in {
        EvidenceRelationshipLabel.SUPPORTS,
        EvidenceRelationshipLabel.REFUTES,
    }:
        assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
        assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    else:
        assert result.inference_status == EvaluationStatus.COMPLETED
        assert result.relationship.label == expected_label


@pytest.mark.parametrize(
    ("case_name", "claim"),
    [
        ("negation", make_claim(original_text="The fictional council did not record 12 markers.")),
        ("numerical mismatch", make_claim(quantities=(ClaimQuantity(value="13", unit="test markers"),))),
        ("unit mismatch", make_claim(quantities=(ClaimQuantity(value="12", unit="kilograms"),))),
        ("temporal mismatch", make_claim(temporal_scope=None)),
        ("geographic mismatch", make_claim(geographic_scope=ClaimGeographicScope(place="Other district"))),
        ("population mismatch", make_claim(population_scope="another population")),
        ("attribution mismatch", make_claim(attribution=ClaimAttribution(speaker="another speaker"))),
        ("entity mismatch", make_claim(entities=(ClaimEntity(mention="another council"),))),
    ],
)
def test_scope_and_context_cases_remain_explicitly_unassessed(case_name, claim) -> None:
    result, _ = evaluate(NLIClass.NEUTRAL, claim=claim)

    assert case_name
    assert result.relationship is not None
    assert result.relationship.label == EvidenceRelationshipLabel.NEUTRAL
    assert all(
        value.status == ScopeMatchStatus.NOT_ASSESSED
        for value in (
            result.scope_assessment.entity,
            result.scope_assessment.temporal,
            result.scope_assessment.geographic,
            result.scope_assessment.population,
        )
    )
    assert "not independently verified" in result.relationship.scope_comparison.rationale


def test_claim_and_evidence_preprocessing_preserves_negation_and_original_sources() -> None:
    negated = make_claim(original_text="  The council did NOT record 12 markers.  ")
    backend = FixtureNLIBackend(NLIClass.NEUTRAL)
    result, _ = evaluate(claim=negated, backend=backend)

    assert backend.received == (PASSAGE, "The council did NOT record 12 markers.")
    assert negated.original_text.startswith("  ")
    assert result.relationship.label == EvidenceRelationshipLabel.NEUTRAL


def test_matching_annotations_do_not_authorize_directional_mapping() -> None:
    claim = make_claim()
    result, _ = evaluate(
        NLIClass.ENTAILMENT,
        claim=claim,
        scope_assessment=matching_scope_assessment(claim),
    )

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.quantity.status == ScopeMatchStatus.MATCH
    assert result.scope_assessment.verification_state == ScopeVerificationState.UNVERIFIED


@pytest.mark.parametrize(
    ("nli_class", "expected_status"),
    [
        (NLIClass.ENTAILMENT, EvaluationStatus.SCOPE_UNASSESSED),
        (NLIClass.CONTRADICTION, EvaluationStatus.SCOPE_UNASSESSED),
    ],
)
def test_quantity_13_vs_12_blocks_directional_relationship(nli_class, expected_status) -> None:
    claim = make_claim(
        original_text=CLAIM_TEXT.replace("12", "13"),
        quantities=(ClaimQuantity(value="13", unit="test markers"),),
    )
    assessment = scope_with(
        matching_scope_assessment(claim),
        quantity=scope_item(
            ScopeMatchStatus.MISMATCH,
            "13",
            "12",
            "12",
        ),
    )

    result, _ = evaluate(
        nli_class,
        claim=claim,
        scope_assessment=assessment,
    )

    assert result.inference_status == expected_status
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.quantity.status == ScopeMatchStatus.MISMATCH
    assert result.raw_nli_scores is not None


@pytest.mark.parametrize(
    ("dimension", "claim", "claim_value", "evidence_value", "basis"),
    [
        (
            "unit",
            make_claim(
                quantities=(ClaimQuantity(value="12", unit="kilograms"),),
            ),
            "kilograms",
            "test markers",
            "test markers",
        ),
        (
            "temporal",
            make_claim(
                original_text=CLAIM_TEXT.replace("2024", "2023"),
                temporal_scope=ClaimTemporalScope(reference_text="2023"),
            ),
            json.dumps(
                {
                    "as_of": None,
                    "reference_text": "2023",
                    "end": None,
                    "start": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "as_of": None,
                    "reference_text": "2024",
                    "end": None,
                    "start": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            "in 2024",
        ),
        (
            "population",
            make_claim(
                population_scope="adults",
                original_text=CLAIM_TEXT.replace(
                    "recorded", "recorded for adults"
                ),
            ),
            "adults",
            "all residents",
            "all residents",
        ),
        (
            "geographic",
            make_claim(
                geographic_scope=ClaimGeographicScope(place="Other district"),
                original_text=CLAIM_TEXT.replace(
                    "fictional Alder district", "Other district"
                ),
            ),
            "Other district",
            "fictional Alder district",
            "fictional Alder district",
        ),
        (
            "attribution",
            make_claim(
                attribution=ClaimAttribution(
                    speaker="Another council",
                    reporting_action="recorded",
                ),
                original_text=CLAIM_TEXT.replace(
                    "fictional Alder council", "Another council", 1
                ),
            ),
            "Another council recorded",
            "fictional Alder council",
            "fictional Alder council",
        ),
        (
            "entity",
            make_claim(
                entities=(ClaimEntity(mention="Another council"),),
                original_text=CLAIM_TEXT.replace(
                    "fictional Alder council", "Another council", 1
                ),
            ),
            "Another council",
            "fictional Alder council",
            "fictional Alder council",
        ),
        (
            "polarity",
            make_claim(
                original_text=CLAIM_TEXT.replace(
                    "recorded", "did not record"
                ),
                relations=(
                    ClaimRelation(
                        subject="fictional Alder council",
                        predicate="recorded",
                        object="12 test markers",
                        polarity="negative",
                    ),
                ),
            ),
            "negative",
            "affirmative",
            "fictional Alder council recorded 12 test markers",
        ),
    ],
)
def test_material_scope_mismatches_are_recorded_and_gate_nli_direction(
    dimension,
    claim,
    claim_value,
    evidence_value,
    basis,
) -> None:
    assessment = scope_with(
        matching_scope_assessment(claim),
        **{
            dimension: scope_item(
                ScopeMatchStatus.MISMATCH,
                claim_value,
                evidence_value,
                basis,
            )
        },
    )

    result, _ = evaluate(
        NLIClass.ENTAILMENT,
        claim=claim,
        scope_assessment=assessment,
    )

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert getattr(result.scope_assessment, dimension).status == ScopeMatchStatus.MISMATCH


def test_unassessed_scope_blocks_directional_output_without_inventing_a_mismatch() -> None:
    result, _ = evaluate(NLIClass.ENTAILMENT)

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.quantity.status == ScopeMatchStatus.NOT_ASSESSED
    assert "independently verified" in result.failure_detail


def test_task55c_forged_match_cannot_authorize_13_vs_12_direction() -> None:
    claim = make_claim(
        original_text=CLAIM_TEXT.replace("12", "13"),
        quantities=(ClaimQuantity(value="13", unit="test markers"),),
    )
    forged_match = scope_with(
        matching_scope_assessment(claim),
        quantity=scope_item(
            ScopeMatchStatus.MATCH,
            "13",
            "13",
            "12",
        ),
    )

    result, _ = evaluate(
        NLIClass.ENTAILMENT,
        claim=claim,
        scope_assessment=forged_match,
    )

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.quantity.status == ScopeMatchStatus.MATCH
    assert result.scope_assessment.verification_state == ScopeVerificationState.UNVERIFIED


def test_task55c_forged_not_applicable_cannot_bypass_text_scope() -> None:
    claim = make_claim(
        entities=None,
        quantities=None,
        temporal_scope=None,
        geographic_scope=None,
        attribution=None,
        relations=None,
        population_scope=None,
    )
    not_applicable = scope_item(
        ScopeMatchStatus.NOT_APPLICABLE,
        evidence_basis="caller assertion",
    )
    forged_assessment = EvidenceScopeAssessment(
        **{
            dimension: not_applicable
            for dimension in (
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
        }
    )

    result, _ = evaluate(
        NLIClass.ENTAILMENT,
        claim=claim,
        scope_assessment=forged_assessment,
    )

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.verification_state == ScopeVerificationState.UNVERIFIED


@pytest.mark.parametrize(
    "dimension",
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
)
def test_unresolved_scope_dimension_blocks_directional_output(dimension) -> None:
    assessment = scope_with(
        matching_scope_assessment(),
        **{dimension: ScopeDimensionAssessment()},
    )

    result, _ = evaluate(scope_assessment=assessment)

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT


def test_conditional_scope_mismatch_is_not_treated_as_verified() -> None:
    claim = make_claim(
        original_text=CLAIM_TEXT + " if inspected.",
        relations=(
            ClaimRelation(
                subject="fictional Alder council",
                predicate="recorded",
                object="12 test markers",
                polarity="affirmative",
                condition="if inspected",
            ),
        ),
    )
    evidence = make_evidence(passage=PASSAGE + " if inspected.")
    assessment = scope_with(
        matching_scope_assessment(claim),
        conditional=scope_item(
            ScopeMatchStatus.MISMATCH,
            "if inspected",
            "unconditional",
            "if inspected",
        ),
    )

    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=assessment,
    )

    assert result.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.scope_assessment.conditional.status == ScopeMatchStatus.MISMATCH


def test_scope_state_cannot_be_forged_through_validation_copy_or_json() -> None:
    assessment = matching_scope_assessment()
    assert assessment.verification_state == ScopeVerificationState.UNVERIFIED
    assert EvidenceScopeAssessment.model_validate_json(
        assessment.model_dump_json()
    ).verification_state == ScopeVerificationState.UNVERIFIED
    with pytest.raises(ValidationError, match="scope verification is unavailable"):
        EvidenceScopeAssessment.model_validate_json(
            '{"verification_state":"VERIFIED_COMPATIBLE"}'
        )
    with pytest.raises(ValidationError, match="scope verification is unavailable"):
        EvidenceScopeAssessment.model_validate_json(
            '{"verification_state":"UNVERIFIED",'
            '"verification_state":"VERIFIED_COMPATIBLE"}'
        )
    duplicate_state = EvidenceScopeAssessment.model_validate_json(
        '{"verification_state":"VERIFIED_COMPATIBLE",'
        '"verification_state":"UNVERIFIED"}'
    )
    assert duplicate_state.verification_state == ScopeVerificationState.UNVERIFIED

    with pytest.raises(ValidationError, match="scope verification is unavailable"):
        EvidenceScopeAssessment(
            verification_state=ScopeVerificationState.VERIFIED_COMPATIBLE
        )

    copied = assessment.model_copy(
        update={"verification_state": ScopeVerificationState.VERIFIED_COMPATIBLE}
    )
    with pytest.raises(ValidationError, match="scope verification is unavailable"):
        evaluate(scope_assessment=copied)

    constructed = EvidenceScopeAssessment.model_construct(
        verification_state=ScopeVerificationState.VERIFIED_COMPATIBLE
    )
    with pytest.raises(ValidationError, match="scope verification is unavailable"):
        evaluate(scope_assessment=constructed)

    constructed_dimension = ScopeDimensionAssessment.model_construct(
        status=ScopeMatchStatus.MATCH,
        claim_value="13",
        evidence_value="12",
        evidence_basis="12",
    )
    nested_constructed = EvidenceScopeAssessment.model_construct(
        quantity=constructed_dimension
    )
    with pytest.raises(ValidationError):
        evaluate(scope_assessment=nested_constructed)


def test_scope_annotations_reject_conflicts_and_unknown_dimensions() -> None:
    with pytest.raises(ValidationError, match="MISMATCH requires different"):
        scope_item(ScopeMatchStatus.MISMATCH, "12", "12", "12")
    with pytest.raises(ValidationError, match="extra"):
        EvidenceScopeAssessment.model_validate(
            {"unknown_dimension": scope_item(ScopeMatchStatus.NOT_ASSESSED)}
        )


def test_scope_annotations_must_bind_to_claim_values_and_exact_passage_basis() -> None:
    claim = make_claim()
    false_claim_value = scope_with(
        matching_scope_assessment(claim),
        quantity=scope_item(
            ScopeMatchStatus.MISMATCH,
            "99",
            "12",
            "12",
        ),
    )
    with pytest.raises(ValueError, match="claim_value"):
        evaluate(NLIClass.ENTAILMENT, claim=claim, scope_assessment=false_claim_value)

    false_passage_basis = scope_with(
        matching_scope_assessment(claim),
        quantity=scope_item(
            ScopeMatchStatus.MATCH,
            "12",
            "12",
            "invented quote",
        ),
    )
    with pytest.raises(ValueError, match="exact passage excerpt"):
        evaluate(NLIClass.ENTAILMENT, claim=claim, scope_assessment=false_passage_basis)


def test_not_applicable_cannot_hide_a_known_structured_scope_value() -> None:
    claim = make_claim()
    forged_scope = scope_with(
        matching_scope_assessment(claim),
        quantity=scope_item(
            ScopeMatchStatus.NOT_APPLICABLE,
            evidence_basis="Quantity omitted by caller.",
        ),
    )

    with pytest.raises(ValueError, match="structured claim values exist"):
        evaluate(NLIClass.ENTAILMENT, claim=claim, scope_assessment=forged_scope)


def test_multiple_structured_quantities_cannot_be_partially_declared_compatible() -> None:
    claim = make_claim(
        quantities=(
            ClaimQuantity(value="12", unit="test markers"),
            ClaimQuantity(value="3", unit="test categories"),
        ),
    )
    assessment = matching_scope_assessment(claim)

    with pytest.raises(ValueError, match="single structured claim value"):
        evaluate(
            NLIClass.ENTAILMENT,
            claim=claim,
            scope_assessment=assessment,
        )


def test_compound_claim_requires_a_selected_recorded_atomic_proposition() -> None:
    compound = make_claim(
        atomicity=ClaimAtomicity.COMPOUND,
        atomic_claims=(
            {"atomic_claim_id": "atom-1", "text": "The council recorded 12 markers."},
            {"atomic_claim_id": "atom-2", "text": "It happened in 2024."},
        ),
    )
    unsupported, _ = evaluate(claim=compound)
    assert unsupported.inference_status == EvaluationStatus.UNSUPPORTED_CLAIM
    assert unsupported.relationship is None

    selected, _ = evaluate(
        claim=compound,
        atomic_claim_id="atom-1",
        scope_assessment=matching_scope_assessment(compound),
    )
    assert selected.inference_status == EvaluationStatus.SCOPE_UNASSESSED
    assert selected.atomic_proposition_id == "atom-1"
    assert selected.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert selected.relationship.atomic_claim_id == "atom-1"


@pytest.mark.parametrize(
    "atomicity",
    [ClaimAtomicity.AMBIGUOUS, ClaimAtomicity.NOT_ASSESSED],
)
def test_ambiguous_or_unassessed_claim_is_not_sent_to_nli(atomicity) -> None:
    backend = FixtureNLIBackend()
    result, _ = evaluate(
        claim=make_claim(atomicity=atomicity),
        backend=backend,
    )

    assert result.inference_status == EvaluationStatus.UNSUPPORTED_CLAIM
    assert result.relationship is None
    assert result.atomic_proposition_id is None
    assert backend.received is None


def test_missing_evidence_passage_maps_only_to_insufficient_context() -> None:
    evidence = make_evidence(
        passage=None,
        extraction_status=ExtractionStatus.MISSING_PASSAGE,
    )
    result, backend = evaluate(evidence=evidence)

    assert result.inference_status == EvaluationStatus.MISSING_EVIDENCE_PASSAGE
    assert result.relationship.label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT
    assert result.raw_nli_scores is None
    assert backend.received is None


def test_unavailable_model_fails_closed_without_scores_or_relationship() -> None:
    result = EvidenceRelationshipEvaluator().evaluate(
        make_claim(),
        make_evidence(),
        language="en",
    )

    assert result.inference_status == EvaluationStatus.MODEL_UNAVAILABLE
    assert result.relationship is None
    assert result.model_identity is None
    assert result.raw_nli_scores is None
    assert UnavailableNLIBackend().infer("premise", "hypothesis").status == InferenceStatus.MODEL_UNAVAILABLE


def test_language_must_be_declared_and_supported() -> None:
    unspecified, unspecified_backend = evaluate(language=None)
    unsupported, unsupported_backend = evaluate(language="fr")

    assert unspecified.inference_status == EvaluationStatus.LANGUAGE_UNSPECIFIED
    assert unspecified_backend.received is None
    assert unsupported.inference_status == EvaluationStatus.UNSUPPORTED_LANGUAGE
    assert unsupported_backend.received is None


def test_inference_failure_is_explicit_and_never_fabricates_a_relation() -> None:
    backend = FixtureNLIBackend(failure=RuntimeError("fixture inference failure"))
    result, _ = evaluate(backend=backend)

    assert result.inference_status == EvaluationStatus.INFERENCE_FAILED
    assert result.failure_detail == "RuntimeError: fixture inference failure"
    assert result.relationship is None
    assert result.raw_nli_scores is None


def test_model_loading_failure_is_distinct_from_unavailable_and_inference_failure() -> None:
    backend = FixtureNLIBackend(failure=ModelLoadError("configured-nli", "load failed"))
    load_failed, _ = evaluate(backend=backend)

    inference_failed, _ = evaluate(
        backend=FixtureNLIBackend(failure=RuntimeError("inference failed"))
    )
    explicitly_unavailable, _ = evaluate(backend=UnavailableNLIBackend())

    assert load_failed.inference_status == EvaluationStatus.MODEL_LOAD_FAILED
    assert load_failed.model_identity == "configured-nli"
    assert load_failed.relationship is None
    assert inference_failed.inference_status == EvaluationStatus.INFERENCE_FAILED
    assert inference_failed.model_identity == "test-only-fixture-nli"
    assert inference_failed.relationship is None
    assert explicitly_unavailable.inference_status == EvaluationStatus.MODEL_UNAVAILABLE


def test_backend_reported_load_failure_has_no_directional_relationship() -> None:
    class LoadFailingBackend(FixtureNLIBackend):
        def infer(self, premise: str, hypothesis: str) -> NLIInference:
            del premise, hypothesis
            return NLIInference(
                status=InferenceStatus.MODEL_LOAD_FAILED,
                model_identity="configured-local-model",
                detail="Local weights could not be loaded.",
            )

    result, _ = evaluate(backend=LoadFailingBackend())

    assert result.inference_status == EvaluationStatus.MODEL_LOAD_FAILED
    assert result.model_identity == "configured-local-model"
    assert result.relationship is None


def test_invalid_backend_output_fails_closed() -> None:
    class InvalidOutputBackend(FixtureNLIBackend):
        def infer(self, premise: str, hypothesis: str):
            del premise, hypothesis
            return {
                "status": "INFERENCE_SUCCEEDED",
                "model_identity": self.model_identity,
                "model_version": self.model_version,
                "scores": [{"label": "unknown", "value": 0.8}],
                "score_kind": "logits",
            }

    result, _ = evaluate(backend=InvalidOutputBackend())

    assert result.inference_status == EvaluationStatus.INFERENCE_FAILED
    assert result.relationship is None
    assert result.raw_nli_scores is None


def test_tied_nli_scores_do_not_create_a_relationship() -> None:
    result, _ = evaluate(backend=FixtureNLIBackend(tie=True))

    assert result.inference_status == EvaluationStatus.AMBIGUOUS_MODEL_OUTPUT
    assert result.relationship is None
    assert result.raw_nli_scores is not None


def test_nli_schema_rejects_missing_classes_invalid_probabilities_and_failure_scores() -> None:
    with pytest.raises(ValidationError, match="all three"):
        NLIInference(
            status=InferenceStatus.COMPLETED,
            model_identity="fixture",
            model_version="v1",
            scores=(NLIScore(label=NLIClass.NEUTRAL, value=0.5),),
            score_kind=NLIScoreKind.PROBABILITIES,
        )
    with pytest.raises(ValidationError, match="sum to 1"):
        NLIInference(
            status=InferenceStatus.COMPLETED,
            model_identity="fixture",
            model_version="v1",
            scores=(
                NLIScore(label=NLIClass.ENTAILMENT, value=0.2),
                NLIScore(label=NLIClass.CONTRADICTION, value=0.2),
                NLIScore(label=NLIClass.NEUTRAL, value=0.2),
            ),
            score_kind=NLIScoreKind.PROBABILITIES,
        )
    with pytest.raises(ValidationError, match="cannot carry class scores"):
        NLIInference(
            status=InferenceStatus.INFERENCE_FAILED,
            scores=(
                NLIScore(label=NLIClass.NEUTRAL, value=1.0),
            ),
            detail="fixture failure",
        )


def test_model_specific_decoder_uses_configured_label_order_and_preserves_scores() -> None:
    decoder = NLIClassDecoder.from_model_config(
        {
            "num_labels": 3,
            "id2label": {
                0: "neutral",
                1: "entailment",
                2: "contradiction",
            },
            "label2id": {
                "neutral": 0,
                "entailment": 1,
                "contradiction": 2,
            },
        },
        output_dimensions=3,
    )

    decoded = decoder.decode(
        (0.25, 0.63, 0.12),
        score_kind=NLIScoreKind.LOGITS,
    )
    assert tuple(score.label for score in decoded) == (
        NLIClass.NEUTRAL,
        NLIClass.ENTAILMENT,
        NLIClass.CONTRADICTION,
    )
    assert tuple(score.value for score in decoded) == (0.25, 0.63, 0.12)


def test_model_specific_decoder_accepts_label2id_without_assuming_indices() -> None:
    decoder = NLIClassDecoder.from_model_config(
        {
            "num_labels": 3,
            "label2id": {
                "contradiction": 0,
                "neutral": 1,
                "entailment": 2,
            },
        },
        output_dimensions=3,
    )

    decoded = decoder.decode(
        (0.2, 0.3, 0.5),
        score_kind=NLIScoreKind.LOGITS,
    )
    assert {score.label: score.value for score in decoded} == {
        NLIClass.CONTRADICTION: 0.2,
        NLIClass.NEUTRAL: 0.3,
        NLIClass.ENTAILMENT: 0.5,
    }


@pytest.mark.parametrize(
    "configuration",
    [
        {"num_labels": 3},
        {"num_labels": 3, "id2label": {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}},
        {"num_labels": 3, "id2label": {0: "entailment", 1: "entailment", 2: "neutral"}},
        {"num_labels": 3, "id2label": {0: "entailment", 1: "neutral"}},
        {
            "num_labels": 3,
            "id2label": {0: "entailment", 1: "neutral", 2: "contradiction"},
            "label2id": {"entailment": 0, "neutral": 2, "contradiction": 1},
        },
        {
            "num_labels": 4,
            "id2label": {
                0: "entailment",
                1: "neutral",
                2: "contradiction",
                3: "other",
            },
        },
    ],
)
def test_model_specific_decoder_rejects_missing_unknown_duplicate_or_inconsistent_labels(
    configuration,
) -> None:
    with pytest.raises(ValueError):
        NLIClassDecoder.from_model_config(
            configuration,
            output_dimensions=3,
        )


def test_model_specific_decoder_rejects_incomplete_configuration_and_bad_outputs() -> None:
    configuration = {
        "num_labels": 3,
        "id2label": {0: "neutral", 1: "contradiction", 2: "entailment"},
    }
    with pytest.raises(ValueError, match="exactly three"):
        NLIClassDecoder.from_model_config(configuration, output_dimensions=2)

    decoder = NLIClassDecoder.from_model_config(configuration, output_dimensions=3)
    with pytest.raises(ValueError, match="output dimension"):
        decoder.decode((0.2, 0.8), score_kind=NLIScoreKind.LOGITS)
    with pytest.raises((ValueError, ValidationError)):
        decoder.decode((float("nan"), 0.2, 0.8), score_kind=NLIScoreKind.LOGITS)
    with pytest.raises(ValueError, match="sum to 1"):
        decoder.decode(
            (0.2, 0.2, 0.2),
            score_kind=NLIScoreKind.PROBABILITIES,
        )
    with pytest.raises(ValueError, match="incomplete"):
        NLIClassDecoder(
            {
                0: NLIClass.ENTAILMENT,
                1: NLIClass.CONTRADICTION,
            }
        )


def test_evaluation_serialization_and_rr_integration_revalidate() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored == result
    rr = EvidenceEvaluationRR(
        evaluation_id="task55-fixture-evaluation",
        claim=claim,
        evidence=(evidence,),
        retrieval_status=RetrievalStatus.COMPLETED_WITH_RESULTS,
        assessment=ClaimAssessment(
            claim_id=claim.claim_id,
            status=AssessmentStatus.NOT_ASSESSED,
        ),
    )

    with pytest.raises(ValueError, match="caller-created evaluation results"):
        attach_relationship_to_rr(rr, restored)

    updated = attach_relationship_to_rr(rr, result)
    assert updated.relationships[-1] == result.relationship
    assert updated.assessment.verdict is None
    assert updated.model_validate_json(updated.model_dump_json()) == updated
    context = build_cmrea_evidence_context(updated)
    assert context.relationships[-1].label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT


def test_caller_created_nondirectional_result_cannot_enter_any_rr(monkeypatch) -> None:
    import app.evidence.trust as trust

    claim = make_claim()
    evidence = make_evidence()
    assert evidence.extracted_passage is not None
    actual, _ = evaluate(
        NLIClass.NEUTRAL,
        claim=claim,
        evidence=evidence,
    )
    forged = type(actual).model_validate(actual.model_dump(mode="python"))
    assert forged.relationship is not None
    assert forged.relationship.label == EvidenceRelationshipLabel.NEUTRAL
    assert not trust._is_evaluator_result(forged)

    with pytest.raises(ValueError, match="caller-created evaluation results"):
        attach_relationship_to_rr(make_rr(claim, evidence), forged)

    source_registry = trust._IdentityRegistry()
    monkeypatch.setattr(
        trust,
        "_authorized_reasoning_representations",
        source_registry,
    )
    directional_source = EvidenceEvaluationRR(
        evaluation_id="test-only-authorized-directional-source",
        claim=claim,
        evidence=(evidence,),
        relationships=(
            EvidenceRelationship(
                relationship_id="test-only-source-relationship",
                claim_id=claim.claim_id,
                evidence_id=evidence.evidence_id,
                label=EvidenceRelationshipLabel.SUPPORTS,
                rationale="Test-only authorized source for adapter boundary coverage.",
                supporting_span=EvidenceSpan(
                    start_char=0,
                    end_char=len(evidence.extracted_passage),
                    exact_text=evidence.extracted_passage,
                ),
            ),
        ),
        retrieval_status=RetrievalStatus.COMPLETED_WITH_RESULTS,
        assessment=ClaimAssessment(
            claim_id=claim.claim_id,
            status=AssessmentStatus.NOT_ASSESSED,
        ),
    )
    assert source_registry.add(directional_source)

    with pytest.raises(ValueError, match="caller-created evaluation results"):
        attach_relationship_to_rr(directional_source, forged)


def test_forged_directional_evaluation_cannot_pass_copy_or_model_construct_boundaries() -> None:
    claim = make_claim()
    evidence = make_evidence()
    neutral_result, _ = evaluate(
        NLIClass.NEUTRAL,
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    json_payload = neutral_result.model_dump(mode="json")
    json_payload["relationship"]["label"] = EvidenceRelationshipLabel.SUPPORTS.value
    json_payload["raw_nli_scores"] = [
        {"label": NLIClass.ENTAILMENT.value, "value": 0.8},
        {"label": NLIClass.CONTRADICTION.value, "value": 0.1},
        {"label": NLIClass.NEUTRAL.value, "value": 0.1},
    ]
    with pytest.raises(ValidationError, match="independently verified compatible scope"):
        type(neutral_result).model_validate_json(json.dumps(json_payload))

    forged_payload = neutral_result.model_dump(mode="python")
    forged_payload["relationship"] = neutral_result.relationship.model_copy(
        update={"label": EvidenceRelationshipLabel.SUPPORTS}
    )
    forged_payload["raw_nli_scores"] = (
        NLIScore(label=NLIClass.ENTAILMENT, value=0.8),
        NLIScore(label=NLIClass.CONTRADICTION, value=0.1),
        NLIScore(label=NLIClass.NEUTRAL, value=0.1),
    )
    forged = type(neutral_result).model_construct(**forged_payload)
    from app.evidence.trust import _evaluator_results

    assert not _evaluator_results.record_evaluator_execution(forged)

    with pytest.raises(ValidationError, match="independently verified compatible scope"):
        attach_relationship_to_rr(make_rr(claim, evidence), forged)


def test_evaluator_adapter_rejects_direct_caller_directional_rr() -> None:
    claim = make_claim()
    evidence = make_evidence()
    existing = make_rr(claim, evidence)
    payload = existing.model_dump(mode="python")
    payload["relationships"] = (
        EvidenceRelationship(
            relationship_id="caller-authored-direction",
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            label=EvidenceRelationshipLabel.SUPPORTS,
            rationale="Caller-authored assertion.",
            supporting_span=EvidenceSpan(
                start_char=0,
                end_char=len(evidence.extracted_passage),
                exact_text=evidence.extracted_passage,
            ),
        ),
    )
    forged_rr = EvidenceEvaluationRR.model_validate(payload)
    evaluation, _ = evaluate(
        NLIClass.NEUTRAL,
        claim=claim,
        evidence=evidence,
    )

    with pytest.raises(ValueError, match="untrusted directional RR content"):
        attach_relationship_to_rr(forged_rr, evaluation)


def test_rr_integration_rejects_mismatched_claim_or_evidence() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    different_claim = make_claim(claim_id="other-claim")
    rr = EvidenceEvaluationRR(
        evaluation_id="task55-fixture-evaluation",
        claim=different_claim,
        evidence=(evidence,),
        retrieval_status=RetrievalStatus.COMPLETED_WITH_RESULTS,
        assessment=ClaimAssessment(
            claim_id=different_claim.claim_id,
            status=AssessmentStatus.NOT_ASSESSED,
        ),
    )

    with pytest.raises(ValueError, match="claim_id"):
        attach_relationship_to_rr(rr, result)


def test_rr_attachment_rejects_same_id_with_changed_passage() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    changed = evidence.model_copy(
        update={"extracted_passage": PASSAGE + " Revised wording."}
    )

    with pytest.raises(ValueError, match="record or provenance"):
        attach_relationship_to_rr(make_rr(claim, changed), result)


def test_rr_attachment_rejects_missing_evaluation_record_fingerprint() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    payload = result.model_dump(mode="python")
    del payload["evidence_record_sha256"]

    with pytest.raises(ValidationError, match="evidence_record_sha256"):
        type(result).model_validate(payload)


def test_missing_passage_evaluation_attaches_only_to_same_missing_record() -> None:
    claim = make_claim()
    missing = make_evidence(
        passage=None,
        extraction_status=ExtractionStatus.MISSING_PASSAGE,
    )
    result, _ = evaluate(claim=claim, evidence=missing)

    attached = attach_relationship_to_rr(make_rr(claim, missing), result)
    assert attached.relationships[-1].label == EvidenceRelationshipLabel.INSUFFICIENT_CONTEXT

    available = make_evidence()
    with pytest.raises(ValueError, match="extraction status|record or provenance"):
        attach_relationship_to_rr(make_rr(claim, available), result)


def test_rr_attachment_rejects_changed_extraction_status() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    partial = evidence.model_copy(
        update={"extraction_status": ExtractionStatus.PARTIAL}
    )

    with pytest.raises(ValueError, match="extraction status|record or provenance"):
        attach_relationship_to_rr(make_rr(claim, partial), result)


def test_rr_attachment_rejects_same_passage_with_changed_provenance() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    changed_provenance = evidence.provenance.model_copy(
        update={"document_reference": "different-document-version"}
    )
    changed = evidence.model_copy(update={"provenance": changed_provenance})

    with pytest.raises(ValueError, match="record or provenance"):
        attach_relationship_to_rr(make_rr(claim, changed), result)


def test_rr_construction_rejects_invalid_evidence_record() -> None:
    claim = make_claim()
    invalid_evidence = make_evidence().model_dump(mode="python")
    invalid_evidence["extracted_passage"] = None
    with pytest.raises(ValidationError, match="AVAILABLE extraction_status"):
        EvidenceEvaluationRR.model_validate(
            {
                "evaluation_id": "invalid-evidence-fixture",
                "claim": claim,
                "evidence": (invalid_evidence,),
                "retrieval_status": RetrievalStatus.COMPLETED_WITH_RESULTS,
                "assessment": ClaimAssessment(
                    claim_id=claim.claim_id,
                    status=AssessmentStatus.NOT_ASSESSED,
                ),
            }
        )


def test_rr_attachment_rejects_caller_reconstructed_scope_assertion() -> None:
    claim = make_claim()
    evidence = make_evidence()
    result, _ = evaluate(
        claim=claim,
        evidence=evidence,
        scope_assessment=matching_scope_assessment(claim),
    )
    forged_scope = scope_with(
        result.scope_assessment,
        quantity=scope_item(
            ScopeMatchStatus.MATCH,
            "13",
            "13",
            "12",
        ),
    )
    forged_payload = result.model_dump(mode="python")
    forged_payload["scope_assessment"] = forged_scope
    # Keep relationship metadata aligned so the scope annotation is internally
    # consistent, but it no longer has evaluator-issued object provenance.
    forged_payload["relationship"] = result.relationship.model_copy(
        update={"scope_comparison": forged_scope.to_contract_comparison()}
    )
    forged = type(result).model_validate(forged_payload)

    with pytest.raises(ValueError, match="caller-created evaluation results"):
        attach_relationship_to_rr(make_rr(claim, evidence), forged)


def test_no_local_model_inference_is_claimed_by_fixture_tests() -> None:
    result = EvidenceRelationshipEvaluator().evaluate(
        make_claim(),
        make_evidence(),
        language="en",
    )

    assert result.inference_status == EvaluationStatus.MODEL_UNAVAILABLE
    assert result.model_identity is None
