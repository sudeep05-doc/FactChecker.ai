"""In-process authorization for evaluator-produced directional evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import json
import math
from threading import RLock
from typing import Any, Mapping, Optional
from uuid import UUID
import weakref

from pydantic import AnyUrl, BaseModel


_DIRECTIONAL_LABELS = {
    "SUPPORTS",
    "REFUTES",
    "PARTIALLY_SUPPORTS",
    "PARTIALLY_REFUTES",
}
_RR_SEMANTIC_FIELDS = (
    "evaluation_id",
    "claim",
    "evidence",
    "retrieval_status",
    "relationships",
    "assessment",
    "supported_modalities",
)
_CMREA_EXPLANATION_CONSTRAINTS = (
    "Use only the original claim and supplied structured records.",
    "Tie each evidence statement to an evidence_id and recorded passage.",
    "Do not upgrade a relationship annotation into a broader claim.",
    "State processing states and abstention reasons without calling them verdicts.",
    "Do not invent sources, dates, passages, or reliability assessments.",
)
_REGISTRATION_AUTHORITY = object()


@dataclass(frozen=True)
class _ContentSnapshot:
    canonical_json: bytes
    payload_json: bytes
    semantic_json: bytes
    semantic_payload_json: bytes


class _IdentityRegistry:
    def __init__(self) -> None:
        self._items: dict[
            int, tuple[weakref.ReferenceType, Optional[_ContentSnapshot]]
        ] = {}
        self._lock = RLock()

    def _register_snapshot(
        self,
        item: object,
        *,
        authority: Optional[object] = None,
    ) -> bool:
        if (
            type(self) is not _IdentityRegistry
            and authority is not _REGISTRATION_AUTHORITY
        ):
            return False
        snapshot = _content_snapshot(item)
        identity = id(item)

        def discard(reference: weakref.ReferenceType) -> None:
            with self._lock:
                if self._items.get(identity, (None, None))[0] is reference:
                    self._items.pop(identity, None)

        try:
            reference = weakref.ref(item, discard)
        except TypeError:
            return False
        with self._lock:
            current = self._items.get(identity)
            if current is not None and current[0]() is item:
                if snapshot is None:
                    self._items[identity] = (current[0], None)
                    return False
                if (
                    current[1] is None
                    or current[1].canonical_json != snapshot.canonical_json
                    or current[1].payload_json != snapshot.payload_json
                ):
                    self._items[identity] = (current[0], None)
                    return False
                return True
            if snapshot is None:
                return False
            self._items[identity] = (reference, snapshot)
            return True

    def add(self, item: object) -> bool:
        return self._register_snapshot(item)

    def contains(self, item: object) -> bool:
        return self.snapshot_if_authorized(item) is not None

    def contains_entry(self, item: object) -> bool:
        with self._lock:
            entry = self._items.get(id(item))
            return entry is not None and entry[0]() is item

    def snapshot_if_authorized(
        self, item: object
    ) -> Optional[_ContentSnapshot]:
        identity = id(item)
        with self._lock:
            entry = self._items.get(identity)
            if entry is None or entry[0]() is not item:
                return None
        snapshot = _content_snapshot(item)
        with self._lock:
            entry = self._items.get(identity)
            if entry is None or entry[0]() is not item:
                return None
            if (
                snapshot is None
                or entry[1] is None
                or entry[1].canonical_json != snapshot.canonical_json
                or entry[1].payload_json != snapshot.payload_json
            ):
                self._items[identity] = (entry[0], None)
                return None
            return entry[1]

    def revoke(self, item: object) -> None:
        with self._lock:
            identity = id(item)
            entry = self._items.get(identity)
            if entry is not None and entry[0]() is item:
                self._items[identity] = (entry[0], None)


def _canonical_value(
    value: object,
    active_models: Optional[set[int]] = None,
) -> Any:
    active_models = active_models if active_models is not None else set()
    if isinstance(value, Enum):
        return {
            "$enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _canonical_value(value.value, active_models),
        }
    if isinstance(value, BaseModel):
        identity = id(value)
        if identity in active_models:
            raise ValueError("cyclic Pydantic model graph cannot be authorized")
        active_models.add(identity)
        try:
            fields = {
                name: _canonical_value(
                    object.__getattribute__(value, name), active_models
                )
                for name in sorted(type(value).model_fields)
            }
        finally:
            active_models.remove(identity)
        return {
            "$model": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": fields,
        }
    if isinstance(value, AnyUrl):
        return {"$url": str(value)}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers cannot be authorized")
        return value
    if isinstance(value, datetime):
        return {
            "$datetime": value.isoformat(),
            "fold": value.fold,
            "timezone_name": value.tzname(),
        }
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, UUID):
        return {"$uuid": str(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical mappings require string keys")
        return {
            key: _canonical_value(value[key], active_models)
            for key in sorted(value)
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item, active_models) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical_value(item, active_models) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
    raise TypeError(
        f"unsupported value type in authorization snapshot: {type(value).__name__}"
    )


def _content_snapshot(value: object) -> Optional[_ContentSnapshot]:
    if not isinstance(value, BaseModel):
        return None
    try:
        canonical_json = _canonical_json(value)
        payload = BaseModel.model_dump(
            value,
            mode="json",
            round_trip=True,
        )
        payload_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        if all(field in payload for field in _RR_SEMANTIC_FIELDS):
            semantic_payload = {
                field: payload[field] for field in _RR_SEMANTIC_FIELDS
            }
            semantic_json = _canonical_json(
                {
                    field: object.__getattribute__(value, field)
                    for field in _RR_SEMANTIC_FIELDS
                }
            )
        else:
            semantic_payload = payload
            semantic_json = canonical_json
        semantic_payload_json = _json_bytes(semantic_payload)
        return _ContentSnapshot(
            canonical_json=canonical_json,
            payload_json=payload_json,
            semantic_json=semantic_json,
            semantic_payload_json=semantic_payload_json,
        )
    except (
        AttributeError,
        OverflowError,
        RecursionError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return None


def _canonical_json(value: object) -> bytes:
    return _json_bytes(_canonical_value(value))


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class _ProtectedIdentityRegistry(_IdentityRegistry):
    def add(self, item: object) -> bool:
        del item
        return False

    def _register_snapshot(self, item: object) -> bool:
        del item
        return False


class _EvaluatorResultRegistry(_ProtectedIdentityRegistry):
    def record_evaluator_execution(self, result: object) -> bool:
        try:
            validated = type(result).model_validate(result)
            if (
                getattr(validated, "evaluator_identity", None)
                != "factchecker-evidence-nli"
                or not getattr(validated, "evaluator_version", None)
            ):
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        return _IdentityRegistry._register_snapshot(
            self,
            result,
            authority=_REGISTRATION_AUTHORITY,
        )


class _ReasoningRepresentationRegistry(_ProtectedIdentityRegistry):
    def record_adapter_transition(
        self,
        record: object,
        source_record: object,
        evaluation: object,
    ) -> bool:
        evaluator_authorized = _is_evaluator_result(evaluation)
        source_authorized = _is_authorized_reasoning_representation(
            source_record
        )
        if not evaluator_authorized:
            return False
        if _contains_directional_content(source_record) and not source_authorized:
            return False
        relationship = getattr(evaluation, "relationship", None)
        if relationship is None:
            return False
        if not getattr(record, "relationships", ()):
            return False
        if record.relationships[-1] != relationship:
            return False
        if (
            getattr(record, "claim", None) is None
            or record.claim.claim_id != getattr(evaluation, "claim_id", None)
            or relationship.claim_id != record.claim.claim_id
            or relationship.evidence_id
            not in {item.evidence_id for item in record.evidence}
        ):
            return False
        if _is_directional_label(relationship.label):
            scope = getattr(evaluation, "scope_assessment", None)
            if (
                not evaluator_authorized
                or scope is None
                or not scope.is_verified_compatible()
            ):
                return False

        source_snapshot = _content_snapshot(source_record)
        record_snapshot = _content_snapshot(record)
        if source_snapshot is None or record_snapshot is None:
            return False
        source_payload = json.loads(source_snapshot.payload_json)
        expected_payload = {
            **source_payload,
            "relationships": [
                *source_payload["relationships"],
                BaseModel.model_dump(
                    relationship,
                    mode="json",
                    round_trip=True,
                ),
            ],
        }
        if record_snapshot.payload_json != _json_bytes(expected_payload):
            return False
        return _IdentityRegistry._register_snapshot(
            self,
            record,
            authority=_REGISTRATION_AUTHORITY,
        )


class _CMREAContextRegistry(_ProtectedIdentityRegistry):
    def record_after_capability(
        self,
        context: object,
        authorized_snapshot: _ContentSnapshot,
    ) -> bool:
        context_snapshot = _content_snapshot(context)
        if (
            context_snapshot is None
            or context_snapshot.semantic_json != authorized_snapshot.semantic_json
            or context_snapshot.semantic_payload_json
            != authorized_snapshot.semantic_payload_json
            or tuple(getattr(context, "explanation_constraints", ()))
            != _CMREA_EXPLANATION_CONSTRAINTS
        ):
            return False
        return _IdentityRegistry._register_snapshot(
            self,
            context,
            authority=_REGISTRATION_AUTHORITY,
        )


_evaluator_results = _EvaluatorResultRegistry()
_authorized_reasoning_representations = _ReasoningRepresentationRegistry()
_authorized_cmrea_contexts = _CMREAContextRegistry()
_cmrea_capabilities: dict[
    int, tuple[weakref.ReferenceType, _ContentSnapshot]
] = {}
_capability_lock = RLock()


def _is_directional_label(label: object) -> bool:
    return getattr(label, "value", label) in _DIRECTIONAL_LABELS


def _contains_directional_content(record: object) -> bool:
    relationships = getattr(record, "relationships", ())
    assessment = getattr(record, "assessment", None)
    verdict = getattr(assessment, "verdict", None)
    return (
        any(
            _is_directional_label(getattr(item, "label", None))
            for item in relationships
        )
        or getattr(verdict, "value", verdict) in {"SUPPORTED", "REFUTED"}
    )


def _is_evaluator_result(result: object) -> bool:
    return _evaluator_results.contains(result)


def _is_authorized_reasoning_representation(record: object) -> bool:
    return _authorized_reasoning_representations.contains(record)


class _CMREACapability:
    __slots__ = ("__weakref__",)


def _issue_cmrea_capability(
    reasoning_representation: object,
) -> Optional[tuple[object, _ContentSnapshot]]:
    snapshot = _authorized_reasoning_representations.snapshot_if_authorized(
        reasoning_representation
    )
    if snapshot is None:
        return None
    capability = _CMREACapability()
    capability_id = id(capability)

    def discard(reference: weakref.ReferenceType) -> None:
        with _capability_lock:
            if _cmrea_capabilities.get(capability_id, (None, None))[0] is reference:
                _cmrea_capabilities.pop(capability_id, None)

    capability_reference = weakref.ref(capability, discard)
    with _capability_lock:
        _cmrea_capabilities[capability_id] = (
            capability_reference,
            snapshot,
        )
    return capability, snapshot


def _authorize_cmrea_context(
    context: object,
    capability: object,
) -> bool:
    with _capability_lock:
        capability_id = id(capability)
        authorization = _cmrea_capabilities.get(capability_id)
        if authorization is None or authorization[0]() is not capability:
            return False
        _cmrea_capabilities.pop(capability_id, None)
        authorized_snapshot = authorization[1]
    return _authorized_cmrea_contexts.record_after_capability(
        context, authorized_snapshot
    )


def _is_authorized_cmrea_context(context: object) -> bool:
    return _authorized_cmrea_contexts.contains(context)


def _is_registered_cmrea_context(context: object) -> bool:
    return _authorized_cmrea_contexts.contains_entry(context)


def _cmrea_context_snapshot(
    context: object,
) -> Optional[_ContentSnapshot]:
    return _authorized_cmrea_contexts.snapshot_if_authorized(context)
