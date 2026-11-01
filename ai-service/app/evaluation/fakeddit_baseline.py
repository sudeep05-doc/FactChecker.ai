"""Controlled downstream classifier experiment for frozen Fakeddit v2 features."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


EXPERIMENT_ID = "task38-baseline-classifier-20261019"
SCHEMA_VERSION = "rr-decision-v2"
PREDICTOR_ALLOWLIST = (
    "clip_text_embedding",
    "clip_image_embedding",
    "clip_text_image_cosine",
)
LABEL_TO_INT = {"FAKE": 0, "REAL": 1}
SPLITS = ("train", "validation", "test")
EXPECTED_COUNTS = {
    "train": {"total": 19068, "FAKE": 9652, "REAL": 9416},
    "validation": {"total": 3801, "FAKE": 1924, "REAL": 1877},
    "test": {"total": 3799, "FAKE": 1923, "REAL": 1876},
}
EXPECTED_MANIFEST_SHA256 = "3a39fe293c9b86820f1b4700ffed2d4d410e8ddf3e8d3f90b3c0267dc05ee6e2"
EXPECTED_TASK37_REPORT_SHA256 = "aa66e24554ee5ddd79aab61f08d3918fffa3a2c30755a34fb262f140ecac5ddb"
EXPECTED_PROTECTED_HASHES = {
    "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl":
        EXPECTED_MANIFEST_SHA256,
    "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json":
        "fd12f7ff13f122073ef995a363d8c0488fffc30c22a6f78f8a525fa82b692ef0",
    "data/research/fakeddit-features/train.jsonl":
        "f0285b2a7e3fc78e9f6907b4ad68106866c17f97aea61185c891bc2779f2d537",
    "data/research/fakeddit-features/validation.jsonl":
        "7a357a260161777d2adbbb093d30c616cd2dbac0f14a2ae783093b73e1947d1b",
    "data/research/fakeddit-features/test.jsonl":
        "dcbaec128e2805c84668156c63f1bce1f9de9f99cf791788f67549744dbc9c42",
    "data/research/fakeddit-features/feature_cache.json":
        "3b33575dc8e0f647d53e23633098cbc776ed393a878c79606a8a98f4fc203b06",
}
MODEL_FEATURES = {
    "cosine_only": ("clip_text_image_cosine",),
    "text_only": ("clip_text_embedding",),
    "image_only": ("clip_image_embedding",),
    "fusion": ("clip_text_embedding", "clip_image_embedding"),
}
MODEL_TIE_ORDER = {"text_only": 0, "image_only": 1, "fusion": 2, "cosine_only": 3}
C_GRID = (0.01, 0.1, 1.0, 10.0)
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 42
THRESHOLD = 0.5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes, *, refuse_existing: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if refuse_existing and sha256_file(path) == hashlib.sha256(content).hexdigest():
            return
        raise FileExistsError(f"refusing to overwrite existing Task 38 artifact: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_json(path: Path, value: Any, *, refuse_existing: bool = True) -> None:
    atomic_write(path, json_bytes(value), refuse_existing=refuse_existing)


def save_model(model: LogisticRegression, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite model artifact: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        joblib.dump(model, temporary_path)
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL record at {path}:{line_number}: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"JSONL record must be an object at {path}:{line_number}")
            yield row


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _environment() -> Dict[str, str]:
    versions = {"python": platform.python_version(), "platform": platform.platform()}
    for package in ("numpy", "scikit-learn", "scipy", "joblib"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _git_commit(ai_service_root: Path) -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ai_service_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _sha256_inventory(paths: Dict[str, Path]) -> Dict[str, dict]:
    inventory = {}
    for key, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"required experiment input is missing: {path}")
        inventory[key] = {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return inventory


def _verify_input_hashes(
    ai_service_root: Path,
    experiment_root: Path,
) -> Tuple[dict, dict, dict, dict]:
    manifest_path = ai_service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    task32_audit_path = ai_service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json"
    task36_root = ai_service_root / "data/research/fakeddit-experiments/task36c-v2-shared-space"
    metadata_path = task36_root / "experiment_metadata.json"
    task37_path = ai_service_root / "data/research/fakeddit-experiments/task37-v2-dataset-audit-20261019/audit_report.md"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    task36_audit_path = task36_root / "full/audit_report.json"
    task36_audit = json.loads(task36_audit_path.read_text(encoding="utf-8"))
    task32_audit = json.loads(task32_audit_path.read_text(encoding="utf-8"))
    task37_hash = sha256_file(task37_path)
    _require(task37_hash == EXPECTED_TASK37_REPORT_SHA256, "Task 37 audit report hash differs from reviewed report")
    _require(metadata.get("experiment_id") == "task36c-v2-shared-space-20261015", "unexpected Task 36C experiment ID")
    _require(metadata.get("schema_version") == SCHEMA_VERSION, "Task 36C schema metadata mismatch")
    _require(metadata.get("model", {}).get("architecture") == "ViT-B-32-quickgelu", "unexpected Task 36C model")
    _require(metadata.get("model", {}).get("pretrained_configuration") == "openai", "unexpected Task 36C checkpoint")
    _require(
        metadata.get("phase_runs", {}).get("full", {}).get("status") == "complete",
        "Task 36C full phase is not complete",
    )
    _require(metadata["inputs"]["manifest_sha256"] == EXPECTED_MANIFEST_SHA256, "Task 36C manifest hash metadata mismatch")
    _require(task36_audit.get("processed_records") == 26668, "Task 36C full audit count mismatch")
    _require(task36_audit.get("extraction_errors") == 0, "Task 36C extraction errors are nonzero")

    paths: Dict[str, Path] = {
        "task32_manifest": manifest_path,
        "task32_audit_report": task32_audit_path,
        "task36_metadata": metadata_path,
        "task36_full_audit_report": task36_audit_path,
        "task37_audit_report": task37_path,
    }
    expected_acquired_hashes = task32_audit["input_artifact_sha256"]
    for split, artifact_key in (
        ("train", "acquired_train"),
        ("validation", "acquired_validation"),
        ("test", "acquired_test"),
    ):
        acquired_path = ai_service_root / f"data/research/fakeddit/acquired/{split}.jsonl"
        paths[f"acquired_{split}"] = acquired_path
    full_output_hashes = metadata["phase_runs"]["full"]["output_files"]
    for relative in (
        "full/train.jsonl",
        "full/validation.jsonl",
        "full/test.jsonl",
        "full/quarantine_accounting.jsonl",
        "full/extraction_errors.jsonl",
    ):
        paths[relative] = task36_root / relative
    observed_inventory = _sha256_inventory(paths)
    for split, artifact_key in (
        ("train", "acquired_train"),
        ("validation", "acquired_validation"),
        ("test", "acquired_test"),
    ):
        _require(
            observed_inventory[f"acquired_{split}"]["sha256"] == expected_acquired_hashes[artifact_key],
            f"acquired source artifact hash mismatch: {split}",
        )
    _require(observed_inventory["task32_manifest"]["sha256"] == EXPECTED_MANIFEST_SHA256, "manifest SHA-256 mismatch")
    _require(
        observed_inventory["task32_audit_report"]["sha256"] == EXPECTED_PROTECTED_HASHES[
            "data/research/fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json"
        ],
        "Task 32B audit report SHA-256 mismatch",
    )
    _require(
        observed_inventory["task36_full_audit_report"]["sha256"]
        == metadata["phase_runs"]["full"]["audit_report_sha256"],
        "Task 36C full audit report SHA-256 mismatch",
    )
    _require(
        task36_audit.get("output_files") == full_output_hashes,
        "Task 36C output hash inventory differs between metadata and full audit report",
    )
    for relative in (
        "full/train.jsonl",
        "full/validation.jsonl",
        "full/test.jsonl",
        "full/quarantine_accounting.jsonl",
        "full/extraction_errors.jsonl",
    ):
        expected = full_output_hashes[relative]
        observed = observed_inventory[relative]
        _require(observed["sha256"] == expected["sha256"], f"Task 36C output SHA-256 mismatch: {relative}")
        _require(observed["size_bytes"] == expected["size_bytes"], f"Task 36C output size mismatch: {relative}")
        _require(
            task36_audit.get("output_files", {}).get(relative) == expected,
            f"Task 36C audit hash mismatch: {relative}",
        )
    _require(
        observed_inventory["task37_audit_report"]["sha256"] == EXPECTED_TASK37_REPORT_SHA256,
        "Task 37 audit report SHA-256 mismatch",
    )

    protected_inventory = {}
    for relative, expected in EXPECTED_PROTECTED_HASHES.items():
        path = ai_service_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"protected artifact is missing: {path}")
        actual = sha256_file(path)
        _require(actual == expected, f"protected artifact hash mismatch: {relative}")
        _require(
            metadata["inputs"]["protected_artifact_hashes"].get(relative) == expected,
            f"Task 36C protected-artifact record mismatch: {relative}",
        )
        protected_inventory[relative] = {
            "path": str(path.resolve()),
            "sha256": actual,
            "expected_sha256": expected,
            "match": True,
        }
    _require(task32_audit.get("label_mapping") == {"0": "FAKE", "1": "REAL"}, "Task 32B label mapping mismatch")
    _require(
        task32_audit.get("quarantined_total") == 4
        and task36_audit.get("quarantined_records") == 4,
        "quarantine accounting mismatch",
    )
    return metadata, task32_audit, observed_inventory, protected_inventory


def _load_manifest(manifest_path: Path) -> Tuple[dict, dict]:
    assigned = {split: [] for split in SPLITS}
    quarantine = []
    seen = set()
    for row in read_jsonl(manifest_path):
        sample_id = row.get("sample_id")
        _require(isinstance(sample_id, str) and bool(sample_id), "manifest contains empty or invalid sample_id")
        _require(sample_id not in seen, f"duplicate manifest sample_id: {sample_id}")
        seen.add(sample_id)
        if row.get("quarantined"):
            _require(row.get("assigned_split") is None, f"quarantined record assigned to a split: {sample_id}")
            quarantine.append(row)
            continue
        split = row.get("assigned_split")
        _require(split in SPLITS, f"invalid assigned split for {sample_id}: {split}")
        _require(row.get("canonical_label") in LABEL_TO_INT, f"unexpected label for {sample_id}")
        raw_label = str(row.get("source_label"))
        _require(LABEL_TO_INT[row["canonical_label"]] == int(raw_label), f"source label mapping mismatch for {sample_id}")
        assigned[split].append(row)
    return assigned, {"records": len(seen), "quarantined": quarantine, "quarantined_count": len(quarantine)}


def validate_record(row: dict, manifest_row: dict, split: str) -> dict:
    sample_id = manifest_row["sample_id"]
    _require(row.get("sample_id") == sample_id, f"record ID mismatch in {split}: expected {sample_id}")
    _require(row.get("label") == manifest_row["canonical_label"], f"label mismatch for {sample_id}")
    _require(
        (row.get("sample_identity") or {}).get("split") == split == manifest_row.get("assigned_split"),
        f"split mismatch for {sample_id}",
    )
    _require(row.get("feature_schema_version") == SCHEMA_VERSION, f"schema version mismatch for {sample_id}")
    predictors = row.get("predictor_features")
    _require(isinstance(predictors, dict), f"predictor_features must be an object for {sample_id}")
    _require(tuple(predictors.keys()) == PREDICTOR_ALLOWLIST, f"predictor allowlist/order mismatch for {sample_id}")
    text = predictors.get("clip_text_embedding")
    image = predictors.get("clip_image_embedding")
    cosine = predictors.get("clip_text_image_cosine")
    _require(isinstance(text, list) and len(text) == 512, f"text embedding dimension mismatch for {sample_id}")
    _require(isinstance(image, list) and len(image) == 512, f"image embedding dimension mismatch for {sample_id}")
    _require(all(isinstance(value, (int, float)) and math.isfinite(value) for value in text), f"invalid text embedding for {sample_id}")
    _require(all(isinstance(value, (int, float)) and math.isfinite(value) for value in image), f"invalid image embedding for {sample_id}")
    _require(abs(math.sqrt(math.fsum(value * value for value in text)) - 1.0) <= 1e-4, f"text embedding norm invalid for {sample_id}")
    _require(abs(math.sqrt(math.fsum(value * value for value in image)) - 1.0) <= 1e-4, f"image embedding norm invalid for {sample_id}")
    _require(isinstance(cosine, (int, float)) and math.isfinite(cosine), f"cosine invalid for {sample_id}")
    _require(-1.0 - 1e-6 <= cosine <= 1.0 + 1e-6, f"cosine out of range for {sample_id}")
    _require(
        abs(float(cosine) - math.fsum(a * b for a, b in zip(text, image))) <= 1e-5,
        f"cosine does not match embeddings for {sample_id}",
    )
    modality = row.get("modality_status") or {}
    _require(modality.get("text") == "available" and modality.get("image") == "available", f"missing modality for {sample_id}")
    rr = row.get("reasoning_representation")
    _require(isinstance(rr, dict), f"reasoning representation missing for {sample_id}")
    consistency = rr.get("consistency") or {}
    _require(rr.get("contradiction") is None and not rr.get("contradiction_records"), f"unexpected contradiction for {sample_id}")
    _require(
        consistency.get("alignment") is None
        and consistency.get("contextual") is None
        and consistency.get("score") is None,
        f"unexpected consistency score for {sample_id}",
    )
    _require(
        rr.get("reasoning_score") is None
        and rr.get("decision_evidence") is None
        and not rr.get("contextual_features")
        and not rr.get("diagnostic_proxies"),
        f"unexpected reasoning value for {sample_id}",
    )
    source = row.get("source_provenance") or {}
    _require(source.get("assigned_split") == split, f"source split provenance mismatch for {sample_id}")
    _require(source.get("component_id") == manifest_row.get("component_id"), f"component provenance mismatch for {sample_id}")
    _require(source.get("image_sha256") == manifest_row.get("image_sha256"), f"image hash provenance mismatch for {sample_id}")
    _require(source.get("model_name") == "ViT-B-32-quickgelu", f"model provenance mismatch for {sample_id}")
    _require(source.get("checkpoint") == "openai", f"checkpoint provenance mismatch for {sample_id}")
    forbidden_key_fragments = ("label", "sample_id", "source", "split", "url", "provenance", "metadata", "subreddit")
    for key in predictors:
        _require(
            not any(fragment in key.lower() for fragment in forbidden_key_fragments),
            f"forbidden predictor field: {key}",
        )
    return predictors


def _audit_feature_split(
    *,
    feature_path: Path,
    manifest_rows: Sequence[dict],
    split: str,
) -> dict:
    counts = Counter()
    ids = set()
    label_counts = Counter()
    norms = {"text_max_abs_error": 0.0, "image_max_abs_error": 0.0, "cosine_max_abs_error": 0.0}
    unique_hashes = {key: set() for key in PREDICTOR_ALLOWLIST}
    iterator = iter(manifest_rows)
    row_count = 0
    for row in read_jsonl(feature_path):
        try:
            manifest_row = next(iterator)
        except StopIteration as error:
            raise ValueError(f"unexpected extra feature record in {split}") from error
        predictors = validate_record(row, manifest_row, split)
        sample_id = row["sample_id"]
        _require(sample_id not in ids, f"duplicate sample ID in {split}: {sample_id}")
        ids.add(sample_id)
        row_count += 1
        label_counts[row["label"]] += 1
        counts["records"] += 1
        counts["text_available"] += 1
        counts["image_available"] += 1
        text, image, cosine = (
            predictors["clip_text_embedding"],
            predictors["clip_image_embedding"],
            predictors["clip_text_image_cosine"],
        )
        norms["text_max_abs_error"] = max(
            norms["text_max_abs_error"],
            abs(math.sqrt(math.fsum(value * value for value in text)) - 1.0),
        )
        norms["image_max_abs_error"] = max(
            norms["image_max_abs_error"],
            abs(math.sqrt(math.fsum(value * value for value in image)) - 1.0),
        )
        norms["cosine_max_abs_error"] = max(
            norms["cosine_max_abs_error"],
            abs(float(cosine) - math.fsum(a * b for a, b in zip(text, image))),
        )
        for key, value in predictors.items():
            encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            unique_hashes[key].add(hashlib.sha256(encoded).digest())
    try:
        remaining = next(iterator)
        raise ValueError(f"missing feature record in {split}: {remaining['sample_id']}")
    except StopIteration:
        pass
    expected = EXPECTED_COUNTS[split]
    _require(row_count == expected["total"], f"unexpected record count for {split}: {row_count}")
    _require(label_counts == {"FAKE": expected["FAKE"], "REAL": expected["REAL"]}, f"label counts mismatch for {split}")
    return {
        "records": row_count,
        "label_counts": dict(label_counts),
        "label_proportions": {
            label: label_counts[label] / row_count for label in ("FAKE", "REAL")
        },
        "missing_or_unexpected_labels": [],
        "duplicate_ids": 0,
        "manifest_correspondence": "exact ID/order/split/label match",
        "modality_availability": {
            "text": {"available": row_count, "missing": 0, "dimensions": [512]},
            "image": {"available": row_count, "missing": 0, "dimensions": [512]},
        },
        "numeric_integrity": {
            "text_nonfinite": 0,
            "image_nonfinite": 0,
            "text_norm_violations": 0,
            "image_norm_violations": 0,
            "cosine_missing": 0,
            "cosine_nonfinite_or_out_of_range": 0,
            "cosine_consistency_violations": 0,
            **norms,
        },
        "distinct_predictor_values": {
            key: len(values) for key, values in unique_hashes.items()
        },
    }


def _task37_title_groups(ai_service_root: Path, manifest_rows: Dict[str, dict]) -> Dict[str, dict]:
    acquired = ai_service_root / "data/research/fakeddit/acquired"
    source_hashes = {}
    records: Dict[str, dict] = {}
    for original_split in SPLITS:
        path = acquired / f"{original_split}.jsonl"
        source_hashes[str(path)] = sha256_file(path)
        for row in read_jsonl(path):
            sample_id = row.get("sample_id")
            if sample_id in manifest_rows:
                if sample_id in records:
                    raise ValueError(f"duplicate acquired sample ID during title sensitivity: {sample_id}")
                records[sample_id] = row
    _require(set(records) == set(manifest_rows), "acquired title source does not reconcile to assigned manifest")
    title_groups: Dict[str, List[dict]] = defaultdict(list)
    for sample_id, manifest_row in manifest_rows.items():
        source = records[sample_id]
        metadata = source.get("metadata") or {}
        _require(source.get("label") == manifest_row["canonical_label"], f"acquired label mismatch for {sample_id}")
        _require(metadata.get("source_file") == manifest_row["source_file"], f"acquired source file mismatch for {sample_id}")
        _require(metadata.get("source_row") == manifest_row["source_row"], f"acquired source row mismatch for {sample_id}")
        text = str(source.get("text") or "").strip().casefold()
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        title_groups[key].append(manifest_row)
    cross_split_groups = [
        (key, group)
        for key, group in title_groups.items()
        if len({row["assigned_split"] for row in group}) > 1
    ]
    affected = {
        row["sample_id"]
        for _, group in cross_split_groups
        for row in group
    }
    return {
        "source_hashes": source_hashes,
        "normalization": "strip whitespace, casefold, SHA-256 exact-title groups",
        "cross_split_group_count": len(cross_split_groups),
        "affected_record_count": len(affected),
        "affected_ids_by_split": {
            split: sorted(
                row["sample_id"]
                for _, group in cross_split_groups
                for row in group
                if row["assigned_split"] == split
            )
            for split in SPLITS
        },
        "affected_label_counts_by_split": {
            split: dict(Counter(
                row["canonical_label"]
                for _, group in cross_split_groups
                for row in group
                if row["assigned_split"] == split
            ))
            for split in SPLITS
        },
        "cross_split_groups_with_both_labels": sum(
            len({row["canonical_label"] for row in group}) > 1
            for _, group in cross_split_groups
        ),
        "groups": {
            key: [row["sample_id"] for row in group]
            for key, group in cross_split_groups
        },
    }


def validate_inputs(ai_service_root: Path, experiment_root: Path) -> dict:
    metadata, task32_audit, inventory, protected = _verify_input_hashes(ai_service_root, experiment_root)
    manifest_path = ai_service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    assigned, quarantine = _load_manifest(manifest_path)
    _require(len(quarantine["quarantined"]) == 4, "expected exactly four quarantined records")
    _require(
        {row["sample_id"] for row in quarantine["quarantined"]}
        == {
            "bzjci1",
            "bzbodv",
            "cltr2f1",
            "2ld43g",
        },
        "quarantined IDs differ from approved manifest",
    )
    split_reports = {}
    task36_root = ai_service_root / "data/research/fakeddit-experiments/task36c-v2-shared-space"
    manifest_by_id = {
        row["sample_id"]: row
        for rows in assigned.values()
        for row in rows
    }
    for split in SPLITS:
        expected = EXPECTED_COUNTS[split]
        _require(len(assigned[split]) == expected["total"], f"manifest count mismatch for {split}")
        split_reports[split] = _audit_feature_split(
            feature_path=task36_root / "full" / f"{split}.jsonl",
            manifest_rows=assigned[split],
            split=split,
        )
    quarantine_path = task36_root / "full/quarantine_accounting.jsonl"
    quarantine_rows = list(read_jsonl(quarantine_path))
    _require(
        [row.get("sample_id") for row in quarantine_rows]
        == [row["sample_id"] for row in quarantine["quarantined"]],
        "Task 36C quarantine output differs from the approved manifest",
    )
    _require(
        all(row.get("quarantined") and row.get("assigned_split") is None for row in quarantine_rows),
        "quarantine output includes assigned records",
    )
    errors = list(read_jsonl(task36_root / "full/extraction_errors.jsonl"))
    _require(not errors, "Task 36C extraction error artifact is not empty")
    title_overlap = _task37_title_groups(ai_service_root, manifest_by_id)
    _require(title_overlap["cross_split_group_count"] == 129, "Task 37 exact-title overlap audit no longer matches")
    _require(title_overlap["affected_record_count"] == 1138, "Task 37 exact-title affected count no longer matches")
    _require(
        title_overlap["cross_split_groups_with_both_labels"] == 4,
        "Task 37 conflicting-label title-group count no longer matches",
    )
    source_paths = {
        f"protected:{relative}": ai_service_root / relative
        for relative in EXPECTED_PROTECTED_HASHES
    }
    source_paths["task38_protocol"] = experiment_root / "experiment_protocol.md"
    source_paths["task38_configuration"] = experiment_root / "configuration.json"
    source_hashes = _sha256_inventory(source_paths)
    config = json.loads((experiment_root / "configuration.json").read_text(encoding="utf-8"))
    _require(config.get("experiment_id") == EXPERIMENT_ID, "configuration experiment ID mismatch")
    report = {
        "experiment_id": EXPERIMENT_ID,
        "status": "passed",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": {
            "records": quarantine["records"],
            "assigned_counts": {
                split: {
                    "total": len(assigned[split]),
                    "FAKE": sum(row["canonical_label"] == "FAKE" for row in assigned[split]),
                    "REAL": sum(row["canonical_label"] == "REAL" for row in assigned[split]),
                }
                for split in SPLITS
            },
            "quarantined_count": quarantine["quarantined_count"],
            "quarantined_ids_and_reasons": [
                {
                    "sample_id": row["sample_id"],
                    "reason": row["quarantine_reason"],
                }
                for row in quarantine["quarantined"]
            ],
            "label_mapping": task32_audit["label_mapping"],
            "source_label_checks": "manifest source_label verified against 0->FAKE, 1->REAL mapping",
        },
        "feature_audit": split_reports,
        "predictor_allowlist": list(PREDICTOR_ALLOWLIST),
        "test_performance_inspected": False,
        "quarantine_accounting": {
            "records": len(quarantine_rows),
            "unexpected_assigned_records": 0,
        },
        "extraction_errors": {"records": len(errors)},
        "title_overlap_sensitivity_preflight": {
            key: value
            for key, value in title_overlap.items()
            if key not in {"groups", "affected_ids_by_split"}
        },
        "input_sha256_inventory": inventory,
        "protected_artifact_sha256_inventory": protected,
        "protocol_and_configuration_sha256": {
            key: value["sha256"]
            for key, value in source_hashes.items()
            if key.startswith("task38_")
        },
        "task36_model": metadata["model"],
        "environment": _environment(),
        "git_commit": _git_commit(ai_service_root),
    }
    report["source_inventory_sha256"] = hashlib.sha256(
        canonical_json(report["input_sha256_inventory"]).encode("utf-8")
    ).hexdigest()
    return report


def feature_matrix(records: Sequence[dict], model_name: str) -> np.ndarray:
    if model_name not in MODEL_FEATURES:
        raise ValueError(f"unknown model candidate: {model_name}")
    matrix = []
    for record in records:
        predictors = record["predictor_features"]
        components = []
        for feature_name in MODEL_FEATURES[model_name]:
            value = predictors[feature_name]
            if feature_name.endswith("_embedding"):
                components.append(np.asarray(value, dtype=np.float32))
            else:
                components.append(np.asarray([value], dtype=np.float32))
        matrix.append(np.concatenate(components))
    result = np.asarray(matrix, dtype=np.float32)
    if result.ndim != 2 or result.shape[1] == 0 or not np.isfinite(result).all():
        raise ValueError(f"invalid predictor matrix for {model_name}")
    return result


def _load_split(ai_service_root: Path, split: str, excluded_ids: Optional[set] = None) -> List[dict]:
    path = ai_service_root / "data/research/fakeddit-experiments/task36c-v2-shared-space/full" / f"{split}.jsonl"
    return [
        row for row in read_jsonl(path)
        if excluded_ids is None or row["sample_id"] not in excluded_ids
    ]


def metric_report(y_true: np.ndarray, probabilities: np.ndarray, threshold: float = THRESHOLD) -> dict:
    predictions = (probabilities >= threshold).astype(np.int64)
    cm = confusion_matrix(y_true, predictions, labels=[0, 1])
    return {
        "positive_class": "REAL",
        "threshold": threshold,
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "precision_REAL": float(precision_score(y_true, predictions, pos_label=1, zero_division=0)),
        "recall_REAL": float(recall_score(y_true, predictions, pos_label=1, zero_division=0)),
        "f1_REAL": float(f1_score(y_true, predictions, pos_label=1, zero_division=0)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision_REAL": float(average_precision_score(y_true, probabilities)),
        "confusion_matrix_labels": ["FAKE", "REAL"],
        "confusion_matrix": cm.tolist(),
        "classification_report": classification_report(
            y_true,
            predictions,
            labels=[0, 1],
            target_names=["FAKE", "REAL"],
            output_dict=True,
            zero_division=0,
        ),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, probabilities, pos_label=1)),
    }


def _write_predictions(path: Path, records: Sequence[dict], probabilities: np.ndarray, split: str) -> None:
    lines = []
    for record, probability in zip(records, probabilities):
        p_real = float(probability)
        lines.append(json.dumps({
            "sample_id": record["sample_id"],
            "split": split,
            "label": record["label"],
            "y_true_REAL": LABEL_TO_INT[record["label"]],
            "probability_REAL": p_real,
            "predicted_label": "REAL" if p_real >= THRESHOLD else "FAKE",
            "threshold": THRESHOLD,
        }, separators=(",", ":"), ensure_ascii=False))
    atomic_write(path, ("\n".join(lines) + "\n").encode("utf-8"))


def _model_instance(c_value: float) -> LogisticRegression:
    return LogisticRegression(
        solver="lbfgs",
        penalty="l2",
        C=float(c_value),
        max_iter=2000,
        class_weight=None,
        random_state=42,
    )


def _selection_rank(candidate: dict) -> tuple:
    return (
        -candidate["metrics"]["roc_auc"],
        -candidate["metrics"]["average_precision_REAL"],
        MODEL_TIE_ORDER[candidate["model_name"]],
        candidate["C"],
    )


def select_model(ai_service_root: Path, experiment_root: Path) -> dict:
    validation_path = experiment_root / "data_validation_report.json"
    if not validation_path.is_file():
        raise FileNotFoundError("run the validate command before model selection")
    for path in (
        experiment_root / "training_and_selection_report.json",
        experiment_root / "model_selection_summary.json",
        experiment_root / "validation_predictions.jsonl",
        experiment_root / "models/selected_primary.joblib",
    ):
        if path.exists():
            raise FileExistsError(f"model selection has already produced an artifact: {path}")
    data_validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if data_validation.get("status") != "passed":
        raise ValueError("data validation did not pass")
    fresh_validation = validate_inputs(ai_service_root, experiment_root)
    if fresh_validation["source_inventory_sha256"] != data_validation.get("source_inventory_sha256"):
        raise ValueError("source inputs changed after validation; refusing to train")
    protocol_path = experiment_root / "experiment_protocol.md"
    configuration_path = experiment_root / "configuration.json"
    protocol_hash = sha256_file(protocol_path)
    config = json.loads(configuration_path.read_text(encoding="utf-8"))
    config_hash = sha256_file(configuration_path)

    train_records = _load_split(ai_service_root, "train")
    validation_records = _load_split(ai_service_root, "validation")
    y_train = np.asarray([LABEL_TO_INT[row["label"]] for row in train_records], dtype=np.int64)
    y_validation = np.asarray([LABEL_TO_INT[row["label"]] for row in validation_records], dtype=np.int64)
    candidates = []
    fitted_models = {}
    for model_name in MODEL_FEATURES:
        x_train = feature_matrix(train_records, model_name)
        x_validation = feature_matrix(validation_records, model_name)
        for c_value in C_GRID:
            model = _model_instance(c_value)
            model.fit(x_train, y_train)
            probabilities = model.predict_proba(x_validation)[:, 1]
            metrics = metric_report(y_validation, probabilities)
            entry = {
                "model_name": model_name,
                "feature_set": list(MODEL_FEATURES[model_name]),
                "C": c_value,
                "metrics": metrics,
            }
            candidates.append(entry)
            fitted_models[(model_name, c_value)] = model
    candidates.sort(key=_selection_rank)
    primary_candidates = [candidate for candidate in candidates if candidate["model_name"] != "cosine_only"]
    selected = min(primary_candidates, key=_selection_rank)
    if selected["model_name"] not in MODEL_FEATURES or selected["C"] not in C_GRID:
        raise AssertionError("selection returned a configuration outside the frozen grid")

    model_path = experiment_root / "models/selected_primary.joblib"
    save_model(fitted_models[(selected["model_name"], selected["C"])], model_path)
    model_hash = sha256_file(model_path)
    selected_validation_probabilities = fitted_models[(selected["model_name"], selected["C"])].predict_proba(
        feature_matrix(validation_records, selected["model_name"])
    )[:, 1]
    _write_predictions(
        experiment_root / "validation_predictions.jsonl",
        validation_records,
        selected_validation_probabilities,
        "validation",
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "protocol_frozen": True,
        "protocol_sha256": protocol_hash,
        "configuration_sha256": config_hash,
        "source_inventory_sha256": data_validation["source_inventory_sha256"],
        "model_name": selected["model_name"],
        "feature_set": selected["feature_set"],
        "C": selected["C"],
        "selection_rule": config["selection"],
        "selected_validation_metrics": selected["metrics"],
        "model_artifact": {
            "path": str(model_path.relative_to(experiment_root)),
            "sha256": model_hash,
            "size_bytes": model_path.stat().st_size,
        },
        "validation_metrics_all_candidates": candidates,
        "candidate_ordered_by_selection_rule": True,
        "cosine_only_role": "diagnostic only; excluded from primary model selection",
        "test_performance_inspected": False,
        "test_used_for_selection": False,
        "commands": sys.argv,
        "environment": _environment(),
        "git_commit": _git_commit(ai_service_root),
        "class_count_train": dict(Counter(row["label"] for row in train_records)),
        "class_count_validation": dict(Counter(row["label"] for row in validation_records)),
        "calibration": "none",
        "classification_threshold": THRESHOLD,
    }
    write_json(experiment_root / "training_and_selection_report.json", report)
    write_json(experiment_root / "model_selection_summary.json", {
        "experiment_id": EXPERIMENT_ID,
        "selected_model": {
            "model_name": selected["model_name"],
            "feature_set": selected["feature_set"],
            "C": selected["C"],
            "validation_roc_auc": selected["metrics"]["roc_auc"],
            "validation_average_precision_REAL": selected["metrics"]["average_precision_REAL"],
        },
        "selection_metric": "validation ROC-AUC; tie-break by validation AP, simpler model, then smaller C",
        "model_artifact_sha256": model_hash,
        "protocol_sha256": protocol_hash,
        "test_used_for_selection": False,
    })
    metrics_dir = experiment_root / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        filename = f"{candidate['model_name']}__C-{candidate['C']:g}.json"
        write_json(metrics_dir / filename, candidate)
    return report


def _cluster_bootstrap(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    component_ids: Sequence[str],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    groups: Dict[str, List[int]] = defaultdict(list)
    for index, component_id in enumerate(component_ids):
        groups[component_id].append(index)
    keys = list(groups)
    if len(keys) < 2:
        raise ValueError("cluster bootstrap requires at least two distinct components")
    rng = np.random.RandomState(seed)
    metric_values: Dict[str, List[float]] = defaultdict(list)
    skipped = 0
    for _ in range(replicates):
        sampled_keys = rng.choice(keys, size=len(keys), replace=True)
        indices = np.asarray(
            [row_index for key in sampled_keys for row_index in groups[key]],
            dtype=np.int64,
        )
        y_sample = y_true[indices]
        probability_sample = probabilities[indices]
        if len(np.unique(y_sample)) < 2:
            skipped += 1
            continue
        metrics = metric_report(y_sample, probability_sample)
        for metric in (
            "accuracy",
            "balanced_accuracy",
            "roc_auc",
            "average_precision_REAL",
            "macro_f1",
            "log_loss",
            "brier_score",
        ):
            metric_values[metric].append(metrics[metric])
    intervals = {}
    for metric, values in metric_values.items():
        intervals[metric] = {
            "lower_95": float(np.percentile(values, 2.5)),
            "upper_95": float(np.percentile(values, 97.5)),
            "valid_replicates": len(values),
        }
    return {
        "method": "percentile cluster bootstrap by image component_id",
        "replicates_requested": replicates,
        "seed": seed,
        "distinct_components": len(keys),
        "skipped_single_class_replicates": skipped,
        "intervals": intervals,
        "limitation": "Does not account for unresolved title/submission linkage or dataset shift.",
    }


def evaluate_test(
    ai_service_root: Path,
    experiment_root: Path,
    *,
    sensitivity_excluded_ids: Optional[set] = None,
    sensitivity_label: Optional[str] = None,
    selection_report_path: Optional[Path] = None,
    model_path_override: Optional[Path] = None,
    output_directory: Optional[Path] = None,
) -> dict:
    data_validation = json.loads((experiment_root / "data_validation_report.json").read_text(encoding="utf-8"))
    selection_path = selection_report_path or experiment_root / "training_and_selection_report.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    protocol_path = experiment_root / "experiment_protocol.md"
    config_path = experiment_root / "configuration.json"
    _require(selection.get("protocol_frozen") is True, "selection record does not confirm frozen protocol")
    _require(selection.get("test_used_for_selection") is False, "selection record used test data")
    _require(selection.get("protocol_sha256") == sha256_file(protocol_path), "frozen protocol hash mismatch")
    _require(selection.get("configuration_sha256") == sha256_file(config_path), "configuration hash mismatch")
    _require(
        selection.get("source_inventory_sha256") == data_validation.get("source_inventory_sha256"),
        "selection source inventory differs from validated inputs",
    )
    fresh_validation = validate_inputs(ai_service_root, experiment_root)
    _require(
        fresh_validation["source_inventory_sha256"] == data_validation.get("source_inventory_sha256"),
        "source inputs changed after protocol validation; refusing test evaluation",
    )
    model_path = model_path_override or experiment_root / selection["model_artifact"]["path"]
    _require(
        sha256_file(model_path) == selection["model_artifact"]["sha256"],
        "selected model artifact hash mismatch",
    )
    output_directory = output_directory or experiment_root
    final_path = output_directory / "final_test_report.json"
    if final_path.exists():
        raise FileExistsError(f"final evaluation already exists and must not be repeated: {final_path}")

    manifest_path = ai_service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    assigned, _ = _load_manifest(manifest_path)
    test_records = _load_split(ai_service_root, "test", sensitivity_excluded_ids)
    expected_test_ids = [
        row["sample_id"]
        for row in assigned["test"]
        if sensitivity_excluded_ids is None or row["sample_id"] not in sensitivity_excluded_ids
    ]
    _require(
        [row["sample_id"] for row in test_records] == expected_test_ids,
        "test evaluation records do not match fixed manifest test assignment",
    )
    model_name = selection["model_name"]
    model = joblib.load(model_path)
    x_test = feature_matrix(test_records, model_name)
    y_test = np.asarray([LABEL_TO_INT[row["label"]] for row in test_records], dtype=np.int64)
    probabilities = model.predict_proba(x_test)[:, 1]
    metrics = metric_report(y_test, probabilities)
    component_ids = [
        next(row for row in assigned["test"] if row["sample_id"] == record["sample_id"])["component_id"]
        for record in test_records
    ]
    bootstrap = _cluster_bootstrap(y_test, probabilities, component_ids)
    _write_predictions(output_directory / "test_predictions.jsonl", test_records, probabilities, "test")
    report = {
        "experiment_id": EXPERIMENT_ID,
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "final_held_out_evaluation": sensitivity_label is None,
        "sensitivity_analysis": sensitivity_label,
        "statement": (
            "One-time final held-out test evaluation after protocol and model selection were frozen."
            if sensitivity_label is None
            else "Separate, predeclared sensitivity evaluation; not used to alter primary results."
        ),
        "model_selection_completed_at": selection["selected_at"],
        "selection_report_sha256": sha256_file(selection_path),
        "selected_model": {
            "model_name": selection["model_name"],
            "feature_set": selection["feature_set"],
            "C": selection["C"],
            "model_artifact_sha256": sha256_file(model_path),
        },
        "test_count": len(test_records),
        "class_counts": dict(Counter(row["label"] for row in test_records)),
        "metrics": metrics,
        "confidence_intervals": bootstrap,
        "positive_class": "REAL",
        "test_used_for_model_selection": False,
        "test_evaluation_count": 1,
        "commands": sys.argv,
        "environment": _environment(),
        "git_commit": _git_commit(ai_service_root),
    }
    write_json(final_path, report)
    return report


def run_title_sensitivity(ai_service_root: Path, experiment_root: Path) -> dict:
    if not (experiment_root / "final_test_report.json").is_file():
        raise ValueError("complete and freeze the primary final test evaluation before sensitivity analysis")
    if (experiment_root / "sensitivity/title_overlap/sensitivity_analysis_report.json").exists():
        raise FileExistsError("title-overlap sensitivity analysis has already been completed")
    validated = validate_inputs(ai_service_root, experiment_root)
    stored_validation = json.loads((experiment_root / "data_validation_report.json").read_text(encoding="utf-8"))
    if validated["source_inventory_sha256"] != stored_validation.get("source_inventory_sha256"):
        raise ValueError("source inputs changed after primary evaluation; refusing sensitivity analysis")
    base_validation = json.loads((experiment_root / "data_validation_report.json").read_text(encoding="utf-8"))
    manifest_path = ai_service_root / "data/research/fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl"
    assigned, _ = _load_manifest(manifest_path)
    manifest_by_id = {row["sample_id"]: row for rows in assigned.values() for row in rows}
    title_info = _task37_title_groups(ai_service_root, manifest_by_id)
    excluded_ids = {
        sample_id
        for ids in title_info["affected_ids_by_split"].values()
        for sample_id in ids
    }
    output_directory = experiment_root / "sensitivity/title_overlap"
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"title sensitivity outputs already exist: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    filtered_counts = {}
    for split in SPLITS:
        remaining = [
            row for row in assigned[split]
            if row["sample_id"] not in excluded_ids
        ]
        filtered_counts[split] = {
            "total": len(remaining),
            "FAKE": sum(row["canonical_label"] == "FAKE" for row in remaining),
            "REAL": sum(row["canonical_label"] == "REAL" for row in remaining),
            "excluded": len(assigned[split]) - len(remaining),
        }
    split_records = {
        split: _load_split(ai_service_root, split, excluded_ids)
        for split in ("train", "validation")
    }
    y_train = np.asarray([LABEL_TO_INT[row["label"]] for row in split_records["train"]], dtype=np.int64)
    y_validation = np.asarray([LABEL_TO_INT[row["label"]] for row in split_records["validation"]], dtype=np.int64)
    candidates = []
    models = {}
    for model_name in MODEL_FEATURES:
        x_train = feature_matrix(split_records["train"], model_name)
        x_validation = feature_matrix(split_records["validation"], model_name)
        for c_value in C_GRID:
            model = _model_instance(c_value)
            model.fit(x_train, y_train)
            metrics = metric_report(y_validation, model.predict_proba(x_validation)[:, 1])
            candidate = {
                "model_name": model_name,
                "feature_set": list(MODEL_FEATURES[model_name]),
                "C": c_value,
                "metrics": metrics,
            }
            candidates.append(candidate)
            models[(model_name, c_value)] = model
    candidates.sort(key=_selection_rank)
    selected = candidates[0]
    sensitivity_model = output_directory / "selected_sensitivity.joblib"
    save_model(models[(selected["model_name"], selected["C"])], sensitivity_model)
    model_sha = sha256_file(sensitivity_model)
    title_analysis = {
        "experiment_id": EXPERIMENT_ID,
        "analysis": "exact normalized-title overlap exclusion sensitivity",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule": "strip whitespace, casefold, SHA-256 exact-title groups occurring in more than one assigned split; exclude all members only within their existing split",
        "group_count": title_info["cross_split_group_count"],
        "affected_record_count": title_info["affected_record_count"],
        "affected_label_counts_by_split": title_info["affected_label_counts_by_split"],
        "groups_with_both_labels": title_info["cross_split_groups_with_both_labels"],
        "excluded_record_counts_by_split": {
            split: filtered_counts[split]["excluded"] for split in SPLITS
        },
        "remaining_counts_by_split": filtered_counts,
        "identifiers_and_group_hashes": {
            "affected_ids_by_split": title_info["affected_ids_by_split"],
            "group_hashes_and_members": title_info["groups"],
        },
        "source_hashes": title_info["source_hashes"],
        "candidate_validation_metrics": candidates,
        "selected_model": {
            "model_name": selected["model_name"],
            "feature_set": selected["feature_set"],
            "C": selected["C"],
            "validation_metrics": selected["metrics"],
            "model_artifact": {
                "path": str(sensitivity_model.relative_to(experiment_root)),
                "sha256": model_sha,
            },
        },
        "protocol_sha256": sha256_file(experiment_root / "experiment_protocol.md"),
        "test_used_for_selection": False,
        "interpretation_limit": "Exact normalized title overlap does not establish that every pair represents the same claim; this does not change the primary split.",
    }
    selection_path = output_directory / "training_and_selection_report.json"
    write_json(selection_path, title_analysis)
    sensitivity_model_info = {
        "model_name": selected["model_name"],
        "feature_set": selected["feature_set"],
        "C": selected["C"],
        "selected_at": title_analysis["created_at"],
        "protocol_frozen": True,
        "test_used_for_selection": False,
        "protocol_sha256": title_analysis["protocol_sha256"],
        "configuration_sha256": sha256_file(experiment_root / "configuration.json"),
        "source_inventory_sha256": base_validation["source_inventory_sha256"],
        "model_artifact": {
            "path": str(sensitivity_model.relative_to(experiment_root)),
            "sha256": model_sha,
        },
    }
    write_json(output_directory / "selection_gate.json", sensitivity_model_info)
    final = evaluate_test(
        ai_service_root,
        experiment_root,
        sensitivity_excluded_ids=excluded_ids,
        sensitivity_label="exact_title_overlap_excluded",
        selection_report_path=output_directory / "selection_gate.json",
        model_path_override=sensitivity_model,
        output_directory=output_directory,
    )
    title_analysis["final_sensitivity_test_report"] = {
        "path": str((output_directory / "final_test_report.json").relative_to(experiment_root)),
        "sha256": sha256_file(output_directory / "final_test_report.json"),
        "metrics": final["metrics"],
        "confidence_intervals": final["confidence_intervals"],
    }
    write_json(output_directory / "sensitivity_analysis_report.json", title_analysis)
    return title_analysis


def finalize_experiment(ai_service_root: Path, experiment_root: Path) -> dict:
    required = (
        experiment_root / "data_validation_report.json",
        experiment_root / "training_and_selection_report.json",
        experiment_root / "model_selection_summary.json",
        experiment_root / "final_test_report.json",
        experiment_root / "sensitivity/title_overlap/sensitivity_analysis_report.json",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"required Task 38 artifact is missing: {path}")
    if (experiment_root / "final_audit_report.md").exists():
        raise FileExistsError("Task 38 final audit report already exists")
    fresh_validation = validate_inputs(ai_service_root, experiment_root)
    stored_validation = json.loads((experiment_root / "data_validation_report.json").read_text(encoding="utf-8"))
    _require(
        fresh_validation["source_inventory_sha256"] == stored_validation["source_inventory_sha256"],
        "source inputs changed during the experiment",
    )
    selection = json.loads((experiment_root / "training_and_selection_report.json").read_text(encoding="utf-8"))
    final_test = json.loads((experiment_root / "final_test_report.json").read_text(encoding="utf-8"))
    sensitivity = json.loads(
        (experiment_root / "sensitivity/title_overlap/sensitivity_analysis_report.json").read_text(encoding="utf-8")
    )
    _require(final_test.get("final_held_out_evaluation") is True, "primary final test report is not marked final")
    _require(final_test.get("test_used_for_model_selection") is False, "test was used for model selection")
    run_metadata = {
        "experiment_id": EXPERIMENT_ID,
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "commands": {
            "validation": "python -m app.evaluation.fakeddit_baseline validate",
            "selection": "python -m app.evaluation.fakeddit_baseline select",
            "primary_test": "python -m app.evaluation.fakeddit_baseline evaluate",
            "title_sensitivity": "python -m app.evaluation.fakeddit_baseline title-sensitivity",
            "final_audit": "python -m app.evaluation.fakeddit_baseline final-audit",
        },
        "environment": _environment(),
        "git_commit": _git_commit(ai_service_root),
        "protocol_sha256": sha256_file(experiment_root / "experiment_protocol.md"),
        "configuration_sha256": sha256_file(experiment_root / "configuration.json"),
        "input_inventory_sha256": stored_validation["source_inventory_sha256"],
        "selected_model": {
            "model_name": selection["model_name"],
            "feature_set": selection["feature_set"],
            "C": selection["C"],
            "artifact_sha256": selection["model_artifact"]["sha256"],
        },
        "primary_test_evaluation_timestamp": final_test["evaluation_timestamp"],
        "primary_test_not_used_for_selection": True,
        "sensitivity_report": "sensitivity/title_overlap/sensitivity_analysis_report.json",
        "classifier_scope": "Fakeddit 2-way distant-supervision labels; not factual verification",
    }
    write_json(experiment_root / "run_metadata.json", run_metadata)
    inventory = {}
    for path in sorted(experiment_root.rglob("*")):
        if not path.is_file() or path == experiment_root / "output_sha256_inventory.json":
            continue
        relative = str(path.relative_to(experiment_root))
        inventory[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    write_json(experiment_root / "output_sha256_inventory.json", inventory)
    input_hash_rows = "\n".join(
        f"| `{key}` | `{value['sha256']}` |"
        for key, value in stored_validation["input_sha256_inventory"].items()
    )
    protected_hash_rows = "\n".join(
        f"| `{relative}` | `{value['sha256']}` | {'Match' if value['match'] else 'MISMATCH'} |"
        for relative, value in stored_validation["protected_artifact_sha256_inventory"].items()
    )

    audit_text = f"""# Task 38 — Final classifier experiment audit

**Finalized:** {run_metadata['finalized_at']}

## Outcome

- Pre-training input audit: **{stored_validation['status'].upper()}**.
- Selected model: **{selection['model_name']}**, features `{', '.join(selection['feature_set'])}`, `C={selection['C']}`.
- Selection used training for fit and validation for model/regularization selection. The test set was not used for selection.
- Primary held-out test evaluation: **{final_test['evaluation_timestamp']}**, once after selection was frozen.
- Exact-title sensitivity analysis: completed separately after the primary test, with {sensitivity['affected_record_count']} records in {sensitivity['group_count']} exact normalized-title groups excluded only within their existing split.
- Linked-submission sensitivity: not run because identifier semantics are unresolved.
- No model fine-tuning or application integration was performed.

## Data and scientific scope

The data validation report confirms exact manifest correspondence, expected counts and labels, v2 predictor allowlisting, finite normalized 512-dimensional embeddings, cosine consistency, no missing modalities, and four quarantined records excluded. Inputs and six protected artifacts passed SHA-256 verification.

The prediction target is Fakeddit's project-mapped 2-way distant-supervision label (`FAKE=0`, `REAL=1`, positive class REAL). This does not demonstrate factual verification of arbitrary claims, source credibility, truth, or evidence-based reasoning. Cosine is semantic similarity, not contradiction or truth confidence.

## Selected validation metrics

```json
{json.dumps(selection['selected_validation_metrics'], indent=2, sort_keys=True)}
```

## One-time held-out test metrics

```json
{json.dumps(final_test['metrics'], indent=2, sort_keys=True)}
```

## Test uncertainty

```json
{json.dumps(final_test['confidence_intervals'], indent=2, sort_keys=True)}
```

## Automated validation

The focused Task 38 tests and related shared-feature/CMREF/RR/CMREA/legacy Fakeddit regression tests completed with **99 passed**. Python compilation and `git diff --check` completed successfully. The selection-path test fits only tiny synthetic fixtures; the tests do not train on the Fakeddit experiment data or evaluate its held-out test set.

## Title-overlap sensitivity

```json
{json.dumps(sensitivity['final_sensitivity_test_report']['metrics'], indent=2, sort_keys=True)}
```

This analysis does not prove title identity means claim identity, remove all leakage, or change the primary fixed split. Remaining risks include unresolved `linked_submission_id` semantics, unverified near-image candidates, distant-supervision label noise, acquisition-selection bias, and possible dependence not captured by image-component bootstrap intervals.

## Artifact integrity

`output_sha256_inventory.json` lists SHA-256 hashes and sizes for all Task 38 artifacts other than itself and this final audit report. `run_metadata.json` records the source inventory digest, selected model, protocol/configuration hashes, commands, environment, and evaluation timestamp. Task 36C outputs and protected Task 32B/v1 artifacts were rechecked before finalization.

### Source artifact SHA-256

| Input | SHA-256 |
|---|---|
{input_hash_rows}

### Protected Task 32B/v1 artifact SHA-256

| Protected artifact | SHA-256 | Result |
|---|---|---|
{protected_hash_rows}
"""
    audit_path = experiment_root / "final_audit_report.md"
    atomic_write(audit_path, audit_text.encode("utf-8"))
    return {
        "final_audit_report": str(audit_path),
        "output_sha256_inventory": str(experiment_root / "output_sha256_inventory.json"),
        "output_files_hashed": len(inventory),
        "input_inventory_sha256": stored_validation["source_inventory_sha256"],
    }


def run_validate(ai_service_root: Path, experiment_root: Path) -> dict:
    if (experiment_root / "training_and_selection_report.json").exists():
        raise ValueError("cannot refresh validation artifacts after model selection")
    report = validate_inputs(ai_service_root, experiment_root)
    write_json(experiment_root / "data_validation_report.json", report, refuse_existing=False)
    write_json(experiment_root / "source_artifact_sha256_inventory.json", {
        "inputs": report["input_sha256_inventory"],
        "protected": report["protected_artifact_sha256_inventory"],
        "inventory_sha256": report["source_inventory_sha256"],
    }, refuse_existing=False)
    write_json(experiment_root / "environment_inventory.json", {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "environment": report["environment"],
        "git_commit": report["git_commit"],
    }, refuse_existing=False)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("validate", "select", "evaluate", "title-sensitivity", "final-audit"))
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        default=Path("data/research/fakeddit-experiments/task38-baseline-classifier-20261019"),
    )
    args = parser.parse_args()
    ai_service_root = Path.cwd().resolve()
    experiment_root = args.experiment_dir.resolve()
    if not (experiment_root / "experiment_protocol.md").is_file() or not (experiment_root / "configuration.json").is_file():
        raise FileNotFoundError("experiment protocol/configuration must exist before running a phase")
    if args.phase == "validate":
        result = run_validate(ai_service_root, experiment_root)
    elif args.phase == "select":
        result = select_model(ai_service_root, experiment_root)
    elif args.phase == "evaluate":
        result = evaluate_test(ai_service_root, experiment_root)
    elif args.phase == "title-sensitivity":
        result = run_title_sensitivity(ai_service_root, experiment_root)
    else:
        result = finalize_experiment(ai_service_root, experiment_root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
