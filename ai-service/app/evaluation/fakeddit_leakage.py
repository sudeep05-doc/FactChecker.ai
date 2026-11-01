"""Create a separate Fakeddit manifest grouped by verified image identity."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from PIL import Image, ImageOps

from app.evaluation.fakeddit_features import (
    FeatureExtractionConfig,
    _is_complete_feature_artifact,
    _resolve_local_image_path,
)

MANIFEST_VERSION = "fakeddit-leakage-safe-manifest-v3"
GROUPING_RULE_VERSION = "exact-image-sha256-plus-reviewed-near-pair-v1"
SPLITS = ("train", "validation", "test")
SPLIT_RATIOS = {"train": 0.715, "validation": 0.1425, "test": 0.1425}
SOURCE_FILES = {
    "train": "all_train.tsv",
    "validation": "all_validate.tsv",
    "test": "all_test_public.tsv",
}
LABEL_MAPPING = {"0": "FAKE", "1": "REAL"}
EXACT_SHA_CONFLICT_IDS = ("bzjci1", "bzbodv")
MANUAL_NEAR_PAIR_IDS = ("cltr2f1", "2ld43g")
EXPECTED_CONFLICT_PROVENANCE = {
    "bzjci1": ("train", "FAKE"),
    "bzbodv": ("validation", "REAL"),
    "cltr2f1": ("train", "FAKE"),
    "2ld43g": ("test", "REAL"),
}
SUCCESSFUL_ACQUISITION_STATUSES = {"downloaded", "already_present", "success", "successful", "acquired"}


class LeakageManifestError(ValueError):
    """Raised when the existing research artifacts cannot safely support a split."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | int(pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return value


def _largest_remainder(total: int, ratios: Mapping[str, float]) -> Dict[str, int]:
    raw = {split: total * ratios[split] for split in SPLITS}
    counts = {split: int(raw[split]) for split in SPLITS}
    remaining = total - sum(counts.values())
    order = sorted(SPLITS, key=lambda split: (-(raw[split] - counts[split]), SPLITS.index(split)))
    for split in order[:remaining]:
        counts[split] += 1
    return counts


def connected_components(
    records: Sequence[dict],
    *,
    near_pairs: Sequence[Tuple[str, str]] = (),
) -> List[List[str]]:
    """Join exact image hashes and only explicitly supplied confirmed near-pairs."""
    sample_ids = [str(record["sample_id"]) for record in records]
    if len(sample_ids) != len(set(sample_ids)):
        raise LeakageManifestError("duplicate sample IDs prevent unambiguous component assignment")
    parent = {sample_id: sample_id for sample_id in sample_ids}

    def find(sample_id: str) -> str:
        while parent[sample_id] != sample_id:
            parent[sample_id] = parent[parent[sample_id]]
            sample_id = parent[sample_id]
        return sample_id

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    by_hash: Dict[str, List[str]] = defaultdict(list)
    for record in records:
        by_hash[str(record["image_sha256"])].append(str(record["sample_id"]))
    for members in by_hash.values():
        for sample_id in members[1:]:
            union(members[0], sample_id)
    for left, right in near_pairs:
        if left not in parent or right not in parent:
            raise LeakageManifestError(f"confirmed near-image member missing: {left}, {right}")
        union(left, right)

    groups: Dict[str, List[str]] = defaultdict(list)
    for sample_id in parent:
        groups[find(sample_id)].append(sample_id)
    return [sorted(members) for members in groups.values()]


def assign_components(
    records: Sequence[dict],
    *,
    seed: int = 42,
    ratios: Mapping[str, float] = SPLIT_RATIOS,
    near_pairs: Sequence[Tuple[str, str]] = (),
) -> Tuple[Dict[str, str], List[List[str]], Dict[str, Dict[str, int]]]:
    """Deterministically allocate whole non-quarantined groups to target class counts."""
    if set(ratios) != set(SPLITS) or abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError("ratios must specify train/validation/test and sum to one")
    by_id = {str(record["sample_id"]): record for record in records}
    groups = connected_components(records, near_pairs=near_pairs)
    available = [record for record in records if not record.get("quarantined")]
    targets = {
        label: _largest_remainder(sum(record["canonical_label"] == label for record in available), ratios)
        for label in ("FAKE", "REAL")
    }
    active_groups = []
    for group in groups:
        members = [by_id[sample_id] for sample_id in group]
        if any(record.get("quarantined") for record in members):
            if not all(record.get("quarantined") for record in members):
                raise LeakageManifestError("quarantine must cover a complete confirmed component")
            continue
        labels = {record["canonical_label"] for record in members}
        if len(labels) != 1:
            raise LeakageManifestError("unquarantined component contains conflicting canonical labels")
        shas = {record["image_sha256"] for record in members}
        component_id = (
            f"image-sha256:{next(iter(shas))}"
            if len(shas) == 1
            else "manual-near-pair:" + hashlib.sha256("\0".join(group).encode("utf-8")).hexdigest()
        )
        active_groups.append((component_id, group, next(iter(labels))))
    active_groups.sort(
        key=lambda item: (
            -len(item[1]),
            hashlib.sha256(f"{seed}\0{item[0]}".encode("utf-8")).hexdigest(),
        )
    )

    current = {split: Counter() for split in SPLITS}
    target_total = {
        split: targets["FAKE"][split] + targets["REAL"][split]
        for split in SPLITS
    }

    def score() -> float:
        total = 0.0
        for split in SPLITS:
            for metric, target in (
                ("total", target_total[split]),
                ("FAKE", targets["FAKE"][split]),
                ("REAL", targets["REAL"][split]),
            ):
                total += ((current[split][metric] - target) / max(target, 1)) ** 2
        return total

    assigned: Dict[str, str] = {}
    for component_id, members, label in active_groups:
        choices = []
        for split in SPLITS:
            current[split]["total"] += len(members)
            current[split][label] += len(members)
            objective = score()
            current[split]["total"] -= len(members)
            current[split][label] -= len(members)
            tie_break = hashlib.sha256(f"{seed}\0{component_id}\0{split}".encode("utf-8")).hexdigest()
            choices.append((objective, tie_break, split))
        chosen = min(choices)[2]
        current[chosen]["total"] += len(members)
        current[chosen][label] += len(members)
        for sample_id in members:
            assigned[sample_id] = chosen
    return assigned, groups, targets


def _load_verified_records(
    *, data_dir: Path, source_dir: Path, feature_dir: Path
) -> Tuple[List[dict], Dict[str, str]]:
    prep_path = data_dir / "preparation_report.json"
    prep_report = json.loads(prep_path.read_text(encoding="utf-8"))
    if prep_report.get("label_mapping", {}).get("canonical_labels") != LABEL_MAPPING:
        raise LeakageManifestError("preparation report label mapping is not the approved 0->FAKE, 1->REAL map")
    config = FeatureExtractionConfig(
        data_dir=data_dir,
        output_dir=feature_dir,
        text_batch_size=8,
        image_batch_size=4,
        device="auto",
        resume=True,
    )
    fingerprint = config.configuration_fingerprint()
    records: List[dict] = []
    hashes: Dict[str, str] = {}
    image_hash_by_path: Dict[str, str] = {}

    for split in SPLITS:
        acquired_path = data_dir / "acquired" / f"{split}.jsonl"
        feature_path = feature_dir / f"{split}.jsonl"
        tsv_path = source_dir / SOURCE_FILES[split]
        acquired: Dict[str, dict] = {}
        with acquired_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                sid = str(row.get("sample_id") or "")
                if not sid or sid in acquired:
                    raise LeakageManifestError(f"missing or duplicate acquired ID: {acquired_path}:{line_number}")
                acquired[sid] = row

        features = []
        with feature_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                artifact = json.loads(line)
                sid = str(artifact.get("sample_id") or "")
                if not sid:
                    raise LeakageManifestError(f"feature record has no sample ID: {feature_path}:{line_number}")
                features.append(artifact)
        feature_ids = [str(record["sample_id"]) for record in features]
        if len(feature_ids) != len(set(feature_ids)):
            raise LeakageManifestError(f"duplicate feature IDs in {feature_path}")
        eligible_ids = set()
        for sid, row in acquired.items():
            metadata = row.get("metadata") or {}
            acquisition = metadata.get("acquisition") or {}
            local = _resolve_local_image_path(metadata.get("local_image_path"), data_dir=data_dir)
            if (
                str(acquisition.get("acquisition_status") or "").strip().lower()
                in SUCCESSFUL_ACQUISITION_STATUSES
                and local is not None
                and local.is_file()
            ):
                eligible_ids.add(sid)
        if set(feature_ids) != eligible_ids:
            raise LeakageManifestError(f"feature records do not reconcile to eligible acquired {split} IDs")

        wanted = set(feature_ids)
        source: Dict[str, dict] = {}
        source_occurrences = Counter()
        with tsv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle, delimiter="\t"), start=2):
                sid = str(row.get("id") or "")
                if sid in wanted:
                    source_occurrences[sid] += 1
                    source[sid] = {**row, "_source_row": row_number}
        if set(source) != wanted or any(count != 1 for count in source_occurrences.values()):
            raise LeakageManifestError(f"feature IDs do not join one-to-one to {tsv_path}")

        for artifact in features:
            sid = str(artifact["sample_id"])
            sample = acquired[sid]
            metadata = sample.get("metadata") or {}
            source_row = source[sid]
            source_label = str(source_row.get("2_way_label") or "")
            canonical_label = LABEL_MAPPING.get(source_label)
            if (
                not canonical_label
                or metadata.get("source_id") != sid
                or metadata.get("source_split") != split
                or metadata.get("source_file") != SOURCE_FILES[split]
                or int(metadata.get("source_row") or -1) != source_row["_source_row"]
                or metadata.get("source_label") != source_label
                or (metadata.get("preparation") or {}).get("label_mapping") != LABEL_MAPPING
                or source_row.get("clean_title") != artifact.get("clean_title")
                or artifact.get("label") != canonical_label
                or sample.get("label") != canonical_label
            ):
                raise LeakageManifestError(f"source identity/label/text mismatch for {split}:{sid}")
            if not _is_complete_feature_artifact(
                artifact,
                sample=sample,
                config=config,
                configuration_fingerprint=fingerprint,
                data_dir=data_dir,
            ):
                raise LeakageManifestError(f"feature artifact is invalid/incompatible for {split}:{sid}")

            local_path = _resolve_local_image_path(metadata.get("local_image_path"), data_dir=data_dir)
            if local_path is None or not local_path.is_file():
                raise LeakageManifestError(f"local image unavailable for {split}:{sid}")
            resolved = str(local_path.resolve())
            actual_sha = image_hash_by_path.get(resolved)
            if actual_sha is None:
                actual_sha = _sha256(local_path)
                image_hash_by_path[resolved] = actual_sha
            recorded_sha = str((metadata.get("acquisition") or {}).get("sha256") or "")
            if not recorded_sha or actual_sha != recorded_sha:
                raise LeakageManifestError(f"acquisition image SHA-256 does not match bytes for {split}:{sid}")
            records.append({
                "sample_id": sid,
                "original_split": split,
                "source_row": source_row["_source_row"],
                "source_file": SOURCE_FILES[split],
                "source_id": str(source_row.get("id") or ""),
                "source_label": source_label,
                "canonical_label": canonical_label,
                "clean_title": str(source_row.get("clean_title") or "").strip(),
                "image_sha256": actual_sha,
                "local_image_path": str(local_path.relative_to(data_dir.resolve())),
                "linked_submission_id_candidate": str(source_row.get("linked_submission_id") or "").strip() or None,
            })

    sample_ids = [record["sample_id"] for record in records]
    if len(sample_ids) != len(set(sample_ids)):
        raise LeakageManifestError("sample IDs are duplicated across original splits")

    input_files = {
        "preparation_report": prep_path,
        "acquisition_report": data_dir / "acquisition_report.json",
        "feature_cache": feature_dir / "feature_cache.json",
    }
    for split in SPLITS:
        input_files[f"acquisition_manifest_{split}"] = data_dir / f"{split}.jsonl"
        input_files[f"acquired_{split}"] = data_dir / "acquired" / f"{split}.jsonl"
        input_files[f"features_{split}"] = feature_dir / f"{split}.jsonl"
        input_files[f"source_tsv_{split}"] = source_dir / SOURCE_FILES[split]
    for key, path in input_files.items():
        if not path.is_file():
            raise LeakageManifestError(f"required input file is missing: {path}")
        hashes[key] = _sha256(path)
    for split in SPLITS:
        recorded = prep_report["input_counts"][split]["input_sha256"]
        if hashes[f"source_tsv_{split}"] != recorded:
            raise LeakageManifestError(f"source TSV hash differs from preparation report: {split}")
    return records, hashes


def _quarantine_and_verify(
    records: Sequence[dict],
    *,
    data_dir: Path,
) -> Tuple[dict, dict, Tuple[Tuple[str, str], ...]]:
    by_id = {record["sample_id"]: record for record in records}
    exact_left, exact_right = EXACT_SHA_CONFLICT_IDS
    near_left, near_right = MANUAL_NEAR_PAIR_IDS
    for sample_id in EXACT_SHA_CONFLICT_IDS + MANUAL_NEAR_PAIR_IDS:
        if sample_id not in by_id:
            raise LeakageManifestError(f"required conflict sample is missing: {sample_id}")
        expected_split, expected_label = EXPECTED_CONFLICT_PROVENANCE[sample_id]
        if (
            by_id[sample_id]["original_split"] != expected_split
            or by_id[sample_id]["canonical_label"] != expected_label
        ):
            raise LeakageManifestError(
                f"required conflict provenance changed for {sample_id}: "
                f"{by_id[sample_id]['original_split']}/{by_id[sample_id]['canonical_label']}"
            )

    exact_records = [by_id[exact_left], by_id[exact_right]]
    if exact_records[0]["image_sha256"] != exact_records[1]["image_sha256"]:
        raise LeakageManifestError("the cited exact-image conflict no longer has identical image bytes")
    if {record["canonical_label"] for record in exact_records} != {"FAKE", "REAL"}:
        raise LeakageManifestError("the cited exact-image pair no longer has opposite labels")

    near_records = [by_id[near_left], by_id[near_right]]
    if near_records[0]["image_sha256"] == near_records[1]["image_sha256"]:
        raise LeakageManifestError("the visually reviewed near-image pair unexpectedly has identical bytes")
    if {record["canonical_label"] for record in near_records} != {"FAKE", "REAL"}:
        raise LeakageManifestError("the visually reviewed near-image pair no longer has opposite labels")

    near_paths = []
    for sample_id in (near_left, near_right):
        local_path = _resolve_local_image_path(by_id[sample_id]["local_image_path"], data_dir=data_dir)
        if local_path is None:
            raise LeakageManifestError(f"confirmed near-image path missing for {sample_id}")
        near_paths.append(local_path)
    near_distance = bin(_dhash(near_paths[0]) ^ _dhash(near_paths[1])).count("1")
    if near_distance != 1:
        raise LeakageManifestError(f"confirmed near-image dHash no longer matches review: distance={near_distance}")

    reasons = {
        exact_left: "EXACT_IMAGE_SHA_LABEL_CONFLICT",
        exact_right: "EXACT_IMAGE_SHA_LABEL_CONFLICT",
        near_left: "MANUALLY_CONFIRMED_NEAR_IMAGE_LABEL_CONFLICT",
        near_right: "MANUALLY_CONFIRMED_NEAR_IMAGE_LABEL_CONFLICT",
    }
    for sample_id, reason in reasons.items():
        by_id[sample_id]["quarantined"] = True
        by_id[sample_id]["quarantine_reason"] = reason
    review = {
        "sample_ids": [near_left, near_right],
        "confirmation": "manually reviewed as the same scene under different crop/resize in Task 31",
        "dhash64_hamming_distance": near_distance,
        "exact_sha256_equal": False,
    }
    conflict = {
        "sample_ids": [exact_left, exact_right],
        "shared_sha256": exact_records[0]["image_sha256"],
        "canonical_labels": {exact_left: by_id[exact_left]["canonical_label"], exact_right: by_id[exact_right]["canonical_label"]},
    }
    return reasons, {"near_image_review": review, "exact_image_label_conflict": conflict}, (MANUAL_NEAR_PAIR_IDS,)


def _report_rows(records: Sequence[dict], assigned: Mapping[str, str], components: Sequence[Sequence[str]], hashes: Mapping[str, str], seed: int, generated_at: str) -> Tuple[str, dict]:
    quarantine_counts = Counter(record["quarantine_reason"] for record in records if record.get("quarantined"))
    counts = {split: Counter() for split in SPLITS}
    original_counts = {split: Counter() for split in SPLITS}
    exact_sha_groups: Dict[str, List[dict]] = defaultdict(list)
    for record in records:
        original_counts[record["original_split"]][record["canonical_label"]] += 1
        exact_sha_groups[record["image_sha256"]].append(record)
        if record["sample_id"] in assigned:
            counts[assigned[record["sample_id"]]][record["canonical_label"]] += 1
    ordered = sorted(records, key=lambda r: (SPLITS.index(r["original_split"]), r["source_row"], r["sample_id"]))
    output_rows = []
    for record in ordered:
        row = {
            "sample_id": record["sample_id"],
            "original_split": record["original_split"],
            "assigned_split": assigned.get(record["sample_id"]),
            "canonical_label": record["canonical_label"],
            "source_label": record["source_label"],
            "source_file": record["source_file"],
            "source_row": record["source_row"],
            "source_id": record["source_id"],
            "linked_submission_id_candidate": record["linked_submission_id_candidate"],
            "image_sha256": record["image_sha256"],
            "component_id": record["component_id"],
            "quarantined": bool(record.get("quarantined")),
            "quarantine_reason": record.get("quarantine_reason"),
            "manual_near_image_review_id": record.get("manual_near_image_review_id"),
            "manifest_version": MANIFEST_VERSION,
            "grouping_rule_version": GROUPING_RULE_VERSION,
            "seed": seed,
            "manifest_generated_at": generated_at,
        }
        output_rows.append(row)
    manifest_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows)
    components_by_id = _components_by_id(records)
    records_by_id = {record["sample_id"]: record for record in records}
    assigned_group_splits = {
        component_id: {assigned[sid] for sid in ids if sid in assigned}
        for component_id, ids in components_by_id.items()
    }
    original_group_splits = {
        component_id: {records_by_id[sid]["original_split"] for sid in ids}
        for component_id, ids in components_by_id.items()
    }
    linked_groups: Dict[str, List[dict]] = defaultdict(list)
    for record in records:
        linked_id = record.get("linked_submission_id_candidate")
        if linked_id:
            linked_groups[linked_id].append(record)
    linked_cross = [group for group in linked_groups.values() if len({r["original_split"] for r in group}) > 1]
    exact_cross = [
        group for group in exact_sha_groups.values()
        if len({record["original_split"] for record in group}) > 1
    ]
    total_records = sum(len(group) for group in exact_sha_groups.values())
    quarantine_records = [
        {
            "sample_id": record["sample_id"],
            "original_split": record["original_split"],
            "source_file": record["source_file"],
            "source_row": record["source_row"],
            "source_label": record["source_label"],
            "canonical_label": record["canonical_label"],
            "image_sha256": record["image_sha256"],
            "component_id": record["component_id"],
            "reason": record["quarantine_reason"],
            "manual_near_image_review_id": record.get("manual_near_image_review_id"),
        }
        for record in records
        if record.get("quarantined")
    ]
    report = {
        "manifest_version": MANIFEST_VERSION,
        "grouping_rule_version": GROUPING_RULE_VERSION,
        "generated_at": generated_at,
        "seed": seed,
        "split_proportions": SPLIT_RATIOS,
        "assignment_objective": "greedy minimization of global squared normalized deviations in total, FAKE, and REAL counts; components ordered by descending size then SHA-256(seed,NUL,component_id); ties broken by SHA-256(seed,NUL,component_id,NUL,split)",
        "label_mapping": LABEL_MAPPING,
        "primary_grouping_keys": ["verified local image-byte SHA-256", "manually confirmed near-image pair"],
        "excluded_grouping_candidates": ["exact title", "linked_submission_id"],
        "linked_submission_id_policy": "retained as candidate provenance only and excluded from primary grouping because field semantics are not authoritative in available source documentation",
        "near_image_candidates_reported": 331,
        "near_image_candidates_accepted_as_confirmed": 1,
        "near_image_candidates_unverified": 330,
        "unverified_near_image_candidate_policy": "reported as candidates only; none are used for grouping or quarantine",
        "input_artifact_sha256": dict(hashes),
        "input_counts_by_original_split": {split: {"total": sum(original_counts[split].values()), "FAKE": original_counts[split]["FAKE"], "REAL": original_counts[split]["REAL"]} for split in SPLITS},
        "quarantine_counts_by_reason": dict(quarantine_counts),
        "quarantined_total": sum(quarantine_counts.values()),
        "quarantined_records": quarantine_records,
        "assigned_counts": {
            split: {
                "total": sum(counts[split].values()),
                "FAKE": counts[split]["FAKE"],
                "REAL": counts[split]["REAL"],
                "FAKE_percent": round(100 * counts[split]["FAKE"] / max(sum(counts[split].values()), 1), 3),
                "REAL_percent": round(100 * counts[split]["REAL"] / max(sum(counts[split].values()), 1), 3),
                "dataset_percent": round(100 * sum(counts[split].values()) / max(total_records - sum(quarantine_counts.values()), 1), 3),
            }
            for split in SPLITS
        },
        "confirmed_exact_sha256_grouping": {
            "group_count": len(exact_sha_groups),
            "cross_original_split_group_count": len(exact_cross),
            "records_in_cross_original_split_groups": sum(len(group) for group in exact_cross),
            "cross_original_split_groups": [
                {
                    "image_sha256": group[0]["image_sha256"],
                    "sample_ids": sorted(record["sample_id"] for record in group),
                    "original_splits": sorted({record["original_split"] for record in group}),
                }
                for group in sorted(exact_cross, key=lambda members: members[0]["image_sha256"])
            ],
        },
        "connected_components_before_quarantine": len(components),
        "components_crossing_original_splits": sum(len(splits) > 1 for splits in original_group_splits.values()),
        "records_in_components_crossing_original_splits": sum(
            len(components_by_id[component_id])
            for component_id, splits in original_group_splits.items()
            if len(splits) > 1
        ),
        "assigned_components_crossing_splits": sum(len(splits) > 1 for splits in assigned_group_splits.values()),
        "linked_submission_id_sensitivity_only": {
            "used_for_primary_grouping": False,
            "cross_split_groups": len(linked_cross),
            "records_in_cross_split_groups": sum(len(group) for group in linked_cross),
            "semantics": "unresolved in authoritative source documentation available to this project",
        },
        "manifest_sha256": hashlib.sha256(manifest_text.encode("utf-8")).hexdigest(),
    }
    return manifest_text, report


def _components_by_id(records: Sequence[dict]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for record in records:
        grouped[str(record["component_id"])].append(str(record["sample_id"]))
    return grouped


def prepare_leakage_safe_manifest(
    *,
    data_dir: str | Path = "data/research/fakeddit",
    source_dir: str | Path = "../research-data/fakeddit",
    feature_dir: str | Path = "data/research/fakeddit-features",
    seed: int = 42,
) -> Tuple[str, dict]:
    data_path, source_path, feature_path = Path(data_dir), Path(source_dir), Path(feature_dir)
    records, input_hashes = _load_verified_records(data_dir=data_path, source_dir=source_path, feature_dir=feature_path)
    quarantine_reasons, special_evidence, near_pairs = _quarantine_and_verify(records, data_dir=data_path)
    for record in records:
        record["quarantined"] = False
        record["quarantine_reason"] = None
        if record["sample_id"] in quarantine_reasons:
            record["quarantined"] = True
            record["quarantine_reason"] = quarantine_reasons[record["sample_id"]]
        if record["sample_id"] in MANUAL_NEAR_PAIR_IDS:
            record["manual_near_image_review_id"] = "task31-visual-review-cltr2f1-2ld43g"
    components = connected_components(records, near_pairs=near_pairs)
    component_by_sample = {}
    records_by_id = {record["sample_id"]: record for record in records}
    for component in components:
        sha_values = {records_by_id[sid]["image_sha256"] for sid in component}
        if len(sha_values) == 1:
            component_id = f"image-sha256:{next(iter(sha_values))}"
        else:
            component_id = "manual-near-pair:" + hashlib.sha256("\0".join(component).encode("utf-8")).hexdigest()
        for sid in component:
            component_by_sample[sid] = component_id
    for record in records:
        record["component_id"] = component_by_sample[record["sample_id"]]
    assignment, _, targets = assign_components(records, seed=seed, near_pairs=near_pairs)
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest_text, report = _report_rows(records, assignment, components, input_hashes, seed, generated_at)
    report.update(special_evidence)
    report["target_class_counts"] = targets
    acquisition_report = json.loads((data_path / "acquisition_report.json").read_text(encoding="utf-8"))
    report["dataset_scope"] = (
        "Records with successful local image acquisition and one complete, source-verified row "
        "in each original feature JSONL. Acquisition failures are excluded before this manifest."
    )
    acquisition_failure_statuses: Counter = Counter()
    for split_summary in acquisition_report["per_split"].values():
        for status, count in split_summary["status_counts"].items():
            if status.strip().lower() not in SUCCESSFUL_ACQUISITION_STATUSES:
                acquisition_failure_statuses[status] += count
    report["acquisition_accounting"] = {
        "total_requested": acquisition_report["counts"]["total_requested"],
        "successful": acquisition_report["counts"]["successful"],
        "failed": acquisition_report["counts"]["failed"],
        "failure_status_counts": dict(sorted(acquisition_failure_statuses.items())),
        "duplicate_content_urls": acquisition_report["counts"].get("duplicate_content_urls", 0),
        "per_split": acquisition_report["per_split"],
    }
    if sum(acquisition_failure_statuses.values()) != acquisition_report["counts"]["failed"]:
        raise LeakageManifestError("acquisition failure status counts do not reconcile to total failures")
    return manifest_text, report


def write_leakage_safe_manifest(
    *,
    data_dir: str | Path = "data/research/fakeddit",
    source_dir: str | Path = "../research-data/fakeddit",
    feature_dir: str | Path = "data/research/fakeddit-features",
    output_dir: str | Path = "data/research/fakeddit-experiments/task32b-leakage-safe-v1",
    seed: int = 42,
) -> dict:
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing experiment directory: {destination}")
    manifest_text, report = prepare_leakage_safe_manifest(
        data_dir=data_dir, source_dir=source_dir, feature_dir=feature_dir, seed=seed
    )
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "manifest.jsonl").write_text(manifest_text, encoding="utf-8")
    (destination / "audit_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/research/fakeddit"))
    parser.add_argument("--source-dir", type=Path, default=Path("../research-data/fakeddit"))
    parser.add_argument("--feature-dir", type=Path, default=Path("data/research/fakeddit-features"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/research/fakeddit-experiments/task32b-leakage-safe-v1"))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        report = write_leakage_safe_manifest(
            data_dir=args.data_dir,
            source_dir=args.source_dir,
            feature_dir=args.feature_dir,
            output_dir=args.output_dir,
            seed=args.seed,
        )
    except (FileExistsError, LeakageManifestError, OSError, json.JSONDecodeError) as error:
        print(f"Fakeddit leakage-safe manifest generation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output_dir": str(args.output_dir), "assigned_counts": report["assigned_counts"], "quarantined_total": report["quarantined_total"], "manifest_sha256": report["manifest_sha256"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())