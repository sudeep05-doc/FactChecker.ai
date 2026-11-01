import hashlib
import json

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.evaluation import fakeddit_baseline as baseline


def _record(sample_id, label, text_value, image_value, cosine):
    vector = [0.0] * 512
    vector[0] = text_value
    vector[1] = (1.0 - text_value * text_value) ** 0.5
    image = [0.0] * 512
    image[0] = image_value
    image[1] = (1.0 - image_value * image_value) ** 0.5
    return {
        "sample_id": sample_id,
        "label": label,
        "sample_identity": {"split": "train"},
        "feature_schema_version": "rr-decision-v2",
        "predictor_features": {
            "clip_text_embedding": vector,
            "clip_image_embedding": image,
            "clip_text_image_cosine": cosine,
        },
        "modality_status": {"text": "available", "image": "available"},
        "source_provenance": {
            "assigned_split": "train",
            "component_id": f"component-{sample_id}",
            "image_sha256": f"sha-{sample_id}",
            "model_name": "ViT-B-32-quickgelu",
            "checkpoint": "openai",
        },
        "reasoning_representation": {
            "contradiction": None,
            "contradiction_records": [],
            "consistency": {"alignment": None, "contextual": None, "score": None},
            "reasoning_score": None,
            "decision_evidence": None,
            "contextual_features": [],
            "diagnostic_proxies": [],
        },
    }


def _manifest(record):
    return {
        "sample_id": record["sample_id"],
        "assigned_split": "train",
        "canonical_label": record["label"],
        "component_id": record["source_provenance"]["component_id"],
        "image_sha256": record["source_provenance"]["image_sha256"],
    }


def test_feature_matrix_uses_only_approved_predictors():
    record = _record("private-id", "REAL", 0.6, 0.8, 0.6 * 0.8 + (1 - 0.6**2) ** 0.5 * (1 - 0.8**2) ** 0.5)

    matrix = baseline.feature_matrix([record], "fusion")

    assert matrix.shape == (1, 1024)
    assert matrix.dtype == np.float32
    expected = np.concatenate((
        np.asarray(record["predictor_features"]["clip_text_embedding"], dtype=np.float32),
        np.asarray(record["predictor_features"]["clip_image_embedding"], dtype=np.float32),
    ))
    np.testing.assert_array_equal(matrix[0], expected)
    assert baseline.feature_matrix([record], "text_only").shape == (1, 512)
    assert baseline.feature_matrix([record], "image_only").shape == (1, 512)
    assert baseline.feature_matrix([record], "cosine_only").shape == (1, 1)


def test_validate_record_rejects_wrong_schema_and_predictor_keys():
    record = _record("sample-1", "REAL", 0.6, 0.8, 0.0)

    invalid_schema = dict(record, feature_schema_version="rr-decision-v1")
    with pytest.raises(ValueError, match="schema version"):
        baseline.validate_record(invalid_schema, _manifest(record), "train")

    invalid_predictors = dict(record)
    invalid_predictors["predictor_features"] = dict(record["predictor_features"], label="REAL")
    with pytest.raises(ValueError, match="allowlist"):
        baseline.validate_record(invalid_predictors, _manifest(record), "train")


def test_validate_record_rejects_cosine_inconsistent_with_embeddings():
    record = _record("sample-2", "FAKE", 0.6, 0.8, -0.5)

    with pytest.raises(ValueError, match="cosine does not match"):
        baseline.validate_record(record, _manifest(record), "train")


def test_metric_report_uses_real_as_positive_and_fixed_confusion_order():
    y_true = np.asarray([0, 0, 1, 1])
    probabilities = np.asarray([0.1, 0.8, 0.7, 0.9])

    report = baseline.metric_report(y_true, probabilities)

    assert report["positive_class"] == "REAL"
    assert report["confusion_matrix_labels"] == ["FAKE", "REAL"]
    assert report["confusion_matrix"] == [[1, 1], [0, 2]]
    assert report["precision_REAL"] == pytest.approx(2 / 3)
    assert report["recall_REAL"] == 1.0


def test_selection_loads_train_and_validation_only(tmp_path, monkeypatch):
    protocol = tmp_path / "experiment_protocol.md"
    protocol.write_text("frozen protocol\n", encoding="utf-8")
    config = tmp_path / "configuration.json"
    config.write_text(json.dumps({"selection": {"primary_metric": "roc_auc"}}), encoding="utf-8")
    inventory_hash = "fixed-source-inventory"
    (tmp_path / "data_validation_report.json").write_text(
        json.dumps({"status": "passed", "source_inventory_sha256": inventory_hash}),
        encoding="utf-8",
    )
    records = []
    for index in range(8):
        label = "REAL" if index % 2 else "FAKE"
        value = 0.9 if label == "REAL" else 0.1
        records.append(_record(f"sample-{index}", label, value, value, 0.9))

    requested_splits = []

    def load_split(_root, split, excluded_ids=None):
        requested_splits.append(split)
        if split == "test":
            raise AssertionError("selection must not load test records")
        return records

    monkeypatch.setattr(baseline, "_load_split", load_split)
    monkeypatch.setattr(
        baseline,
        "validate_inputs",
        lambda *_args: {"source_inventory_sha256": inventory_hash},
    )
    monkeypatch.setattr(baseline, "_git_commit", lambda *_args: "test-commit")

    report = baseline.select_model(tmp_path, tmp_path)

    assert set(requested_splits) == {"train", "validation"}
    assert "test" not in requested_splits
    assert report["test_used_for_selection"] is False
    assert report["model_artifact"]["sha256"] == hashlib.sha256(
        (tmp_path / report["model_artifact"]["path"]).read_bytes()
    ).hexdigest()


def test_frozen_protocol_hash_gate_prevents_test_loading(tmp_path, monkeypatch):
    protocol = tmp_path / "experiment_protocol.md"
    protocol.write_text("frozen protocol\n", encoding="utf-8")
    config = tmp_path / "configuration.json"
    config.write_text("{}", encoding="utf-8")
    validation = {
        "source_inventory_sha256": "source",
    }
    (tmp_path / "data_validation_report.json").write_text(json.dumps(validation), encoding="utf-8")
    selection = {
        "protocol_frozen": True,
        "test_used_for_selection": False,
        "protocol_sha256": "wrong-hash",
        "configuration_sha256": baseline.sha256_file(config),
        "source_inventory_sha256": "source",
    }
    selection_path = tmp_path / "training_and_selection_report.json"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    test_loaded = []
    monkeypatch.setattr(
        baseline,
        "_load_split",
        lambda _root, split, *_args: test_loaded.append(split),
    )

    with pytest.raises(ValueError, match="protocol hash"):
        baseline.evaluate_test(tmp_path, tmp_path)

    assert test_loaded == []


def test_model_configuration_and_metric_determinism():
    first = baseline._model_instance(0.1)
    second = baseline._model_instance(0.1)
    assert isinstance(first, LogisticRegression)
    assert first.get_params() == second.get_params()

    y = np.asarray([0, 0, 1, 1])
    p = np.asarray([0.2, 0.3, 0.7, 0.8])
    assert baseline.metric_report(y, p) == baseline.metric_report(y, p)
