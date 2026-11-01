"""Resumable, leakage-manifest-driven rr-decision-v2 Fakeddit extraction."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import open_clip

from app.config.settings import Settings
from app.decision.features_v2 import (
    FEATURE_SCHEMA_VERSION,
    OPENCLIP_CHECKPOINT,
    OPENCLIP_DIMENSION,
    OPENCLIP_MODEL,
    PREDICTOR_ALLOWLIST,
    ModalityStatus,
    RRDecisionV2Features,
)
from app.evaluation.fakeddit_shared_features import build_shared_space_feature_artifact
from app.models import OpenCLIPImageEncoder


EXPECTED_MANIFEST_SHA256 = "3a39fe293c9b86820f1b4700ffed2d4d410e8ddf3e8d3f90b3c0267dc05ee6e2"
EXPECTED_AUDIT_SHA256 = "fd12f7ff13f122073ef995a363d8c0488fffc30c22a6f78f8a525fa82b692ef0"
EXPECTED_CHECKPOINT_SHA256 = "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"
PROTECTED_ARTIFACTS = {
    "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl":
        EXPECTED_MANIFEST_SHA256,
    "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json":
        EXPECTED_AUDIT_SHA256,
    "data/research/fakeddit-features/train.jsonl":
        "f0285b2a7e3fc78e9f6907b4ad68106866c17f97aea61185c891bc2779f2d537",
    "data/research/fakeddit-features/validation.jsonl":
        "7a357a260161777d2adbbb093d30c616cd2dbac0f14a2ae783093b73e1947d1b",
    "data/research/fakeddit-features/test.jsonl":
        "dcbaec128e2805c84668156c63f1bce1f9de9f99cf791788f67549744dbc9c42",
    "data/research/fakeddit-features/feature_cache.json":
        "3b33575dc8e0f647d53e23633098cbc776ed393a878c79606a8a98f4fc203b06",
}
EXPECTED_COUNTS = {"train": 19068, "validation": 3801, "test": 3799}
EXPECTED_QUARANTINED = 4
SPLITS = ("train", "validation", "test")
EXPERIMENT_ID = "task36c-v2-shared-space-20261015"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _ordered_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _atomic_write(path: Path, content: bytes, *, refuse_different_existing: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if refuse_different_existing and _sha256(path) == hashlib.sha256(content).hexdigest():
            return
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _atomic_replace_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (_canonical_json(value) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _read_jsonl(path: Path) -> List[dict]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {error}") from error
            if not isinstance(item, dict):
                raise ValueError(f"JSONL record is not an object at {path}:{line_number}")
            records.append(item)
    return records


def _runtime_versions() -> Dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for distribution in ("torch", "open_clip_torch", "torchvision", "Pillow", "numpy", "pydantic"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def _git_commit() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _load_inputs(
    *,
    service_root: Path,
    manifest_path: Path,
    audit_path: Path,
) -> Tuple[List[dict], List[dict], Dict[str, dict], Dict[str, Any]]:
    expected_manifest = service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    expected_audit = service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json"
    if manifest_path.resolve() != expected_manifest.resolve() or audit_path.resolve() != expected_audit.resolve():
        raise ValueError("Task 36C requires the approved Task 32B manifest and audit report paths")
    manifest_sha = _sha256(manifest_path)
    audit_sha = _sha256(audit_path)
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise ValueError(f"manifest SHA-256 mismatch: {manifest_sha}")
    if audit_sha != EXPECTED_AUDIT_SHA256:
        raise ValueError(f"audit report SHA-256 mismatch: {audit_sha}")
    protected_hashes = {}
    for relative_path, expected_hash in PROTECTED_ARTIFACTS.items():
        protected_path = service_root / relative_path
        if not protected_path.is_file():
            raise FileNotFoundError(f"protected research artifact is missing: {protected_path}")
        actual_hash = _sha256(protected_path)
        if actual_hash != expected_hash:
            raise ValueError(f"protected artifact SHA-256 mismatch for {relative_path}: {actual_hash}")
        protected_hashes[relative_path] = actual_hash

    manifest = _read_jsonl(manifest_path)
    ids = [str(row.get("sample_id") or "") for row in manifest]
    if len(ids) != len(set(ids)) or any(not sample_id for sample_id in ids):
        raise ValueError("manifest sample IDs must be non-empty and unique")
    assigned = [row for row in manifest if not row.get("quarantined")]
    quarantined = [row for row in manifest if row.get("quarantined")]
    counts = Counter(str(row.get("assigned_split")) for row in assigned)
    if len(manifest) != sum(EXPECTED_COUNTS.values()) + EXPECTED_QUARANTINED:
        raise ValueError(f"unexpected manifest size: {len(manifest)}")
    if dict(counts) != EXPECTED_COUNTS or len(quarantined) != EXPECTED_QUARANTINED:
        raise ValueError(f"manifest split/quarantine totals differ: {dict(counts)}, {len(quarantined)}")
    for row in assigned:
        if row.get("assigned_split") not in SPLITS or row.get("canonical_label") not in {"REAL", "FAKE"}:
            raise ValueError(f"invalid assigned manifest record: {row.get('sample_id')}")
        if row.get("quarantine_reason") is not None:
            raise ValueError(f"assigned record has quarantine reason: {row['sample_id']}")
    if any(row.get("assigned_split") is not None for row in quarantined):
        raise ValueError("quarantined records must not have an assigned split")

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audited_counts = {split: audit["assigned_counts"][split]["total"] for split in SPLITS}
    if audited_counts != EXPECTED_COUNTS or audit.get("quarantined_total") != EXPECTED_QUARANTINED:
        raise ValueError("audit report counts do not match required manifest totals")

    data_root = service_root / "data/research/fakeddit"
    sources: Dict[str, dict] = {}
    for original_split in SPLITS:
        source_path = data_root / "acquired" / f"{original_split}.jsonl"
        for record in _read_jsonl(source_path):
            sample_id = str(record.get("sample_id") or "")
            if sample_id in sources:
                raise ValueError(f"duplicate acquired sample ID: {sample_id}")
            sources[sample_id] = record

    original_features: Dict[str, dict] = {}
    feature_root = service_root / "data/research/fakeddit-features"
    for split in SPLITS:
        for record in _read_jsonl(feature_root / f"{split}.jsonl"):
            sample_id = str(record.get("sample_id") or "")
            if sample_id in original_features:
                raise ValueError(f"duplicate original feature sample ID: {sample_id}")
            original_features[sample_id] = record

    verified_image_hashes: Dict[str, str] = {}
    for row in manifest:
        sample_id = row["sample_id"]
        source = sources.get(sample_id)
        feature = original_features.get(sample_id)
        if source is None or feature is None:
            raise ValueError(f"manifest sample lacks source or original feature mapping: {sample_id}")
        source_meta = source.get("metadata") or {}
        acquisition = source_meta.get("acquisition") or {}
        for key in ("source_file", "source_row", "source_id"):
            if source_meta.get(key) != row.get(key):
                raise ValueError(f"{key} provenance mismatch for {sample_id}")
        if (
            source.get("split") != row.get("original_split")
            or source_meta.get("source_split") != row.get("original_split")
            or source.get("label") != row.get("canonical_label")
            or feature.get("label") != row.get("canonical_label")
            or str(source_meta.get("source_label")) != str(row.get("source_label"))
        ):
            raise ValueError(f"source split/label provenance mismatch for {sample_id}")
        text = str(source.get("text") or source_meta.get("clean_title") or "").strip()
        if not text or feature.get("clean_title") != text:
            raise ValueError(f"source title mapping mismatch for {sample_id}")
        local_path = source_meta.get("local_image_path") or source.get("local_image_path")
        if not local_path:
            raise ValueError(f"source local image path is absent for {sample_id}")
        image_path = Path(local_path)
        if not image_path.is_absolute():
            image_path = data_root / image_path
        if not image_path.is_file():
            raise ValueError(f"source image is missing for {sample_id}: {image_path}")
        if (feature.get("image_provenance") or {}).get("local_image_path") != local_path:
            raise ValueError(f"original image provenance mismatch for {sample_id}")
        if acquisition.get("acquisition_status") not in {
            "downloaded", "already_present", "success", "successful", "acquired",
        }:
            raise ValueError(f"assigned source has unsuccessful acquisition: {sample_id}")
        if acquisition.get("sha256") != row.get("image_sha256"):
            raise ValueError(f"source acquisition hash differs from manifest for {sample_id}")
        resolved_image_path = str(image_path.resolve())
        actual_image_hash = verified_image_hashes.get(resolved_image_path)
        if actual_image_hash is None:
            actual_image_hash = _sha256(image_path)
            verified_image_hashes[resolved_image_path] = actual_image_hash
        if actual_image_hash != row.get("image_sha256"):
            raise ValueError(f"local image bytes differ from manifest for {sample_id}")
        row["_source_record"] = source
        row["_resolved_image_path"] = resolved_image_path

    return assigned, quarantined, sources, {
        "manifest_sha256": manifest_sha,
        "audit_report_sha256": audit_sha,
        "audit_report": audit,
        "manifest_record_count": len(manifest),
        "assigned_counts": dict(counts),
        "quarantined_count": len(quarantined),
        "source_record_count": len(sources),
        "original_feature_record_count": len(original_features),
        "local_images_available_for_assigned": len(assigned),
        "verified_protected_artifact_hashes": protected_hashes,
        "unique_local_image_files_verified": len(verified_image_hashes),
    }


def _verify_model_and_checkpoint() -> Tuple[str, str]:
    if OPENCLIP_MODEL != "ViT-B-32-quickgelu" or OPENCLIP_CHECKPOINT != "openai":
        raise ValueError("v2 model configuration is not ViT-B-32-quickgelu/openai")
    model_config = open_clip.get_model_config(OPENCLIP_MODEL)
    pretrained_config = open_clip.get_pretrained_cfg(OPENCLIP_MODEL, OPENCLIP_CHECKPOINT)
    if not model_config or not pretrained_config:
        raise ValueError("OpenCLIP registry does not contain the configured model/checkpoint")
    if model_config.get("quick_gelu") is not True or pretrained_config.get("quick_gelu") is not True:
        raise ValueError("OpenCLIP model and checkpoint QuickGELU settings do not match")
    if model_config.get("embed_dim") != OPENCLIP_DIMENSION:
        raise ValueError("OpenCLIP model embedding dimension is not 512")
    expected_url = (
        "https://openaipublic.azureedge.net/clip/models/"
        f"{EXPECTED_CHECKPOINT_SHA256}/ViT-B-32.pt"
    )
    if pretrained_config.get("url") != expected_url:
        raise ValueError("configured OpenCLIP checkpoint does not resolve to the verified official URL")
    checkpoint_path = Path.home() / ".cache/clip/ViT-B-32.pt"
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"official checkpoint is missing: {checkpoint_path}")
    checkpoint_sha = _sha256(checkpoint_path)
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError(f"checkpoint SHA-256 mismatch: {checkpoint_sha}")
    return str(checkpoint_path), checkpoint_sha


def _select_pilot(records: List[dict]) -> List[dict]:
    targets = {"train": 3, "validation": 3, "test": 2}
    selected = []
    for split in SPLITS:
        selected.extend([record for record in records if record["assigned_split"] == split][:targets[split]])
    if len(selected) != 8 or {row["assigned_split"] for row in selected} != set(SPLITS):
        raise ValueError("unable to select eight assigned pilot samples across all splits")
    return selected


def _sample_for_builder(manifest_record: dict) -> dict:
    source = manifest_record["_source_record"]
    metadata = source.get("metadata") or {}
    return {
        "sample_id": manifest_record["sample_id"],
        "source_reference": source.get("source_reference") or manifest_record["source_id"],
        "split": manifest_record["assigned_split"],
        "label": manifest_record["canonical_label"],
        "text": source.get("text") or metadata.get("clean_title") or "",
        "metadata": {"local_image_path": manifest_record["_resolved_image_path"]},
    }


def _provenance_record(manifest_record: dict, *, checkpoint_sha: str, device: str) -> dict:
    return {
        "manifest_source_file": manifest_record["source_file"],
        "manifest_source_row": manifest_record["source_row"],
        "source_id": manifest_record["source_id"],
        "original_split": manifest_record["original_split"],
        "assigned_split": manifest_record["assigned_split"],
        "component_id": manifest_record["component_id"],
        "image_sha256": manifest_record["image_sha256"],
        "checkpoint_sha256": checkpoint_sha,
        "requested_device": device,
        "model_name": OPENCLIP_MODEL,
        "checkpoint": OPENCLIP_CHECKPOINT,
    }


def _validate_record(record: dict, manifest_record: dict) -> None:
    if record.get("sample_id") != manifest_record["sample_id"]:
        raise ValueError("feature sample ID does not match manifest")
    if record.get("label") != manifest_record["canonical_label"]:
        raise ValueError("feature label does not match manifest")
    identity = record.get("sample_identity") or {}
    if identity.get("split") != manifest_record["assigned_split"]:
        raise ValueError("feature split does not match revised manifest assignment")
    if identity.get("source_reference") != (manifest_record["_source_record"].get("source_reference") or manifest_record["source_id"]):
        raise ValueError("feature source reference does not match acquired source")
    if record.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("feature schema version is not rr-decision-v2")
    if record.get("source_provenance", {}).get("component_id") != manifest_record["component_id"]:
        raise ValueError("feature component provenance does not match manifest")
    modality_status = record.get("modality_status") or {}
    provenance = record.get("modality_provenance") or {}
    RRDecisionV2Features(
        clip_text_embedding=(record.get("predictor_features") or {}).get("clip_text_embedding"),
        clip_image_embedding=(record.get("predictor_features") or {}).get("clip_image_embedding"),
        clip_text_image_cosine=(record.get("predictor_features") or {}).get("clip_text_image_cosine"),
        text_status=modality_status.get("text"),
        image_status=modality_status.get("image"),
        text_provenance=provenance.get("text"),
        image_provenance=provenance.get("image"),
    )
    predictor = record["predictor_features"]
    if tuple(predictor) != PREDICTOR_ALLOWLIST:
        raise ValueError("predictor field names/order differ from the approved allowlist")
    rr = record.get("reasoning_representation")
    if rr is not None:
        if rr.get("contradiction") is not None:
            raise ValueError("v2 similarity-only output must not claim contradiction")
        if rr.get("consistency", {}).get("score") is not None:
            raise ValueError("v2 similarity-only output must not claim consistency")
        if rr.get("reasoning_score") is not None or rr.get("decision_evidence") is not None:
            raise ValueError("v2 similarity-only output must not claim reasoning or decision evidence")
    expected_similarity_count = int(
        predictor.get("clip_text_embedding") is not None
        and predictor.get("clip_image_embedding") is not None
    )
    actual_similarity_count = len((rr or {}).get("pairwise_similarities", []))
    if expected_similarity_count != actual_similarity_count:
        raise ValueError("RR similarity records do not match available modality pair")
    if "label" in predictor or "sample_id" in predictor or "split" in predictor:
        raise ValueError("metadata leaked into predictor features")


def _failure_record(
    manifest_record: dict,
    *,
    checkpoint_sha: str,
    device: str,
    error: Exception,
) -> dict:
    message = " ".join(str(error).split())[:1000]
    modality_provenance = {
        "status": ModalityStatus.UNAVAILABLE.value,
        "model_name": OPENCLIP_MODEL,
        "checkpoint": OPENCLIP_CHECKPOINT,
        "checkpoint_weights_sha256": None,
        "weights_verified": False,
        "dimension": None,
        "shared_model_instance": True,
        "processing": {},
        "error_code": "FEATURE_ARTIFACT_BUILD_FAILED",
        "error_message": message,
    }
    return {
        "sample_id": manifest_record["sample_id"],
        "sample_identity": {
            "sample_id": manifest_record["sample_id"],
            "source_reference": manifest_record["_source_record"].get("source_reference") or manifest_record["source_id"],
            "split": manifest_record["assigned_split"],
        },
        "label": manifest_record["canonical_label"],
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "predictor_features": {
            "clip_text_embedding": None,
            "clip_image_embedding": None,
            "clip_text_image_cosine": None,
        },
        "modality_status": {
            "text": ModalityStatus.UNAVAILABLE.value,
            "image": ModalityStatus.UNAVAILABLE.value,
        },
        "modality_provenance": {
            "text": dict(modality_provenance),
            "image": dict(modality_provenance),
        },
        "reasoning_representation": None,
        "source_provenance": {
            **_provenance_record(manifest_record, checkpoint_sha=checkpoint_sha, device=device),
            "component_id": manifest_record["component_id"],
        },
        "extraction_error": {"type": type(error).__name__, "message": message},
    }


def _record_checkpoint_path(checkpoint_dir: Path, sample_id: str) -> Path:
    safe_name = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    return checkpoint_dir / f"{safe_name}.json"


def _load_checkpoint(path: Path, *, config_fingerprint: str, manifest_record: dict) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    record = envelope.get("record")
    if envelope.get("configuration_fingerprint") != config_fingerprint or not isinstance(record, dict):
        raise ValueError(f"existing record checkpoint has incompatible configuration: {path}")
    record_digest = hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()
    if envelope.get("record_sha256") != record_digest:
        raise ValueError(f"existing record checkpoint failed integrity verification: {path}")
    _validate_record(record, manifest_record)
    return record


def _memory_usage(torch: Any, device: str) -> Dict[str, Optional[int]]:
    rss_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports ru_maxrss in bytes; this runner targets macOS explicitly.
    result: Dict[str, Optional[int]] = {"max_rss_bytes": rss_bytes}
    if device == "mps" and hasattr(torch, "mps"):
        try:
            result["mps_allocated_bytes"] = int(torch.mps.current_allocated_memory())
            result["mps_driver_allocated_bytes"] = int(torch.mps.driver_allocated_memory())
        except (AttributeError, RuntimeError):
            result["mps_allocated_bytes"] = None
            result["mps_driver_allocated_bytes"] = None
    else:
        result["mps_allocated_bytes"] = None
        result["mps_driver_allocated_bytes"] = None
    return result


@contextmanager
def _exclusive_run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _output_jsonl(records: List[dict]) -> bytes:
    return b"".join((_ordered_json(record) + "\n").encode("utf-8") for record in records)


def _audit_phase(
    *,
    records: List[dict],
    manifest_records: List[dict],
    quarantined: List[dict],
    split_paths: Dict[str, Path],
    errors_path: Path,
    checkpoint_sha: str,
) -> Dict[str, Any]:
    by_id = {record["sample_id"]: record for record in manifest_records}
    if len(by_id) != len(manifest_records):
        raise ValueError("duplicate manifest IDs in phase audit set")
    output_records: List[dict] = []
    for split in SPLITS:
        split_rows = _read_jsonl(split_paths[split])
        expected_ids = [row["sample_id"] for row in manifest_records if row["assigned_split"] == split]
        actual_ids = [row.get("sample_id") for row in split_rows]
        if actual_ids != expected_ids:
            raise ValueError(f"{split} output does not reconcile exactly to manifest order")
        for output in split_rows:
            manifest_record = by_id.get(output.get("sample_id"))
            if manifest_record is None:
                raise ValueError(f"unknown sample ID in {split} output: {output.get('sample_id')}")
            _validate_record(output, manifest_record)
            if output["source_provenance"].get("checkpoint_sha256") != checkpoint_sha:
                raise ValueError("record checkpoint provenance mismatch")
            output_records.append(output)
    quarantine_path = split_paths["quarantine"]
    quarantine_rows = _read_jsonl(quarantine_path)
    if [row.get("sample_id") for row in quarantine_rows] != [row["sample_id"] for row in quarantined]:
        raise ValueError("quarantine accounting does not reconcile exactly")
    if set(by_id).intersection(row.get("sample_id") for row in quarantine_rows):
        raise ValueError("quarantined sample appears in an assigned split")
    for row in quarantine_rows:
        if not row.get("quarantined") or row.get("assigned_split") is not None:
            raise ValueError("invalid quarantine accounting record")

    error_rows = _read_jsonl(errors_path)
    expected_errors = [
        record["sample_id"]
        for record in output_records
        if record.get("extraction_error") is not None
    ]
    if [row.get("sample_id") for row in error_rows] != expected_errors:
        raise ValueError("extraction error output does not reconcile to failed records")

    stats: Dict[str, Any] = {
        "processed_records": len(output_records),
        "quarantined_records": len(quarantine_rows),
        "extraction_errors": len(error_rows),
        "per_split": {},
    }
    for split in SPLITS:
        rows = [row for row in output_records if row["sample_identity"]["split"] == split]
        availability = Counter()
        for row in rows:
            text = row["predictor_features"]["clip_text_embedding"] is not None
            image = row["predictor_features"]["clip_image_embedding"] is not None
            availability[("both" if text and image else "text_only" if text else "image_only" if image else "neither")] += 1
        stats["per_split"][split] = {
            "records": len(rows),
            "text_available": sum(row["modality_status"]["text"] == "available" for row in rows),
            "image_available": sum(row["modality_status"]["image"] == "available" for row in rows),
            "both": availability["both"],
            "text_only": availability["text_only"],
            "image_only": availability["image_only"],
            "neither": availability["neither"],
        }
    return stats


def _run_phase(
    *,
    phase: str,
    records: List[dict],
    quarantined: List[dict],
    output_root: Path,
    checkpoint_sha: str,
    device: str,
    config_fingerprint: str,
    encoder: OpenCLIPImageEncoder,
    data_dir: Path,
    metadata: dict,
) -> Dict[str, Any]:
    phase_root = output_root / phase
    checkpoint_dir = phase_root / "record_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    split_paths = {split: phase_root / f"{split}.jsonl" for split in SPLITS}
    split_paths["quarantine"] = phase_root / "quarantine_accounting.jsonl"
    errors_path = phase_root / "extraction_errors.jsonl"
    final_paths = list(split_paths.values()) + [errors_path]
    if metadata.get("phase_runs", {}).get(phase, {}).get("status") == "complete":
        raise FileExistsError(f"{phase} phase is already complete; refusing to rerun it")

    started = time.monotonic()
    phase_info = metadata.setdefault("phase_runs", {}).setdefault(phase, {})
    phase_info.update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "requested_device": device,
        "batch_size": 1,
        "input_records": len(records),
        "last_completed_count": 0,
    })
    _atomic_replace_json(output_root / "experiment_metadata.json", metadata)

    results: Dict[str, dict] = {}
    for index, manifest_record in enumerate(records, 1):
        sample_id = manifest_record["sample_id"]
        checkpoint_path = _record_checkpoint_path(checkpoint_dir, sample_id)
        if checkpoint_path.exists():
            record = _load_checkpoint(
                checkpoint_path,
                config_fingerprint=config_fingerprint,
                manifest_record=manifest_record,
            )
        else:
            try:
                built = build_shared_space_feature_artifact(
                    _sample_for_builder(manifest_record),
                    data_dir=data_dir,
                    encoder=encoder,
                    device=device,
                )
                record = {
                    **built,
                    "sample_id": sample_id,
                    "source_provenance": {
                        **_provenance_record(manifest_record, checkpoint_sha=checkpoint_sha, device=device),
                        "component_id": manifest_record["component_id"],
                    },
                }
                _validate_record(record, manifest_record)
            except Exception as error:
                record = _failure_record(
                    manifest_record,
                    checkpoint_sha=checkpoint_sha,
                    device=device,
                    error=error,
                )
                _validate_record(record, manifest_record)
            envelope = {
                "configuration_fingerprint": config_fingerprint,
                "record_sha256": hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest(),
                "record": record,
            }
            _atomic_write(checkpoint_path, (_ordered_json(envelope) + "\n").encode("utf-8"))
        results[sample_id] = record
        if index == 1 or index % 50 == 0 or index == len(records):
            phase_info["last_completed_count"] = index
            phase_info["memory"] = _memory_usage(__import__("torch"), device)
            _atomic_replace_json(output_root / "experiment_metadata.json", metadata)
            print(
                f"{phase}: {index}/{len(records)} records "
                f"elapsed_seconds={time.monotonic() - started:.1f} "
                f"memory={phase_info['memory']}",
                flush=True,
            )

    ordered_records = [results[row["sample_id"]] for row in records]
    for split in SPLITS:
        selected = [record for record in ordered_records if record["sample_identity"]["split"] == split]
        _atomic_write(split_paths[split], _output_jsonl(selected))
    _atomic_write(
        split_paths["quarantine"],
        _output_jsonl(quarantined),
    )
    errors = [
        {
            "sample_id": record["sample_id"],
            "split": record["sample_identity"]["split"],
            "error": record["extraction_error"],
        }
        for record in ordered_records
        if record.get("extraction_error") is not None
    ]
    _atomic_write(errors_path, _output_jsonl(errors))
    audit = _audit_phase(
        records=ordered_records,
        manifest_records=records,
        quarantined=quarantined,
        split_paths=split_paths,
        errors_path=errors_path,
        checkpoint_sha=checkpoint_sha,
    )

    output_files = {}
    for path in final_paths:
        output_files[str(path.relative_to(output_root))] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    audit.update({
        "phase": phase,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "device": encoder.resolved_device,
        "batch_size": 1,
        "memory": _memory_usage(__import__("torch"), device),
        "output_files": output_files,
    })
    audit_path = phase_root / "audit_report.json"
    _atomic_replace_json(audit_path, audit)
    phase_info.update({
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "last_completed_count": len(records),
        "elapsed_seconds": audit["elapsed_seconds"],
        "resolved_device": encoder.resolved_device,
        "extraction_errors": audit["extraction_errors"],
        "per_split": audit["per_split"],
        "pilot_sample_ids": [row["sample_id"] for row in records] if phase == "pilot" else None,
        "audit_report_sha256": _sha256(audit_path),
        "output_files": output_files,
    })
    if phase == "pilot":
        average_row_bytes = sum(info["size_bytes"] for key, info in output_files.items() if key.endswith(".jsonl") and key != "quarantine_accounting.jsonl") / max(1, len(records))
        estimated_outputs = int(average_row_bytes * sum(EXPECTED_COUNTS.values()) * 1.4)
        free_bytes = shutil.disk_usage(output_root).free
        phase_info["estimated_full_output_bytes_with_checkpoint_headroom"] = estimated_outputs * 2
        phase_info["free_disk_bytes_after_pilot"] = free_bytes
        if free_bytes < estimated_outputs * 2:
            phase_info["status"] = "pilot_failed_insufficient_disk"
            _atomic_replace_json(output_root / "experiment_metadata.json", metadata)
            raise OSError("insufficient disk space for conservative full output estimate")
        if audit["extraction_errors"] or any(
            counts["text_available"] != counts["records"]
            or counts["image_available"] != counts["records"]
            or counts["both"] != counts["records"]
            for counts in audit["per_split"].values()
            if counts["records"]
        ):
            phase_info["status"] = "pilot_failed_feature_availability"
            _atomic_replace_json(output_root / "experiment_metadata.json", metadata)
            raise RuntimeError("pilot did not produce valid text and image embeddings for every sample")
    _atomic_replace_json(output_root / "experiment_metadata.json", metadata)
    return audit


def run_extraction(
    *,
    phase: str,
    service_root: Path,
    output_root: Path,
    device: str,
) -> Dict[str, Any]:
    if phase not in {"pilot", "full"}:
        raise ValueError("phase must be 'pilot' or 'full'")
    if device not in {"mps", "cpu"}:
        raise ValueError("device must be 'mps' or 'cpu'")
    if output_root.exists() and not (output_root / "experiment_metadata.json").is_file():
        if any(output_root.iterdir()):
            raise FileExistsError(f"experiment directory is not empty: {output_root}")
    service_root = service_root.resolve()
    output_root = output_root.resolve()
    manifest_path = service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    audit_path = service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json"
    checkpoint_path, checkpoint_sha = _verify_model_and_checkpoint()
    assigned, quarantined, _, input_info = _load_inputs(
        service_root=service_root,
        manifest_path=manifest_path,
        audit_path=audit_path,
    )
    if output_root.exists() and (output_root / "experiment_metadata.json").exists():
        metadata = json.loads((output_root / "experiment_metadata.json").read_text(encoding="utf-8"))
        if metadata.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError("existing experiment metadata has a different experiment ID")
    else:
        if output_root.exists() and any(output_root.iterdir()):
            raise FileExistsError(f"experiment directory is not empty: {output_root}")
        output_root.mkdir(parents=True, exist_ok=True)
        config = {
            "experiment_id": EXPERIMENT_ID,
            "schema_version": FEATURE_SCHEMA_VERSION,
            "model_name": OPENCLIP_MODEL,
            "checkpoint": OPENCLIP_CHECKPOINT,
            "checkpoint_sha256": checkpoint_sha,
            "manifest_sha256": input_info["manifest_sha256"],
            "audit_report_sha256": input_info["audit_report_sha256"],
            "device": device,
            "batch_size": 1,
            "predictor_allowlist": list(PREDICTOR_ALLOWLIST),
        }
        fingerprint = hashlib.sha256(_canonical_json(config).encode("utf-8")).hexdigest()
        metadata = {
            "experiment_id": EXPERIMENT_ID,
            "schema_version": FEATURE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "software_versions": _runtime_versions(),
            "model": {
                "architecture": OPENCLIP_MODEL,
                "pretrained_configuration": OPENCLIP_CHECKPOINT,
                "checkpoint_path": checkpoint_path,
                "checkpoint_sha256": checkpoint_sha,
            },
            "inputs": {
                "manifest_path": str(manifest_path),
                "manifest_sha256": input_info["manifest_sha256"],
                "audit_report_path": str(audit_path),
                "audit_report_sha256": input_info["audit_report_sha256"],
                "assigned_counts": EXPECTED_COUNTS,
                "assigned_total": sum(EXPECTED_COUNTS.values()),
                "quarantined_total": EXPECTED_QUARANTINED,
                "source_record_count": input_info["source_record_count"],
                "original_feature_record_count": input_info["original_feature_record_count"],
                "local_images_available_for_assigned": input_info["local_images_available_for_assigned"],
                "protected_artifact_hashes": input_info["verified_protected_artifact_hashes"],
                "unique_local_image_files_verified": input_info["unique_local_image_files_verified"],
            },
            "feature_builder_configuration": {
                "function": "build_shared_space_feature_artifact",
                "data_dir": str(service_root / "data/research/fakeddit"),
                "predictor_allowlist": list(PREDICTOR_ALLOWLIST),
                "tokenizer_context_length": 77,
                "truncation_policy": "preserve_start_end_tokens_truncate_body_to_context_minus_2-v1",
                "alignment_mode": "similarity_only",
            },
            "run_configuration": config,
            "configuration_fingerprint": fingerprint,
            "phase_runs": {},
        }
        _atomic_write(output_root / "experiment_metadata.json", (_canonical_json(metadata) + "\n").encode("utf-8"))

    expected_config = metadata.get("run_configuration") or {}
    run_config = {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": FEATURE_SCHEMA_VERSION,
        "model_name": OPENCLIP_MODEL,
        "checkpoint": OPENCLIP_CHECKPOINT,
        "checkpoint_sha256": checkpoint_sha,
        "manifest_sha256": input_info["manifest_sha256"],
        "audit_report_sha256": input_info["audit_report_sha256"],
        "device": device,
        "batch_size": 1,
        "predictor_allowlist": list(PREDICTOR_ALLOWLIST),
    }
    config_fingerprint = hashlib.sha256(_canonical_json(run_config).encode("utf-8")).hexdigest()
    if expected_config != run_config or metadata.get("configuration_fingerprint") != config_fingerprint:
        raise ValueError("resume configuration differs from the original experiment configuration")

    if phase == "full":
        pilot = metadata.get("phase_runs", {}).get("pilot", {})
        if pilot.get("status") != "complete" or pilot.get("extraction_errors") not in (None, 0):
            raise ValueError("full extraction requires a completed, passing eight-record pilot")
        if pilot.get("requested_device") != device:
            raise ValueError("full extraction device must match the successful pilot device")

    phase_records = _select_pilot(assigned) if phase == "pilot" else assigned
    run_path = output_root / ".experiment.lock"
    with _exclusive_run_lock(run_path):
        encoder = OpenCLIPImageEncoder(settings=Settings(
            image_encoder_model=OPENCLIP_MODEL,
            image_encoder_checkpoint=OPENCLIP_CHECKPOINT,
            image_encoder_device=device,
            image_encoder_batch_size=1,
        ))
        result = _run_phase(
            phase=phase,
            records=phase_records,
            quarantined=quarantined,
            output_root=output_root,
            checkpoint_sha=checkpoint_sha,
            device=device,
            config_fingerprint=config_fingerprint,
            encoder=encoder,
            data_dir=service_root / "data/research/fakeddit",
            metadata=metadata,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("pilot", "full"), required=True)
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        default=Path("data/research/fakeddit-experiments/task36c-v2-shared-space"),
    )
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()
    if args.batch_size != 1:
        parser.error("Task 36C pilot/full run requires batch size 1")
    result = run_extraction(
        phase=args.phase,
        service_root=Path.cwd(),
        output_root=args.experiment_dir,
        device=args.device,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
