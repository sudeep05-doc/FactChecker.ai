import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from app.evaluation.datasets import load_jsonl
from app.evaluation.fakeddit import FakedditPreparationError
from app.evaluation.fakeddit_preparation import (
    DEFAULT_LABEL_MAPPING,
    FakedditResearchSubsetConfig,
    normalize_image_url,
    prepare_fakeddit_research_subset,
)
from app.evaluation.schemas import DatasetSplit, GroundTruthLabel


FIELDS = ("id", "clean_title", "image_url", "2_way_label")


def row(sample_id, label="0", *, text="claim", image_url=None):
    return {
        "id": sample_id,
        "clean_title": text,
        "image_url": image_url or f"https://images.example/{sample_id}.jpg",
        "2_way_label": label,
    }


def write_tsv(path: Path, rows, fields=FIELDS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def prepare(tmp_path, *, train=None, validation=None, test=None, config=None):
    paths = {}
    for split, rows in (
        (DatasetSplit.TRAIN, train or []),
        (DatasetSplit.VALIDATION, validation or []),
        (DatasetSplit.TEST, test or []),
    ):
        path = tmp_path / f"{split.value}.tsv"
        write_tsv(path, rows)
        paths[split] = path
    return prepare_fakeddit_research_subset(
        paths[DatasetSplit.TRAIN],
        paths[DatasetSplit.VALIDATION],
        paths[DatasetSplit.TEST],
        config=config or FakedditResearchSubsetConfig(1, 1, 1, seed=42),
    )


def test_required_columns_are_validated(tmp_path):
    train = tmp_path / "train.tsv"
    validation = tmp_path / "validation.tsv"
    test = tmp_path / "test.tsv"
    write_tsv(train, [])
    write_tsv(validation, [], fields=("id", "clean_title", "image_url"))
    write_tsv(test, [])

    with pytest.raises(FakedditPreparationError, match="required Fakeddit fields"):
        prepare_fakeddit_research_subset(train, validation, test)


def test_empty_text_and_image_are_filtered_and_counted(tmp_path):
    result = prepare(
        tmp_path,
        train=[row("no-text", text=""), row("no-image", image_url="  ")],
    )

    stats = result.report["input_counts"]["train"]
    assert stats["missing_clean_title"] == 1
    assert stats["missing_image_url"] == 1
    assert result.report["exclusions"]["filtered_missing_modality_rows"] == 2
    assert not result.manifests[DatasetSplit.TRAIN]


def test_invalid_labels_are_rejected_without_guessing(tmp_path):
    result = prepare(tmp_path, train=[row("bad", label="2"), row("blank", label="")])

    assert result.report["input_counts"]["train"]["invalid_labels"] == 2
    assert result.report["exclusions"]["by_reason"]["INVALID_LABEL"] == 2
    assert result.manifests[DatasetSplit.TRAIN] == []


def test_default_mapping_has_explicit_fakeddit_semantics(tmp_path):
    result = prepare(
        tmp_path,
        train=[row("fake", label="0"), row("true", label="1")],
    )

    assert DEFAULT_LABEL_MAPPING == {"0": GroundTruthLabel.FAKE, "1": GroundTruthLabel.REAL}
    assert result.report["label_mapping"]["canonical_labels"] == {"0": "FAKE", "1": "REAL"}
    assert result.report["label_mapping"]["semantics"] == {"0": "Fake", "1": "True"}


def test_selection_is_deterministic_for_same_seed(tmp_path):
    training = [row(f"fake-{index}", label="0") for index in range(12)]
    training += [row(f"true-{index}", label="1") for index in range(12)]
    config = FakedditResearchSubsetConfig(4, 0, 0, seed=15)
    first = prepare(tmp_path / "first", train=training, config=config)
    second = prepare(tmp_path / "second", train=training, config=config)

    assert [sample.sample_id for sample in first.manifests[DatasetSplit.TRAIN]] == [
        sample.sample_id for sample in second.manifests[DatasetSplit.TRAIN]
    ]


def test_selection_is_class_balanced(tmp_path):
    training = [row(f"fake-{index}", label="0") for index in range(8)]
    training += [row(f"true-{index}", label="1") for index in range(8)]
    result = prepare(
        tmp_path,
        train=training,
        config=FakedditResearchSubsetConfig(3, 0, 0),
    )

    counts = Counter(sample.label for sample in result.manifests[DatasetSplit.TRAIN])
    assert counts == {GroundTruthLabel.FAKE: 3, GroundTruthLabel.REAL: 3}


def test_duplicate_ids_are_detected_and_later_official_split_row_excluded(tmp_path):
    result = prepare(
        tmp_path,
        train=[row("same-id", label="0")],
        validation=[row("same-id", label="0", image_url="https://images.example/other.jpg")],
    )

    assert result.report["duplicate_ids"]["duplicate_id_groups"] == 1
    assert result.report["duplicate_ids"]["duplicate_id_rows"] == 1
    assert result.report["input_counts"]["validation"]["duplicate_id_rows"] == 1
    duplicate = next(
        item for item in result.excluded_samples
        if item["sample_id"] == "same-id" and item["split"] == "validation"
    )
    assert "DUPLICATE_SAMPLE_ID" in duplicate["exclusion_reasons"]


def test_duplicate_image_urls_within_split_are_detected_and_deduplicated(tmp_path):
    result = prepare(
        tmp_path,
        train=[
            row("same-image-1", image_url="https://images.example/shared.jpg"),
            row("same-image-2", image_url="https://images.example/shared.jpg"),
        ],
    )

    assert result.report["duplicate_image_urls"]["within_split_duplicate_url_groups"] == 1
    assert result.report["duplicate_image_urls"]["within_split_duplicate_url_rows"] == 1
    assert result.report["exclusions"]["by_reason"]["DUPLICATE_IMAGE_URL_WITHIN_SPLIT"] == 1
    assert len(result.manifests[DatasetSplit.TRAIN]) == 0


@pytest.mark.parametrize(
    ("owner_split", "leaking_split"),
    [
        (DatasetSplit.TRAIN, DatasetSplit.VALIDATION),
        (DatasetSplit.TRAIN, DatasetSplit.TEST),
        (DatasetSplit.VALIDATION, DatasetSplit.TEST),
    ],
)
def test_official_split_url_precedence_removes_leakage(tmp_path, owner_split, leaking_split):
    split_rows = {split: [] for split in DatasetSplit}
    split_rows[owner_split].append(row("owner", image_url="https://images.example/shared.jpg"))
    split_rows[leaking_split].append(row("leaker", image_url="https://images.example/shared.jpg"))
    for split in DatasetSplit:
        split_rows[split].append(row(f"true-{split.value}", label="1"))

    result = prepare(
        tmp_path,
        train=split_rows[DatasetSplit.TRAIN],
        validation=split_rows[DatasetSplit.VALIDATION],
        test=split_rows[DatasetSplit.TEST],
    )

    assert result.report["duplicate_image_urls"]["cross_split_duplicate_url_groups"] == 1
    assert result.report["input_counts"][leaking_split.value]["cross_split_duplicate_url_rows"] == 1
    leaker = next(item for item in result.excluded_samples if item["sample_id"] == "leaker")
    assert "IMAGE_URL_LEAKAGE" in leaker["exclusion_reasons"]


def test_conflicting_labels_for_same_url_exclude_every_candidate(tmp_path):
    shared = "https://images.example/conflict.jpg"
    result = prepare(
        tmp_path,
        train=[row("fake", label="0", image_url=shared)],
        validation=[row("true", label="1", image_url=shared)],
    )

    duplicates = result.report["duplicate_image_urls"]
    assert duplicates["conflicting_label_url_count"] == 1
    assert duplicates["conflicting_label_rows"] == 2
    assert all(not result.manifests[split] for split in DatasetSplit)
    assert result.report["exclusions"]["by_reason"]["CONFLICTING_IMAGE_URL_LABELS"] == 2


def test_shortfall_report_keeps_available_classes_balanced(tmp_path):
    training = [row("fake-1", label="0"), row("fake-2", label="0"), row("true-1", label="1")]
    result = prepare(
        tmp_path,
        train=training,
        config=FakedditResearchSubsetConfig(3, 0, 0),
    )

    selection = result.report["selection"]["train"]
    assert selection["selected_per_class"] == {"FAKE": 1, "REAL": 1}
    assert selection["shortfall_per_class"] == {"FAKE": 2, "REAL": 2}
    assert result.report["exclusions"]["by_reason"]["NOT_SELECTED_SUBSET_LIMIT"] == 1


def test_manifest_and_report_metadata_round_trip_through_task25_loader(tmp_path):
    image_url = "https://images.example/remote.jpg?size=large"
    result = prepare(
        tmp_path,
        train=[row("source-1", image_url=image_url), row("source-true", label="1")],
    )
    output_dir = tmp_path / "manifest"
    result.write(output_dir)

    loaded = load_jsonl(output_dir / "train.jsonl", DatasetSplit.TRAIN)
    record = next(sample for sample in loaded if sample.sample_id == "source-1")
    report = json.loads((output_dir / "preparation_report.json").read_text(encoding="utf-8"))
    assert record.image == image_url
    assert record.metadata["dataset"] == "fakeddit"
    assert record.metadata["source_split"] == "train"
    assert record.metadata["source_label"] == "0"
    assert record.metadata["modality_status"]["image"] == "source_url_available_not_downloaded"
    assert report["image_acquisition"].startswith("not_performed")
    assert record.metadata["preparation"]["seed"] == report["subset_configuration"]["seed"]
    assert record.metadata["preparation"]["subset_per_class"] == {
        "train": 1,
        "validation": 1,
        "test": 1,
    }


def test_manifest_generation_is_deterministic(tmp_path):
    training = [row(f"sample-{index}", label=str(index % 2)) for index in range(20)]
    config = FakedditResearchSubsetConfig(4, 0, 0, seed=42)
    first = prepare(tmp_path / "one", train=training, config=config)
    second = prepare(tmp_path / "two", train=training, config=config)
    one_path = tmp_path / "one-output"
    two_path = tmp_path / "two-output"
    first.write(one_path)
    second.write(two_path)

    assert (one_path / "train.jsonl").read_bytes() == (two_path / "train.jsonl").read_bytes()


def test_url_normalization_preserves_path_query_and_fragment():
    assert normalize_image_url("  HTTPS://User:Pass@EXAMPLE.COM:443/Path?Token=AbC#part  ") == (
        "https://User:Pass@example.com:443/Path?Token=AbC#part"
    )
    assert normalize_image_url("https://example.com/a") != normalize_image_url("https://example.com/A")