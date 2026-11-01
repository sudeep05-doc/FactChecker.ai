import json

import pytest

from app.decision.features_v2 import PREDICTOR_ALLOWLIST
from app.evaluation.fakeddit_shared_extraction import (
    _atomic_write,
    _output_jsonl,
    _select_pilot,
)


def test_pilot_selection_is_deterministic_and_covers_each_split():
    records = [
        {"sample_id": f"{split}-{index}", "assigned_split": split}
        for split, count in (("train", 5), ("validation", 4), ("test", 3))
        for index in range(count)
    ]

    pilot = _select_pilot(records)

    assert [(row["assigned_split"], row["sample_id"]) for row in pilot] == [
        ("train", "train-0"),
        ("train", "train-1"),
        ("train", "train-2"),
        ("validation", "validation-0"),
        ("validation", "validation-1"),
        ("validation", "validation-2"),
        ("test", "test-0"),
        ("test", "test-1"),
    ]


def test_output_jsonl_preserves_predictor_allowlist_order():
    predictor = {name: None for name in PREDICTOR_ALLOWLIST}
    record = {"predictor_features": predictor}

    serialized = _output_jsonl([record])
    decoded = json.loads(serialized.decode("utf-8"))

    assert tuple(decoded["predictor_features"]) == PREDICTOR_ALLOWLIST


def test_atomic_write_never_replaces_different_existing_output(tmp_path):
    path = tmp_path / "record.json"
    _atomic_write(path, b"original")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        _atomic_write(path, b"changed")

    assert path.read_bytes() == b"original"
