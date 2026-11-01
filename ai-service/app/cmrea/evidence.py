"""Traceable CMREA input derived from an already validated evidence RR."""

from copy import deepcopy
import json
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from app.evidence.schemas import (
    ClaimAssessment,
    ClaimModality,
    ClaimRecord,
    EvidenceRecord,
    EvidenceRelationship,
    RetrievalStatus,
)
from app.rr.evidence import EvidenceEvaluationRR
from app.rr.models import RRModel
from app.evidence.trust import (
    _authorize_cmrea_context,
    _contains_directional_content,
    _cmrea_context_snapshot,
    _is_registered_cmrea_context,
    _issue_cmrea_capability,
)


class CMREAEvidenceContext(RRModel):
    """Source records CMREA may explain without adding factual assertions."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    evaluation_id: str
    claim: ClaimRecord
    evidence: Tuple[EvidenceRecord, ...] = Field(default_factory=tuple)
    retrieval_status: RetrievalStatus
    relationships: Tuple[EvidenceRelationship, ...] = Field(default_factory=tuple)
    assessment: ClaimAssessment
    supported_modalities: Optional[Tuple[ClaimModality, ...]] = None
    explanation_constraints: Tuple[str, ...] = Field(
        default_factory=lambda: (
            "Use only the original claim and supplied structured records.",
            "Tie each evidence statement to an evidence_id and recorded passage.",
            "Do not upgrade a relationship annotation into a broader claim.",
            "State processing states and abstention reasons without calling them verdicts.",
            "Do not invent sources, dates, passages, or reliability assessments.",
        )
    )

    def __getattribute__(self, name: str) -> Any:
        """Read authorized fields from a detached copy of their stored snapshot."""
        model_fields = object.__getattribute__(self, "__class__").model_fields
        if name in model_fields and _is_registered_cmrea_context(self):
            snapshot = _cmrea_context_snapshot(self)
            if snapshot is None:
                raise ValueError(
                    "authorized directional CMREA context was modified"
                )
            detached = _materialize_cmrea_snapshot(snapshot.payload_json)
            return object.__getattribute__(detached, name)
        return super().__getattribute__(name)

    def model_copy(
        self,
        *,
        update: Optional[Dict[str, Any]] = None,
        deep: bool = False,
    ) -> "CMREAEvidenceContext":
        data = self.model_dump(mode="python", round_trip=True)
        if deep:
            data = deepcopy(data)
        data.update(update or {})
        return self.__class__.model_validate(data)

    @classmethod
    def model_construct(
        cls, _fields_set: Optional[set[str]] = None, **values: Any
    ) -> "CMREAEvidenceContext":
        supplied_fields = len(values) + int(_fields_set is not None)
        raise TypeError(
            "model_construct() is disabled for evidence contracts; "
            f"use model_validate() instead ({supplied_fields} supplied fields)"
        )

    def model_dump(self, **kwargs: Any) -> Any:
        if _is_registered_cmrea_context(self):
            snapshot = _cmrea_context_snapshot(self)
            if snapshot is None:
                raise ValueError(
                    "authorized directional CMREA context was modified"
                )
            detached = _materialize_cmrea_snapshot(snapshot.payload_json)
            return BaseModel.model_dump(detached, **kwargs)
        if _contains_directional_content(self):
            raise ValueError(
                "untrusted directional CMREA context cannot be serialized"
            )
        self.__class__.model_validate(self)
        return BaseModel.model_dump(self, **kwargs)

    def model_dump_json(self, **kwargs: Any) -> str:
        if _is_registered_cmrea_context(self):
            snapshot = _cmrea_context_snapshot(self)
            if snapshot is None:
                raise ValueError(
                    "authorized directional CMREA context was modified"
                )
            detached = _materialize_cmrea_snapshot(snapshot.payload_json)
            return BaseModel.model_dump_json(detached, **kwargs)
        if _contains_directional_content(self):
            raise ValueError(
                "untrusted directional CMREA context cannot be serialized"
            )
        self.__class__.model_validate(self)
        return BaseModel.model_dump_json(self, **kwargs)

    @model_validator(mode="after")
    def validate_evidence_context(
        self,
        info: ValidationInfo,
    ) -> "CMREAEvidenceContext":
        EvidenceEvaluationRR.model_validate(
            {
                "evaluation_id": self.evaluation_id,
                "claim": self.claim,
                "evidence": self.evidence,
                "retrieval_status": self.retrieval_status,
                "relationships": self.relationships,
                "assessment": self.assessment,
                "supported_modalities": self.supported_modalities,
            }
        )
        if _contains_directional_content(self):
            if not _authorize_cmrea_context(self, info.context):
                raise ValueError(
                    "directional CMREA input requires evaluator-authorized RR provenance"
                )
        return self


def build_cmrea_evidence_context(
    reasoning_representation: EvidenceEvaluationRR,
) -> CMREAEvidenceContext:
    """Expose recorded claim/evidence relations to CMREA without generation."""

    validated_rr = EvidenceEvaluationRR.model_validate(reasoning_representation)
    has_directional_content = _contains_directional_content(validated_rr)
    capability = None
    if has_directional_content:
        issued = _issue_cmrea_capability(reasoning_representation)
        if issued is None:
            raise ValueError(
                "caller-created directional RR content cannot enter CMREA"
            )
        capability, snapshot = issued
        payload = json.loads(snapshot.payload_json)
    else:
        payload = BaseModel.model_dump(
            validated_rr,
            mode="python",
            round_trip=True,
        )
        payload = deepcopy(payload)
    if capability is None:
        return CMREAEvidenceContext(**payload)
    return CMREAEvidenceContext.model_validate(payload, context=capability)


def _materialize_cmrea_snapshot(payload_json: bytes) -> CMREAEvidenceContext:
    payload = json.loads(payload_json)
    payload["claim"] = ClaimRecord.model_validate(payload["claim"])
    payload["evidence"] = tuple(
        EvidenceRecord.model_validate(item) for item in payload["evidence"]
    )
    payload["retrieval_status"] = RetrievalStatus(payload["retrieval_status"])
    payload["relationships"] = tuple(
        EvidenceRelationship.model_validate(item)
        for item in payload["relationships"]
    )
    payload["assessment"] = ClaimAssessment.model_validate(
        payload["assessment"]
    )
    if payload["supported_modalities"] is not None:
        payload["supported_modalities"] = tuple(
            ClaimModality(item) for item in payload["supported_modalities"]
        )
    payload["explanation_constraints"] = tuple(
        payload["explanation_constraints"]
    )
    return BaseModel.model_construct.__func__(
        CMREAEvidenceContext,
        _fields_set=set(payload),
        **payload,
    )
