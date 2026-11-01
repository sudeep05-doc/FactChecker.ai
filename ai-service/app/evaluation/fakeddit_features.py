"""Offline feature extraction for the acquired Fakeddit research dataset."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union
from uuid import NAMESPACE_URL, UUID, uuid5

from app.cmref import CMREF
from app.cmref.projection import ProjectionAdapter, ProjectionRegistry
from app.config.settings import Settings
from app.decision.features import extract_features
from app.evaluation.schemas import DatasetSplit, GroundTruthLabel
from app.models import OpenCLIPImageEncoder, SentenceTransformerTextEncoder
from app.rr import build_reasoning_representation
from app.usr import UnifiedSemanticRepresentationBuilder
from app.usr.models import USRImage, USRText

FEATURE_SCHEMA_VERSION = "fakeddit-foundation-v1"
CACHE_SCHEMA_VERSION = "fakeddit-feature-cache-v1"
DEFAULT_TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_IMAGE_MODEL = "ViT-B-32"
DEFAULT_IMAGE_CHECKPOINT = "openai"
CONFIGURATION_FINGERPRINT_VERSION = "fakeddit-feature-config-v2"
TEXT_PREPROCESSING_VERSION = "ordered-character-chunks-mean-normalized-v1"
IMAGE_PREPROCESSING_VERSION = "openclip-checkpoint-transform-rgb-normalized-v1"
LEGACY_TEXT_PREPROCESSING_VERSION = "ordered_character_chunks_mean_normalized"


@dataclass(frozen=True)
class FeatureExtractionConfig:
    data_dir: Union[str, Path] = "data/research/fakeddit"
    output_dir: Union[str, Path] = "data/research/fakeddit-features"
    text_batch_size: int = 16
    image_batch_size: int = 8
    device: str = "auto"
    split: Optional[Union[str, DatasetSplit]] = None
    max_samples: Optional[int] = None
    resume: bool = True
    quiet: bool = False

    def __post_init__(self) -> None:
        if self.text_batch_size < 1:
            raise ValueError("text_batch_size must be positive")
        if self.image_batch_size < 1:
            raise ValueError("image_batch_size must be positive")
        if self.max_samples is not None and self.max_samples < 1:
            raise ValueError("max_samples must be positive")

    def configuration_hash(self) -> str:
        """Return the original hash retained for legacy checkpoint compatibility."""
        payload = {
            "feature_schema": FEATURE_SCHEMA_VERSION,
            "cache_schema": CACHE_SCHEMA_VERSION,
            "data_dir": str(Path(self.data_dir)),
            "output_dir": str(Path(self.output_dir)),
            "text_batch_size": self.text_batch_size,
            "image_batch_size": self.image_batch_size,
            "device": self.device,
            "split": self.split.value if isinstance(self.split, DatasetSplit) else str(self.split),
            "max_samples": self.max_samples,
            "resume": self.resume,
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def configuration_fingerprint(
        self,
        *,
        library_versions: Optional[Dict[str, str]] = None,
    ) -> str:
        payload = {
            "fingerprint_version": CONFIGURATION_FINGERPRINT_VERSION,
            "legacy_configuration_hash": self.configuration_hash(),
            "feature_schema": FEATURE_SCHEMA_VERSION,
            "cache_schema": CACHE_SCHEMA_VERSION,
            "decision_feature_schema": "rr-decision-v1",
            "models": {
                "text": {"model_id": DEFAULT_TEXT_MODEL},
                "image": {"model_id": DEFAULT_IMAGE_MODEL, "checkpoint": DEFAULT_IMAGE_CHECKPOINT},
            },
            "preprocessing": {
                "text": {
                    "version": TEXT_PREPROCESSING_VERSION,
                    "chunk_size_characters": 4000,
                    "language": "en",
                    "normalized": True,
                },
                "image": {
                    "version": IMAGE_PREPROCESSING_VERSION,
                    "color_mode": "RGB",
                    "normalized": True,
                },
            },
            "libraries": library_versions if library_versions is not None else _runtime_library_versions(),
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=1)
def _runtime_library_versions() -> Dict[str, str]:
    distributions = (
        "torch",
        "sentence-transformers",
        "transformers",
        "open_clip_torch",
        "torchvision",
        "Pillow",
        "numpy",
    )
    versions = {"python": sys.version.split()[0]}
    for distribution in distributions:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def _coerce_split(value: Union[str, DatasetSplit]) -> DatasetSplit:
    if isinstance(value, DatasetSplit):
        return value
    normalized = str(value).strip().lower()
    for split in DatasetSplit:
        if normalized == split.value:
            return split
    raise ValueError(f"unsupported split: {value}")


class FeatureExtractionCache:
    """JSONL-style JSON cache keyed by sample_id and configuration hash."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.values: Dict[str, Any] = {}
        if self.path.is_file():
            try:
                self.values = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.values = {}

    def get(
        self,
        sample_id: str,
        configuration_hash: str,
        configuration_fingerprint: Optional[str] = None,
    ) -> Optional[dict]:
        value = self.values.get(sample_id)
        if not value:
            return None
        if value.get("configuration_hash") == configuration_hash:
            if configuration_fingerprint is not None and value.get("configuration_fingerprint") != configuration_fingerprint:
                return None
            return value
        return None

    def put(self, sample_id: str, configuration_hash: str, payload: dict) -> None:
        self.values[sample_id] = {"configuration_hash": configuration_hash, **payload}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.path, json.dumps(self.values, indent=2, sort_keys=True))


def _atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@contextmanager
def _checkpoint_lock(output_dir: Path) -> Iterator[None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".feature-extraction.lock"
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_jsonl_records(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Interrupted writes may leave a truncated final JSON object at the end of the file.
                # Keep the valid records and skip only the incomplete trailing fragment.
                continue
    return records


def _acquired_local_image(record: dict, data_dir: Path) -> Optional[Path]:
    metadata = record.get("metadata") or {}
    acquisition = metadata.get("acquisition") or {}
    status = str(acquisition.get("acquisition_status") or "").strip().lower()
    if status not in {"downloaded", "already_present", "success", "successful", "acquired"}:
        return None
    local_image = metadata.get("local_image_path") or record.get("local_image_path")
    return _resolve_local_image_path(local_image, data_dir=data_dir)


def iter_acquired_records(
    data_dir: Union[str, Path],
    *,
    split: Optional[Union[str, DatasetSplit]] = None,
    max_samples: Optional[int] = None,
    statistics: Optional[Dict[str, int]] = None,
) -> Iterator[dict]:
    root = Path(data_dir)
    splits = [
        _coerce_split(split)
    ] if split is not None else [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]

    for current in splits:
        manifest = _resolve_manifest_path(root, current)
        if not manifest.exists():
            continue
        seen = 0
        with manifest.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                record_split = record.get("split")
                if record_split is not None:
                    record_split = _coerce_split(record_split)
                    if record_split != current:
                        continue
                if "sample_id" not in record or not str(record["sample_id"]).strip():
                    continue
                if _acquired_local_image(record, root) is None:
                    if statistics is not None:
                        statistics["acquisition_skipped"] = statistics.get("acquisition_skipped", 0) + 1
                    continue
                if max_samples is not None and seen >= max_samples:
                    return
                seen += 1
                yield record


def _resolve_manifest_path(data_dir: Path, split: DatasetSplit) -> Path:
    candidate_directories = [data_dir / "acquired", data_dir]
    for directory in candidate_directories:
        candidate = directory / f"{split.value}.jsonl"
        if candidate.is_file():
            return candidate
    return data_dir / "acquired" / f"{split.value}.jsonl"


def _effective_split(record: dict, fallback: DatasetSplit) -> DatasetSplit:
    split_value = record.get("split")
    if split_value is None:
        return fallback
    return _coerce_split(split_value)


def _coerce_label(value: Any) -> GroundTruthLabel:
    return GroundTruthLabel(str(value).strip().upper())


def _resolve_local_image_path(image_path: Any, *, data_dir: Path) -> Optional[Path]:
    if image_path is None:
        return None
    candidate = Path(str(image_path))
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    if candidate.is_file():
        return candidate.resolve()
    root_candidates = [
        data_dir / candidate,
        data_dir / "acquired" / candidate,
        data_dir / "images" / candidate.name,
        data_dir / "acquired" / "images" / candidate.name,
    ]
    for path in root_candidates:
        if path.is_file():
            return path.resolve()
    return None


def _pad_or_truncate(values: Sequence[float], target_dim: int) -> List[float]:
    padded = list(values)
    if len(padded) < target_dim:
        padded.extend([0.0] * (target_dim - len(padded)))
    elif len(padded) > target_dim:
        padded = padded[:target_dim]
    return padded


def _projection_registry_for(text_embedding: Any, image_embedding: Any) -> ProjectionRegistry:
    working_dim = max(int(text_embedding.dimension), int(image_embedding.dimension))
    text_name = text_embedding.model_name
    image_name = image_embedding.model_name
    adapters = {
        text_name: ProjectionAdapter(
            model_name=text_name,
            source_dimension=text_embedding.dimension,
            target_dimension=working_dim,
            version="padded-identity-v1",
            transform=lambda values, source=text_embedding.dimension, target=working_dim: _pad_or_truncate(values, target),
        ),
        image_name: ProjectionAdapter(
            model_name=image_name,
            source_dimension=image_embedding.dimension,
            target_dimension=working_dim,
            version="padded-identity-v1",
            transform=lambda values, source=image_embedding.dimension, target=working_dim: _pad_or_truncate(values, target),
        ),
    }
    return ProjectionRegistry(working_dim, adapters=adapters)


def build_feature_artifact(
    sample: dict,
    config: FeatureExtractionConfig,
    *,
    text_encoder: Optional[SentenceTransformerTextEncoder] = None,
    image_encoder: Optional[OpenCLIPImageEncoder] = None,
    text_usr: Optional[USRText] = None,
    image_usr: Optional[USRImage] = None,
) -> dict:
    sample_id = str(sample["sample_id"])
    split = _effective_split(sample, DatasetSplit.TEST)
    label = _coerce_label(sample.get("label", "REAL")).value
    clean_title = str(sample.get("text") or sample.get("metadata", {}).get("clean_title") or "").strip()
    if not clean_title:
        raise ValueError(f"sample {sample_id} is missing clean_title/text")

    metadata = sample.get("metadata") or {}
    local_image_path = metadata.get("local_image_path") or sample.get("local_image_path")
    resolved_path = _resolve_local_image_path(local_image_path, data_dir=Path(config.data_dir))
    if resolved_path is None or not resolved_path.is_file():
        raise ValueError(f"sample {sample_id} is missing a valid local image path")

    settings = Settings(
        text_encoder_model=DEFAULT_TEXT_MODEL,
        text_encoder_device=config.device,
        text_encoder_batch_size=config.text_batch_size,
        text_encoder_chunk_size=4000,
        image_encoder_model=DEFAULT_IMAGE_MODEL,
        image_encoder_checkpoint=DEFAULT_IMAGE_CHECKPOINT,
        image_encoder_device=config.device,
        image_encoder_batch_size=config.image_batch_size,
    )
    if text_usr is None:
        text_encoder = text_encoder or SentenceTransformerTextEncoder(settings=settings)
        text_usr = text_encoder.to_usr_text(clean_title, language="en")
    if image_usr is None:
        image_encoder = image_encoder or OpenCLIPImageEncoder(settings=settings)
        image_usr = image_encoder.to_usr_image(str(resolved_path))
    if text_usr is None:
        raise ValueError(f"sample {sample_id} text embedding is unavailable")
    if image_usr is None:
        raise ValueError(f"sample {sample_id} image embedding is unavailable")

    usr = UnifiedSemanticRepresentationBuilder().build(
        uuid5(NAMESPACE_URL, sample_id),
        text=text_usr,
        image=image_usr,
    )
    cmref = CMREF(_projection_registry_for(text_usr.embedding, image_usr.embedding))
    rr = build_reasoning_representation(cmref.reason(usr))
    feature_vector = extract_features(rr)
    configuration_hash = config.configuration_hash()
    configuration_fingerprint = config.configuration_fingerprint()
    artifact = {
        "sample_id": sample_id,
        "sample_identity": {
            "sample_id": sample_id,
            "source_reference": sample.get("source_reference") or sample_id,
            "split": split.value,
        },
        "split": split.value,
        "label": label,
        "clean_title": clean_title,
        "text_provenance": {
            "clean_title": clean_title,
            "language": "en",
            "model_name": text_usr.embedding.model_name,
            "dimension": text_usr.embedding.dimension,
            "normalized": text_usr.embedding.normalized,
            "source": "SentenceTransformerTextEncoder.to_usr_text",
            "processing": text_usr.metadata.get("processing", {}),
        },
        "image_provenance": {
            "local_image_path": str(resolved_path.relative_to(Path(config.data_dir).resolve())) if str(resolved_path).startswith(str(Path(config.data_dir).resolve())) else str(resolved_path),
            "source_url": sample.get("image") or metadata.get("image_reference"),
            "model_name": image_usr.embedding.model_name,
            "checkpoint": image_usr.metadata.get("checkpoint"),
            "dimension": image_usr.embedding.dimension,
            "normalized": image_usr.embedding.normalized,
            "processing": image_usr.metadata.get("processing", {}),
        },
        "feature_vector": feature_vector.values,
        "feature_names": feature_vector.names,
        "feature_schema_version": feature_vector.schema_version,
        "feature_cache_version": CACHE_SCHEMA_VERSION,
        "configuration_hash": configuration_hash,
        "configuration_fingerprint": configuration_fingerprint,
        "configuration_fingerprint_version": CONFIGURATION_FINGERPRINT_VERSION,
        "model_metadata": {
            "text": {
                "model_name": text_usr.embedding.model_name,
                "dimension": text_usr.embedding.dimension,
                "normalized": text_usr.embedding.normalized,
                "device": text_usr.metadata.get("processing", {}).get("device"),
            },
            "image": {
                "model_name": image_usr.embedding.model_name,
                "dimension": image_usr.embedding.dimension,
                "normalized": image_usr.embedding.normalized,
                "checkpoint": image_usr.metadata.get("checkpoint"),
                "device": image_usr.metadata.get("processing", {}).get("device"),
            },
            "cmref": {
                "working_dimension": max(text_usr.embedding.dimension, image_usr.embedding.dimension),
                "projection_version": "padded-identity-v1",
            },
            "rr": {
                "available_modalities": rr.available_modalities,
                "reasoning_score": rr.reasoning_score,
                "decision_evidence": rr.decision_evidence,
            },
        },
        "cmref_metadata": {
            "available_modalities": rr.available_modalities,
            "omitted_modalities": rr.omitted_modalities,
            "reasoning_score": rr.reasoning_score,
            "decision_evidence": rr.decision_evidence,
            "pairwise_alignment_count": len(rr.pairwise_alignments),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return artifact


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    data = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    _atomic_write_text(path, data)


def _is_complete_feature_artifact(
    artifact: Any,
    *,
    sample: dict,
    config: FeatureExtractionConfig,
    configuration_fingerprint: str,
    data_dir: Path,
) -> bool:
    if not isinstance(artifact, dict):
        return False
    sample_id = str(sample.get("sample_id") or "")
    split = _effective_split(sample, DatasetSplit.TEST).value
    vector = artifact.get("feature_vector")
    if not isinstance(vector, list) or len(vector) != 20:
        return False
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in vector):
        return False
    if (
        str(artifact.get("sample_id")) != sample_id
        or artifact.get("split") != split
        or artifact.get("feature_cache_version") != CACHE_SCHEMA_VERSION
        or artifact.get("feature_schema_version") != "rr-decision-v1"
        or not isinstance(artifact.get("feature_names"), list)
        or len(artifact["feature_names"]) != 20
        or not artifact.get("created_at")
    ):
        return False
    stored_fingerprint = artifact.get("configuration_fingerprint")
    if stored_fingerprint is not None:
        if (
            stored_fingerprint != configuration_fingerprint
            or artifact.get("configuration_hash") != config.configuration_hash()
            or artifact.get("configuration_fingerprint_version") != CONFIGURATION_FINGERPRINT_VERSION
        ):
            return False
    elif not _matches_legacy_configuration(artifact, config):
        return False
    identity = artifact.get("sample_identity") or {}
    if identity.get("sample_id") != sample_id or identity.get("split") != split:
        return False
    if artifact.get("label") != sample.get("label"):
        return False
    text = artifact.get("text_provenance") or {}
    image = artifact.get("image_provenance") or {}
    text_model = ((artifact.get("model_metadata") or {}).get("text") or {})
    image_model = ((artifact.get("model_metadata") or {}).get("image") or {})
    if (
        not text.get("clean_title")
        or text.get("model_name") != DEFAULT_TEXT_MODEL
        or text.get("dimension") != 384
        or not isinstance(text.get("processing"), dict)
        or image.get("model_name") != DEFAULT_IMAGE_MODEL
        or image.get("checkpoint") != DEFAULT_IMAGE_CHECKPOINT
        or image.get("dimension") != 512
        or not isinstance(image.get("processing"), dict)
        or text_model.get("model_name") != DEFAULT_TEXT_MODEL
        or text_model.get("dimension") != 384
        or image_model.get("model_name") != DEFAULT_IMAGE_MODEL
        or image_model.get("checkpoint") != DEFAULT_IMAGE_CHECKPOINT
        or image_model.get("dimension") != 512
    ):
        return False
    source_image = _acquired_local_image(sample, data_dir)
    artifact_image = _resolve_local_image_path(image.get("local_image_path"), data_dir=data_dir)
    return source_image is not None and artifact_image is not None and source_image.resolve() == artifact_image.resolve()


def _matches_legacy_configuration(artifact: dict, config: FeatureExtractionConfig) -> bool:
    text = artifact.get("text_provenance") or {}
    image = artifact.get("image_provenance") or {}
    text_processing = text.get("processing") or {}
    image_processing = image.get("processing") or {}
    model_metadata = artifact.get("model_metadata") or {}
    text_model = model_metadata.get("text") or {}
    image_model = model_metadata.get("image") or {}
    return (
        artifact.get("configuration_hash") == config.configuration_hash()
        and text.get("model_name") == DEFAULT_TEXT_MODEL
        and text.get("dimension") == 384
        and text.get("normalized") is True
        and text.get("source") == "SentenceTransformerTextEncoder.to_usr_text"
        and text_processing.get("batch_size") == config.text_batch_size
        and text_processing.get("requested_device") == config.device
        and text_processing.get("deterministic_inference") is True
        and text_processing.get("normalized_embeddings") is True
        and text_processing.get("chunking_strategy") == LEGACY_TEXT_PREPROCESSING_VERSION
        and image.get("model_name") == DEFAULT_IMAGE_MODEL
        and image.get("checkpoint") == DEFAULT_IMAGE_CHECKPOINT
        and image.get("dimension") == 512
        and image.get("normalized") is True
        and image_processing.get("batch_size") == config.image_batch_size
        and image_processing.get("requested_device") == config.device
        and image_processing.get("deterministic_inference") is True
        and image_processing.get("normalized_embedding") is True
        and text_model.get("model_name") == DEFAULT_TEXT_MODEL
        and text_model.get("dimension") == 384
        and image_model.get("model_name") == DEFAULT_IMAGE_MODEL
        and image_model.get("checkpoint") == DEFAULT_IMAGE_CHECKPOINT
        and image_model.get("dimension") == 512
    )


def reconcile_feature_checkpoint(config: FeatureExtractionConfig) -> Dict[str, Any]:
    with _checkpoint_lock(Path(config.output_dir)):
        return _reconcile_feature_checkpoint(config)


def _reconcile_feature_checkpoint(config: FeatureExtractionConfig) -> Dict[str, Any]:
    """Reconcile complete artifacts from JSONL/cache, then persist both in manifest order.

    JSONL is the canonical user-facing dataset. A complete cache-only artifact is
    restored to JSONL, while valid JSONL-only artifacts rebuild the cache index.
    """
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_hash = config.configuration_hash()
    config_fingerprint = config.configuration_fingerprint()
    cache = FeatureExtractionCache(output_dir / "feature_cache.json")
    original_cache_entries = len(cache.values)
    manifest_by_split: Dict[str, Dict[str, dict]] = {}
    order_by_split: Dict[str, List[str]] = {}
    acquisition_skipped_by_split: Dict[str, int] = {}
    for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST):
        skipped = {"acquisition_skipped": 0}
        acquired = list(iter_acquired_records(config.data_dir, split=split, statistics=skipped))
        manifest_by_split[split.value] = {str(record["sample_id"]): record for record in acquired}
        order_by_split[split.value] = [str(record["sample_id"]) for record in acquired]
        acquisition_skipped_by_split[split.value] = skipped["acquisition_skipped"]

    jsonl_rows: Dict[str, List[dict]] = {}
    original_feature_rows = 0
    original_failure_rows = 0
    for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST):
        path = output_dir / f"{split.value}.jsonl"
        rows = _read_jsonl_records(path)
        jsonl_rows[split.value] = rows
        original_feature_rows += sum("feature_vector" in row for row in rows)
        original_failure_rows += sum("feature_vector" not in row for row in rows)

    completed_by_split: Dict[str, Dict[str, dict]] = {split.value: {} for split in DatasetSplit}
    jsonl_ids: set = set()
    cache_ids: set = set()
    cache_only_recovered = 0
    jsonl_only_recovered = 0
    for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST):
        split_name = split.value
        eligible = manifest_by_split[split_name]
        rows_by_id: Dict[str, dict] = {}
        for row in jsonl_rows[split_name]:
            sample_id = str(row.get("sample_id") or "")
            if sample_id and sample_id not in rows_by_id:
                rows_by_id[sample_id] = row
        for sample_id in order_by_split[split_name]:
            sample = eligible[sample_id]
            jsonl_candidate = rows_by_id.get(sample_id)
            if not _is_complete_feature_artifact(
                jsonl_candidate,
                sample=sample,
                config=config,
                configuration_fingerprint=config_fingerprint,
                data_dir=Path(config.data_dir),
            ):
                jsonl_candidate = None
            cache_candidate = cache.values.get(sample_id)
            if not _is_complete_feature_artifact(
                cache_candidate,
                sample=sample,
                config=config,
                configuration_fingerprint=config_fingerprint,
                data_dir=Path(config.data_dir),
            ):
                cache_candidate = None
            if jsonl_candidate is not None:
                artifact = jsonl_candidate
                jsonl_ids.add(sample_id)
                if cache_candidate is None:
                    jsonl_only_recovered += 1
            elif cache_candidate is not None:
                artifact = cache_candidate
                cache_only_recovered += 1
            else:
                continue
            completed_by_split[split_name][sample_id] = artifact
            cache_ids.add(sample_id)

    canonical_cache: Dict[str, dict] = {}
    for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST):
        split_name = split.value
        canonical_rows = [
            completed_by_split[split_name][sample_id]
            for sample_id in order_by_split[split_name]
            if sample_id in completed_by_split[split_name]
        ]
        output_path = output_dir / f"{split_name}.jsonl"
        if output_path.exists() or canonical_rows:
            _write_jsonl(output_path, canonical_rows)
        for artifact in canonical_rows:
            canonical_cache[str(artifact["sample_id"])] = {
                "configuration_hash": config_hash,
                **artifact,
            }
    cache.values = canonical_cache
    cache.save()

    output_completed_ids = {
        str(row["sample_id"])
        for rows in completed_by_split.values()
        for row in rows.values()
    }
    cache_completed_ids = set(cache.values)
    if output_completed_ids != cache_completed_ids:
        raise RuntimeError("checkpoint reconciliation failed: JSONL/cache completed IDs differ")
    records_requiring_recomputation = sum(
        len(manifest_by_split[split.value]) - len(completed_by_split[split.value])
        for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST)
    )
    return {
        "original_jsonl_feature_rows": original_feature_rows,
        "original_failure_rows": original_failure_rows,
        "original_cache_entries": original_cache_entries,
        "reconciled_feature_rows": len(output_completed_ids),
        "reconciled_cache_entries": len(cache_completed_ids),
        "cache_only_records_recovered": cache_only_recovered,
        "jsonl_only_records_recovered": jsonl_only_recovered,
        "records_requiring_recomputation": records_requiring_recomputation,
        "acquisition_failures_skipped": sum(acquisition_skipped_by_split.values()),
        "acquisition_failures_by_split": acquisition_skipped_by_split,
        "completed_ids_by_split": {split: set(rows) for split, rows in completed_by_split.items()},
    }


def _process_batch(
    batch: List[dict],
    *,
    config: FeatureExtractionConfig,
    output_dir: Path,
    split: DatasetSplit,
    cache: FeatureExtractionCache,
    text_encoder: SentenceTransformerTextEncoder,
    image_encoder: OpenCLIPImageEncoder,
    progress: List[dict],
) -> Tuple[int, int]:
    if not batch:
        return 0, 0

    texts = [str(record.get("text") or record.get("metadata", {}).get("clean_title") or "").strip() for record in batch]
    images = []
    for record in batch:
        local_image = (record.get("metadata") or {}).get("local_image_path") or record.get("local_image_path")
        resolved = _resolve_local_image_path(local_image, data_dir=Path(config.data_dir))
        images.append(str(resolved) if resolved is not None else "")

    text_results = text_encoder.encode_batch_with_chunking(texts, language="en")
    image_results = image_encoder.encode_batch(images)
    if len(text_results) != len(batch) or len(image_results) != len(batch):
        raise RuntimeError("foundation encoders returned a result count that does not match the input batch")

    split_output = output_dir / f"{split.value}.jsonl"
    existing_records = _read_jsonl_records(split_output)
    records_by_id = {
        str(record["sample_id"]): record
        for record in existing_records
        if "sample_id" in record and "feature_vector" in record
    }
    completed: List[dict] = []
    failed = 0
    for sample, text, text_result, image_result in zip(batch, texts, text_results, image_results):
        sample_id = str(sample["sample_id"])
        try:
            if text_result.status.value != "available":
                raise ValueError(f"text embedding unavailable: {text_result.error_code}")
            if image_result.encoding_status.value != "completed":
                raise ValueError(f"image embedding unavailable: {image_result.errors[0].code if image_result.errors else 'unknown'}")
            text_usr = text_encoder.to_usr_text_from_result(text, text_result)
            image_usr = image_encoder.to_usr_image_from_result(image_result)
            if text_usr is None:
                raise ValueError(f"sample {sample_id} text embedding is unavailable")
            if image_usr is None:
                raise ValueError(f"sample {sample_id} image embedding is unavailable")
            artifact = build_feature_artifact(
                sample,
                config,
                text_usr=text_usr,
                image_usr=image_usr,
            )
            records_by_id[sample_id] = artifact
            completed.append(artifact)
            progress.append({"sample_id": sample_id, "status": "processed"})
        except Exception as exc:  # pragma: no cover - defensive handling for real runs
            failed += 1
            progress.append({"sample_id": sample_id, "status": "failed", "error": str(exc)})

    if completed:
        order = [str(record["sample_id"]) for record in existing_records if record.get("feature_vector")]
        order.extend(artifact["sample_id"] for artifact in completed if artifact["sample_id"] not in order)
        _write_jsonl(split_output, [records_by_id[sample_id] for sample_id in order])
        for artifact in completed:
            cache.put(str(artifact["sample_id"]), config.configuration_hash(), artifact)
        cache.save()
    return len(completed), failed


def run_feature_extraction(config: FeatureExtractionConfig) -> Dict[str, Any]:
    with _checkpoint_lock(Path(config.output_dir)):
        return _run_feature_extraction(config)


def _run_feature_extraction(config: FeatureExtractionConfig) -> Dict[str, Any]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_splits = [
        _coerce_split(config.split)
    ] if config.split is not None else [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]
    checkpoint = _reconcile_feature_checkpoint(config)
    cache = FeatureExtractionCache(output_dir / "feature_cache.json")
    summary = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "total": 0,
        "successful": 0,
        "acquisition_skipped": sum(checkpoint["acquisition_failures_by_split"][split.value] for split in target_splits),
        "extraction_failed": 0,
        "splits": {split.value: {"total": 0, "processed": 0, "skipped": 0, "failed": 0} for split in target_splits},
    }
    text_encoder = SentenceTransformerTextEncoder(
        settings=Settings(
            text_encoder_model=DEFAULT_TEXT_MODEL,
            text_encoder_device=config.device,
            text_encoder_batch_size=config.text_batch_size,
            text_encoder_chunk_size=4000,
        )
    )
    image_encoder = OpenCLIPImageEncoder(
        settings=Settings(
            image_encoder_model=DEFAULT_IMAGE_MODEL,
            image_encoder_checkpoint=DEFAULT_IMAGE_CHECKPOINT,
            image_encoder_device=config.device,
            image_encoder_batch_size=config.image_batch_size,
        )
    )

    for split in target_splits:
        batch: List[dict] = []
        for record in iter_acquired_records(config.data_dir, split=split, max_samples=config.max_samples):
            summary["total"] += 1
            summary["splits"][split.value]["total"] += 1
            sample_id = str(record.get("sample_id") or "")
            if config.resume and sample_id in checkpoint["completed_ids_by_split"][split.value]:
                summary["skipped"] += 1
                summary["splits"][split.value]["skipped"] += 1
                continue
            batch.append(record)
            if len(batch) >= min(config.text_batch_size, config.image_batch_size):
                processed, failed = _process_batch(
                    batch,
                    config=config,
                    output_dir=output_dir,
                    split=split,
                    cache=cache,
                    text_encoder=text_encoder,
                    image_encoder=image_encoder,
                    progress=[],
                )
                summary["processed"] += processed
                summary["failed"] += failed
                summary["splits"][split.value]["processed"] += processed
                summary["splits"][split.value]["failed"] += failed
                batch = []
        if batch:
            processed, failed = _process_batch(
                batch,
                config=config,
                output_dir=output_dir,
                split=split,
                cache=cache,
                text_encoder=text_encoder,
                image_encoder=image_encoder,
                progress=[],
            )
            summary["processed"] += processed
            summary["failed"] += failed
            summary["splits"][split.value]["processed"] += processed
            summary["splits"][split.value]["failed"] += failed

    final_checkpoint = _reconcile_feature_checkpoint(config)
    summary["successful"] = summary["processed"] + summary["skipped"]
    summary["extraction_failed"] = sum(
        summary["splits"][split.value]["total"]
        - summary["splits"][split.value]["skipped"]
        - summary["splits"][split.value]["processed"]
        for split in target_splits
    )
    if final_checkpoint["reconciled_feature_rows"] != final_checkpoint["reconciled_cache_entries"]:
        raise RuntimeError("feature extraction finished with inconsistent JSONL/cache state")

    if not config.quiet:
        print(json.dumps(summary, sort_keys=True, indent=2))
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract text+image foundation features from acquired Fakeddit data.")
    parser.add_argument("--data-dir", default="data/research/fakeddit", help="Directory containing acquired manifests and images")
    parser.add_argument("--output-dir", default="data/research/fakeddit-features", help="Where to write feature artifacts and cache")
    parser.add_argument("--text-batch-size", type=int, default=16, help="SentenceTransformer batch size")
    parser.add_argument("--image-batch-size", type=int, default=8, help="OpenCLIP batch size")
    parser.add_argument("--device", default="auto", help="Explicit device selection: auto, cpu, or mps")
    parser.add_argument("--split", choices=["train", "validation", "test"], help="Optional split filter")
    parser.add_argument("--max-samples", type=int, default=None, help="Optional smoke-test cap for a split")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True, help="Resume from validated checkpoint records (default)")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing cache entries and recompute")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logging")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = FeatureExtractionConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        text_batch_size=args.text_batch_size,
        image_batch_size=args.image_batch_size,
        device=args.device,
        split=args.split,
        max_samples=args.max_samples,
        resume=args.resume and not args.no_resume,
        quiet=args.quiet,
    )
    run_feature_extraction(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
