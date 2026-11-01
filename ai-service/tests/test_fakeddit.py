import csv
from pathlib import Path

import pytest
from PIL import Image

from app.evaluation import (
    FakedditAdapter,
    FakedditFieldMap,
    FakedditPreparationError,
    GroundTruthLabel,
)


def write_tsv(path: Path, rows, fields=("id", "clean_title", "image_url", "2_way_label")):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def adapter(mapping=None, **kwargs):
    return FakedditAdapter(label_mapping=mapping or {"0": "REAL", "1": "FAKE"}, **kwargs)


def test_valid_row_conversion_and_explicit_label_mapping(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [{"id": "post-1", "clean_title": "A claim", "image_url": "", "2_way_label": "1"}])

    result = adapter().prepare(path, require_image=False)

    assert result.samples[0].sample_id == "post-1"
    assert result.samples[0].label == GroundTruthLabel.FAKE
    assert result.samples[0].source_reference == "post-1"
    assert result.provenance["label_mapping"] == {"0": "REAL", "1": "FAKE"}


def test_mapping_is_required_and_unknown_source_labels_rejected(tmp_path: Path):
    with pytest.raises(FakedditPreparationError, match="label_mapping"):
        FakedditAdapter(label_mapping={})
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [{"id": "post-1", "clean_title": "claim", "image_url": "", "2_way_label": "unknown"}])

    result = adapter().prepare(path, require_image=False)

    assert result.samples == []
    assert result.counts["invalid_labels"] == 1
    assert result.invalid_rows[0]["code"] == "INVALID_OR_UNMAPPED_LABEL"


def test_missing_text_and_image_are_counted_and_not_marked_fake(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [{"id": "post-1", "clean_title": "", "image_url": "missing.jpg", "2_way_label": "0"}])

    result = adapter().prepare(path)

    assert result.samples == []
    assert result.counts["missing_text"] == 1
    assert result.counts["missing_image"] == 1
    assert result.counts["image_unavailable"] == 1
    assert result.counts["invalid_labels"] == 0


def test_multimodal_subset_uses_only_text_and_available_image(tmp_path: Path):
    image = tmp_path / "post-1.jpg"
    Image.new("RGB", (4, 4), color="white").save(image)
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [
        {"id": "post-1", "clean_title": "claim", "image_url": str(image), "2_way_label": "0"},
        {"id": "post-2", "clean_title": "claim 2", "image_url": "missing.jpg", "2_way_label": "1"},
    ])

    result = adapter().prepare(path)

    assert [sample.sample_id for sample in result.samples] == ["post-1"]
    assert result.samples[0].metadata["modality_status"] == {"text": "available", "image": "available"}
    assert result.counts["text_image_available"] == 1


def test_injected_image_acquisition_and_failure_provenance(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [
        {"id": "post-1", "clean_title": "claim", "image_url": "https://example.test/a.jpg", "2_way_label": "0"},
        {"id": "post-2", "clean_title": "claim 2", "image_url": "https://example.test/b.jpg", "2_way_label": "1"},
    ])

    def acquire(url, source_id):
        selected = tmp_path / "selected.jpg"
        Image.new("RGB", (4, 4), color="white").save(selected)
        return str(selected) if source_id == "post-1" else None

    result = adapter(image_acquirer=acquire).prepare(path)

    assert [sample.sample_id for sample in result.samples] == ["post-1"]
    assert result.counts["image_unavailable"] == 1
    assert result.samples[0].metadata["image_reference"].startswith("https://")


def test_duplicate_ids_and_missing_fields_are_reported(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [
        {"id": "same", "clean_title": "one", "image_url": "", "2_way_label": "0"},
        {"id": "same", "clean_title": "two", "image_url": "", "2_way_label": "1"},
    ])
    result = adapter().prepare(path, require_image=False)
    assert result.counts["duplicate_ids"] == 1
    assert len(result.samples) == 1

    malformed = tmp_path / "malformed.tsv"
    write_tsv(malformed, [{"id": "x", "clean_title": "claim", "image_url": ""}], fields=("id", "clean_title", "image_url"))
    with pytest.raises(FakedditPreparationError, match="missing"):
        adapter().prepare(malformed, require_image=False)


def test_deterministic_subset_and_manifest_serialization(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [{"id": f"post-{i}", "clean_title": f"claim {i}", "image_url": "", "2_way_label": str(i % 2)} for i in range(6)])

    first = adapter().prepare(path, require_image=False, max_samples=3, seed=9)
    second = adapter().prepare(path, require_image=False, max_samples=3, seed=9)

    assert [sample.sample_id for sample in first.samples] == [sample.sample_id for sample in second.samples]
    assert json_lines(first.manifest_jsonl())[0]["metadata"]["dataset"] == "Fakeddit"


def json_lines(value):
    import json
    return [json.loads(line) for line in value.splitlines()]


def test_no_silent_fake_assignment_on_image_failure(tmp_path: Path):
    path = tmp_path / "fakeddit.tsv"
    write_tsv(path, [{"id": "post-1", "clean_title": "claim", "image_url": "missing.jpg", "2_way_label": "0"}])

    result = adapter().prepare(path, require_image=False)

    assert result.samples[0].label == GroundTruthLabel.REAL
    assert result.samples[0].image is None
    assert result.samples[0].metadata["modality_status"]["image"] == "unavailable"
