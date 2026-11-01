"""Deterministic, leakage-safe preparation of small Fakeddit research splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from app.evaluation.fakeddit import FakedditAdapter, FakedditFieldMap, FakedditPreparationError
from app.evaluation.schemas import DatasetSplit, EvaluationSample, GroundTruthLabel


PREPARATION_VERSION = "fakeddit-research-subset-v1"
URL_NORMALIZATION_VERSION = "trim-scheme-host-case-v1"
DEFAULT_LABEL_MAPPING = {
    "0": GroundTruthLabel.FAKE,
    "1": GroundTruthLabel.REAL,
}
SPLIT_ORDER = (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST)
SPLIT_PRIORITY = {split: index for index, split in enumerate(SPLIT_ORDER)}


@dataclass(frozen=True)
class FakedditResearchSubsetConfig:
    train_per_class: int = 10_000
    validation_per_class: int = 2_000
    test_per_class: int = 2_000
    seed: int = 42
    label_mapping: Mapping[str, GroundTruthLabel | str] = field(
        default_factory=lambda: dict(DEFAULT_LABEL_MAPPING)
    )

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.requested_counts().values()):
            raise FakedditPreparationError("samples per class must be non-negative")
        adapter = FakedditAdapter(label_mapping=self.label_mapping)
        if set(adapter.label_mapping) != {"0", "1"} or set(adapter.label_mapping.values()) != set(GroundTruthLabel):
            raise FakedditPreparationError(
                "label_mapping must map source labels 0 and 1 to distinct REAL/FAKE labels"
            )
        object.__setattr__(self, "label_mapping", adapter.label_mapping)

    def requested_counts(self) -> Dict[DatasetSplit, int]:
        return {
            DatasetSplit.TRAIN: self.train_per_class,
            DatasetSplit.VALIDATION: self.validation_per_class,
            DatasetSplit.TEST: self.test_per_class,
        }


@dataclass
class _SourceRow:
    split: DatasetSplit
    source_file: str
    row_number: int
    sample_id: str
    text: str
    image_url: str
    normalized_url: str
    source_label: str
    label: Optional[GroundTruthLabel]
    reasons: List[str] = field(default_factory=list)


@dataclass
class FakedditResearchPreparationResult:
    manifests: Dict[DatasetSplit, List[EvaluationSample]]
    report: Dict[str, object]
    excluded_samples: List[Dict[str, object]]

    def write(self, output_dir: str | Path, *, overwrite: bool = False) -> None:
        destination = Path(output_dir)
        outputs = [
            destination / "train.jsonl",
            destination / "validation.jsonl",
            destination / "test.jsonl",
            destination / "preparation_report.json",
            destination / "excluded_samples.jsonl",
        ]
        if not overwrite:
            existing = [str(path) for path in outputs if path.exists()]
            if existing:
                raise FakedditPreparationError(
                    f"output files already exist (pass --overwrite to replace): {existing}"
                )
        destination.mkdir(parents=True, exist_ok=True)
        for split, filename in (
            (DatasetSplit.TRAIN, "train.jsonl"),
            (DatasetSplit.VALIDATION, "validation.jsonl"),
            (DatasetSplit.TEST, "test.jsonl"),
        ):
            _write_jsonl(destination / filename, (sample.model_dump(mode="json") for sample in self.manifests[split]))
        (destination / "preparation_report.json").write_text(
            json.dumps(self.report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write_jsonl(destination / "excluded_samples.jsonl", self.excluded_samples)


def normalize_image_url(value: str) -> str:
    """Trim URL whitespace and lowercase only its scheme and hostname."""
    candidate = value.strip()
    match = re.match(r"^(?:(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*):)?//(?P<authority>[^/?#]*)(?P<tail>.*)$", candidate)
    if not match:
        return candidate

    authority = match.group("authority")
    user_info, separator, host_port = authority.rpartition("@")
    prefix = f"{user_info}{separator}" if separator else ""
    if host_port.startswith("["):
        closing_bracket = host_port.find("]")
        if closing_bracket >= 0:
            host_port = host_port[: closing_bracket + 1].lower() + host_port[closing_bracket + 1 :]
    else:
        host, colon, port = host_port.partition(":")
        host_port = host.lower() + (colon + port if colon else "")
    scheme = match.group("scheme")
    normalized_prefix = f"{scheme.lower()}://" if scheme else "//"
    return normalized_prefix + prefix + host_port + match.group("tail")


def prepare_fakeddit_research_subset(
    train_path: str | Path,
    validation_path: str | Path,
    test_path: str | Path,
    *,
    config: FakedditResearchSubsetConfig = FakedditResearchSubsetConfig(),
) -> FakedditResearchPreparationResult:
    """Prepare balanced manifests without changing official partitions or fetching media."""
    field_map = FakedditFieldMap()
    rows: List[_SourceRow] = []
    split_stats: Dict[str, Dict[str, object]] = {}
    paths = {
        DatasetSplit.TRAIN: Path(train_path),
        DatasetSplit.VALIDATION: Path(validation_path),
        DatasetSplit.TEST: Path(test_path),
    }

    for split in SPLIT_ORDER:
        path = paths[split]
        stats: Dict[str, object] = {
            "input_file": str(path),
            "input_sha256": None,
            "input_rows": 0,
            "missing_clean_title": 0,
            "missing_image_url": 0,
            "invalid_labels": 0,
            "usable_text_image_rows": 0,
            "duplicate_id_rows": 0,
            "duplicate_image_url_rows": 0,
            "cross_split_duplicate_url_rows": 0,
        }
        split_stats[split.value] = stats
        for row_number, row in _read_tsv(path, field_map):
            stats["input_rows"] += 1
            sample_id = _clean(row.get(field_map.sample_id))
            text = _clean(row.get(field_map.text))
            image_url = _clean(row.get(field_map.image))
            source_label = _clean(row.get(field_map.label))
            label = config.label_mapping.get(source_label)
            reasons = []
            if not sample_id:
                reasons.append("MISSING_SAMPLE_ID")
            if not text:
                stats["missing_clean_title"] += 1
                reasons.append("MISSING_CLEAN_TITLE")
            if not image_url:
                stats["missing_image_url"] += 1
                reasons.append("MISSING_IMAGE_URL")
            if label is None:
                stats["invalid_labels"] += 1
                reasons.append("INVALID_LABEL")
            elif sample_id and text and image_url:
                stats["usable_text_image_rows"] += 1
            rows.append(_SourceRow(
                split=split,
                source_file=str(path),
                row_number=row_number,
                sample_id=sample_id,
                text=text,
                image_url=image_url,
                normalized_url=normalize_image_url(image_url) if image_url else "",
                source_label=source_label,
                label=label,
                reasons=reasons,
            ))
        stats["input_sha256"] = _sha256(path)

    duplicate_id_audit = _deduplicate_ids(rows, split_stats)
    url_groups = _group_by_url(rows)
    duplicate_url_audit, conflict_urls, url_owners = _audit_urls(url_groups, split_stats)

    for row in rows:
        if not row.sample_id or not row.text or not row.image_url or row.label is None:
            continue
        if row.normalized_url in conflict_urls:
            row.reasons.append("CONFLICTING_IMAGE_URL_LABELS")
        owner = url_owners[row.normalized_url]
        if SPLIT_PRIORITY[owner] < SPLIT_PRIORITY[row.split]:
            row.reasons.append("IMAGE_URL_LEAKAGE")

    for group in url_groups.values():
        for split in SPLIT_ORDER:
            eligible = sorted(
                (
                    row for row in group
                    if row.split == split
                    and row.sample_id
                    and row.text
                    and row.image_url
                    and row.label is not None
                    and "DUPLICATE_SAMPLE_ID" not in row.reasons
                ),
                key=lambda row: row.row_number,
            )
            for duplicate in eligible[1:]:
                duplicate.reasons.append("DUPLICATE_IMAGE_URL_WITHIN_SPLIT")

    requested = config.requested_counts()
    manifests: Dict[DatasetSplit, List[EvaluationSample]] = {}
    selection_stats: Dict[str, object] = {}
    for split in SPLIT_ORDER:
        available = {
            label: [
                row for row in rows
                if row.split == split and row.label == label and not row.reasons
            ]
            for label in GroundTruthLabel
        }
        count = min(requested[split], *(len(available[label]) for label in GroundTruthLabel))
        selected_rows = []
        for label in GroundTruthLabel:
            ordered = sorted(available[label], key=lambda row: _selection_key(row, config.seed))
            selected_rows.extend(ordered[:count])
            for not_selected in ordered[count:]:
                not_selected.reasons.append("NOT_SELECTED_SUBSET_LIMIT")
        selected_rows.sort(key=lambda row: _selection_key(row, config.seed))
        manifests[split] = [_to_sample(row, config) for row in selected_rows]
        selected_counts = {
            label.value: sum(row.label == label for row in selected_rows)
            for label in GroundTruthLabel
        }
        selection_stats[split.value] = {
            "requested_per_class": requested[split],
            "available_per_class": {label.value: len(available[label]) for label in GroundTruthLabel},
            "selected_per_class": selected_counts,
            "shortfall_per_class": {
                label.value: requested[split] - selected_counts[label.value]
                for label in GroundTruthLabel
            },
            "selected_total": len(selected_rows),
        }

    excluded_samples = [
        _exclusion_record(row)
        for row in sorted(rows, key=lambda item: (SPLIT_PRIORITY[item.split], item.row_number))
        if row.reasons
    ]
    exclusion_counts = _exclusion_counts(rows, split_stats)
    report = {
        "implementation": PREPARATION_VERSION,
        "dataset": "fakeddit",
        "input_files": {split.value: str(paths[split]) for split in SPLIT_ORDER},
        "input_counts": split_stats,
        "label_mapping": {
            "source_column": field_map.label,
            "canonical_labels": {
                source: label.value for source, label in sorted(config.label_mapping.items())
            },
            "semantics": {
                source: ("Fake" if label == GroundTruthLabel.FAKE else "True")
                for source, label in sorted(config.label_mapping.items())
            },
        },
        "required_columns": [field_map.sample_id, field_map.text, field_map.image, field_map.label],
        "filter": {
            "requires_nonempty_clean_title": True,
            "requires_nonempty_image_url": True,
            "invalid_label_policy": "exclude; accept only configured source labels 0 and 1",
        },
        "url_normalization": {
            "version": URL_NORMALIZATION_VERSION,
            "rules": [
                "trim leading and trailing whitespace",
                "lowercase URL scheme and hostname only",
                "preserve path, query, fragment, port, and user information",
                "do not remove query parameters or URL fragments",
            ],
        },
        "duplicate_ids": {
            "duplicate_id_groups": len(duplicate_id_audit),
            "duplicate_id_rows": sum(len(item["rows"]) - 1 for item in duplicate_id_audit),
            "resolution": "keep first row in official split precedence, then source row order",
            "audit": duplicate_id_audit,
        },
        "duplicate_image_urls": {
            "duplicate_url_groups": sum(item["occurrence_count"] > 1 for item in duplicate_url_audit),
            "within_split_duplicate_url_groups": sum(
                any(count > 1 for count in item["rows_by_split"].values())
                for item in duplicate_url_audit
            ),
            "within_split_duplicate_url_rows": sum(
                stats["duplicate_image_url_rows"] for stats in split_stats.values()
            ),
            "cross_split_duplicate_url_groups": sum(len(item["splits"]) > 1 for item in duplicate_url_audit),
            "cross_split_duplicate_url_rows": sum(
                stats["cross_split_duplicate_url_rows"] for stats in split_stats.values()
            ),
            "conflicting_label_url_count": len(conflict_urls),
            "conflicting_label_rows": sum(
                item["occurrence_count"] for item in duplicate_url_audit if item["conflicting_labels"]
            ),
            "resolution": {
                "same_split": "keep first eligible source row and exclude repeated image URLs",
                "cross_split": "TRAIN takes precedence over VALIDATION, which takes precedence over TEST",
                "conflicting_labels": "exclude all eligible rows for the normalized URL",
            },
            "audit": duplicate_url_audit,
        },
        "exclusions": exclusion_counts,
        "subset_configuration": {
            "train_per_class": config.train_per_class,
            "validation_per_class": config.validation_per_class,
            "test_per_class": config.test_per_class,
            "seed": config.seed,
            "selection": "ascending SHA-256(seed + NUL + original Fakeddit id)",
            "shortfall_policy": "select equally from both classes up to the smallest available class count",
        },
        "final_selected_counts": {
            split.value: {
                "total": len(manifests[split]),
                "classes": selection_stats[split.value]["selected_per_class"],
            }
            for split in SPLIT_ORDER
        },
        "selection": selection_stats,
        "image_acquisition": "not_performed; manifests retain source URLs only",
        "training_or_evaluation": "not_performed",
    }
    return FakedditResearchPreparationResult(manifests, report, excluded_samples)


def _read_tsv(path: Path, field_map: FakedditFieldMap):
    if not path.is_file():
        raise FakedditPreparationError(f"Fakeddit TSV file does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fields = reader.fieldnames or []
            required = (field_map.sample_id, field_map.text, field_map.image, field_map.label)
            missing = [name for name in required if name not in fields]
            if missing:
                raise FakedditPreparationError(f"required Fakeddit fields are missing: {missing}")
            for row_number, row in enumerate(reader, start=2):
                yield row_number, row
    except FakedditPreparationError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise FakedditPreparationError(f"unable to read Fakeddit TSV {path}: {error}") from error


def _deduplicate_ids(rows: List[_SourceRow], split_stats: Dict[str, Dict[str, object]]):
    groups: Dict[str, List[_SourceRow]] = {}
    for row in rows:
        if row.sample_id:
            groups.setdefault(row.sample_id, []).append(row)
    audit = []
    for sample_id in sorted(groups):
        group = sorted(groups[sample_id], key=lambda row: (SPLIT_PRIORITY[row.split], row.row_number))
        if len(group) < 2:
            continue
        for duplicate in group[1:]:
            duplicate.reasons.append("DUPLICATE_SAMPLE_ID")
            split_stats[duplicate.split.value]["duplicate_id_rows"] += 1
        audit.append({
            "sample_id": sample_id,
            "rows": [
                {"split": row.split.value, "source_row": row.row_number}
                for row in group
            ],
        })
    return audit


def _group_by_url(rows: List[_SourceRow]) -> Dict[str, List[_SourceRow]]:
    groups: Dict[str, List[_SourceRow]] = {}
    for row in rows:
        if row.normalized_url:
            groups.setdefault(row.normalized_url, []).append(row)
    return groups


def _audit_urls(url_groups, split_stats):
    audit = []
    conflict_urls = set()
    owners = {}
    for url in sorted(url_groups):
        group = url_groups[url]
        rows_by_split = {
            split.value: sum(row.split == split for row in group)
            for split in SPLIT_ORDER
        }
        present_splits = [split for split in SPLIT_ORDER if rows_by_split[split.value]]
        owners[url] = present_splits[0]
        for split in SPLIT_ORDER:
            count = rows_by_split[split.value]
            split_stats[split.value]["duplicate_image_url_rows"] += max(0, count - 1)
            if split != owners[url] and count:
                split_stats[split.value]["cross_split_duplicate_url_rows"] += count
        labels = sorted({row.label.value for row in group if row.label is not None})
        conflicting = len(labels) > 1
        if conflicting:
            conflict_urls.add(url)
        if len(group) > 1:
            audit.append({
                "normalized_url": url,
                "original_urls": sorted({row.image_url for row in group}),
                "splits": [split.value for split in present_splits],
                "owner_split": owners[url].value,
                "rows_by_split": rows_by_split,
                "canonical_labels": labels,
                "conflicting_labels": conflicting,
                "occurrence_count": len(group),
            })
    return audit, conflict_urls, owners


def _selection_key(row: _SourceRow, seed: int):
    digest = hashlib.sha256(f"{seed}\0{row.sample_id}".encode("utf-8")).hexdigest()
    return digest, row.sample_id


def _to_sample(row: _SourceRow, config: FakedditResearchSubsetConfig) -> EvaluationSample:
    return EvaluationSample(
        sample_id=row.sample_id,
        label=row.label,
        text=row.text,
        image=row.image_url,
        split=row.split,
        source_reference=row.sample_id,
        metadata={
            "dataset": "fakeddit",
            "source_id": row.sample_id,
            "source_split": row.split.value,
            "source_row": row.row_number,
            "source_file": Path(row.source_file).name,
            "source_label": row.source_label,
            "image_reference": row.image_url,
            "modality_status": {
                "text": "available",
                "image": "source_url_available_not_downloaded",
            },
            "preparation": {
                "version": PREPARATION_VERSION,
                "seed": config.seed,
                "subset_per_class": {
                    split.value: config.requested_counts()[split] for split in SPLIT_ORDER
                },
                "url_normalization_version": URL_NORMALIZATION_VERSION,
                "label_mapping": {
                    source: label.value for source, label in sorted(config.label_mapping.items())
                },
            },
        },
    )


def _exclusion_record(row: _SourceRow) -> Dict[str, object]:
    return {
        "sample_id": row.sample_id or None,
        "split": row.split.value,
        "source_file": Path(row.source_file).name,
        "source_row": row.row_number,
        "source_label": row.source_label,
        "image_url": row.image_url or None,
        "exclusion_reasons": sorted(set(row.reasons)),
    }


def _exclusion_counts(rows: List[_SourceRow], split_stats: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    by_reason = {}
    for row in rows:
        for reason in set(row.reasons):
            by_reason[reason] = by_reason.get(reason, 0) + 1
    duplicate_or_ambiguity_reasons = {
        "DUPLICATE_SAMPLE_ID",
        "DUPLICATE_IMAGE_URL_WITHIN_SPLIT",
        "CONFLICTING_IMAGE_URL_LABELS",
    }
    return {
        "excluded_row_count": sum(bool(row.reasons) for row in rows),
        "filtered_missing_modality_rows": sum(
            "MISSING_CLEAN_TITLE" in row.reasons or "MISSING_IMAGE_URL" in row.reasons
            for row in rows
        ),
        "filtered": {
            "missing_clean_title_rows": sum(stats["missing_clean_title"] for stats in split_stats.values()),
            "missing_image_url_rows": sum(stats["missing_image_url"] for stats in split_stats.values()),
            "invalid_label_rows": by_reason.get("INVALID_LABEL", 0),
        },
        "excluded_due_to_leakage": by_reason.get("IMAGE_URL_LEAKAGE", 0),
        "excluded_due_to_duplicate_or_ambiguity": sum(
            any(reason in duplicate_or_ambiguity_reasons for reason in row.reasons)
            for row in rows
        ),
        "excluded_due_to_subset_limit": by_reason.get("NOT_SELECTED_SUBSET_LIMIT", 0),
        "by_reason": dict(sorted(by_reason.items())),
        "counts_by_reason_can_overlap": True,
    }


def _clean(value: Optional[str]) -> str:
    return str(value or "").strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise FakedditPreparationError(f"unable to hash Fakeddit TSV {path}: {error}") from error
    return digest.hexdigest()


def _write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path, help="official Fakeddit train TSV")
    parser.add_argument("--validation", required=True, type=Path, help="official Fakeddit validation TSV")
    parser.add_argument("--test", required=True, type=Path, help="official Fakeddit test TSV")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--train-per-class", type=int, default=10_000)
    parser.add_argument("--validation-per-class", type=int, default=2_000)
    parser.add_argument("--test-per-class", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--label-0", choices=[label.value for label in GroundTruthLabel], default="FAKE")
    parser.add_argument("--label-1", choices=[label.value for label in GroundTruthLabel], default="REAL")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        config = FakedditResearchSubsetConfig(
            train_per_class=args.train_per_class,
            validation_per_class=args.validation_per_class,
            test_per_class=args.test_per_class,
            seed=args.seed,
            label_mapping={"0": args.label_0, "1": args.label_1},
        )
        result = prepare_fakeddit_research_subset(
            args.train, args.validation, args.test, config=config
        )
        result.write(args.output_dir, overwrite=args.overwrite)
    except (FakedditPreparationError, OSError) as error:
        print(f"Fakeddit preparation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "final_selected_counts": result.report["final_selected_counts"],
        "exclusions": result.report["exclusions"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())