"""Train isolated text-only and image-only Task 47 models from Task 36C."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


AI_SERVICE_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = AI_SERVICE_ROOT / "data/research"
EXPERIMENTS_ROOT = RESEARCH_ROOT / "fakeddit-experiments"
FEATURE_ROOT = EXPERIMENTS_ROOT / "task36c-v2-shared-space"
TASK38_ROOT = EXPERIMENTS_ROOT / "task38-baseline-classifier-20261019"
OUTPUT_ROOT = EXPERIMENTS_ROOT / "task47-modality-specific-classifiers-20261029"
SPLITS = ("train", "validation", "test")
LABEL_TO_INT = {"FAKE": 0, "REAL": 1}
EXPECTED_SCHEMA = "rr-decision-v2"
EXPECTED_MODEL = "ViT-B-32-quickgelu"
EXPECTED_CHECKPOINT = "openai"
EXPECTED_CHECKPOINT_SHA256 = "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"
FEATURES = {
    "text_only": ("clip_text_embedding",),
    "image_only": ("clip_image_embedding",),
}
C_GRID = (0.01, 0.1, 1.0, 10.0)
EXPECTED_COUNTS = {
    "train": {"total": 19068, "FAKE": 9652, "REAL": 9416},
    "validation": {"total": 3801, "FAKE": 1924, "REAL": 1877},
    "test": {"total": 3799, "FAKE": 1923, "REAL": 1876},
}
KNOWN_PROTECTED_HASHES = {
    "fakeddit-experiments/task32b-leakage-safe-v3/manifest.jsonl":
        "3a39fe293c9b86820f1b4700ffed2d4d410e8ddf3e8d3f90b3c0267dc05ee6e2",
    "fakeddit-experiments/task32b-leakage-safe-v3/audit_report.json":
        "fd12f7ff13f122073ef995a363d8c0488fffc30c22a6f78f8a525fa82b692ef0",
    "fakeddit-features/train.jsonl":
        "f0285b2a7e3fc78e9f6907b4ad68106866c17f97aea61185c891bc2779f2d537",
    "fakeddit-features/validation.jsonl":
        "7a357a260161777d2adbbb093d30c616cd2dbac0f14a2ae783093b73e1947d1b",
    "fakeddit-features/test.jsonl":
        "dcbaec128e2805c84668156c63f1bce1f9de9f99cf791788f67549744dbc9c42",
    "fakeddit-features/feature_cache.json":
        "3b33575dc8e0f647d53e23633098cbc776ed393a878c79606a8a98f4fc203b06",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing experiment artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _load_records(
    split: str,
) -> Tuple[np.ndarray, np.ndarray, List[int], List[str], Dict[str, int]]:
    source_path = FEATURE_ROOT / "full" / f"{split}.jsonl"
    text_vectors: List[List[float]] = []
    image_vectors: List[List[float]] = []
    labels: List[int] = []
    sample_ids: List[str] = []
    counts = {"total": 0, "FAKE": 0, "REAL": 0}
    seen = set()

    with source_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            record = json.loads(line)
            sample_id = record.get("sample_id") or (record.get("sample_identity") or {}).get("sample_id")
            if not isinstance(sample_id, str) or not sample_id:
                raise ValueError(f"{split}:{line_number} has no sample_id")
            if sample_id in seen:
                raise ValueError(f"{split}:{line_number} repeats sample_id {sample_id}")
            seen.add(sample_id)
            if record.get("feature_schema_version") != EXPECTED_SCHEMA:
                raise ValueError(f"{split}:{line_number} has an unexpected feature schema")
            if (record.get("sample_identity") or {}).get("split") != split:
                raise ValueError(f"{split}:{line_number} has a mismatched split assignment")
            label = record.get("label")
            if label not in LABEL_TO_INT:
                raise ValueError(f"{split}:{line_number} has an unsupported label")
            predictors = record.get("predictor_features")
            if not isinstance(predictors, dict):
                raise ValueError(f"{split}:{line_number} has no predictor_features object")
            if tuple(predictors) != (
                "clip_text_embedding",
                "clip_image_embedding",
                "clip_text_image_cosine",
            ):
                raise ValueError(f"{split}:{line_number} predictor feature order differs from Task 38")

            text = predictors["clip_text_embedding"]
            image = predictors["clip_image_embedding"]
            for feature_name, vector in (("text", text), ("image", image)):
                if not isinstance(vector, list) or len(vector) != 512:
                    raise ValueError(f"{split}:{line_number} {feature_name} embedding is not 512-D")
                if not all(isinstance(value, (int, float)) and np.isfinite(value) for value in vector):
                    raise ValueError(f"{split}:{line_number} {feature_name} embedding is non-finite")
                norm = float(np.linalg.norm(np.asarray(vector, dtype=np.float64)))
                if abs(norm - 1.0) > 1e-4:
                    raise ValueError(f"{split}:{line_number} {feature_name} embedding is not L2-normalized")
            if (record.get("modality_status") or {}).get("text") != "available" or (
                record.get("modality_status") or {}
            ).get("image") != "available":
                raise ValueError(f"{split}:{line_number} has a missing modality")

            text_vectors.append(predictors["clip_text_embedding"])
            labels.append(LABEL_TO_INT[label])
            sample_ids.append(sample_id)
            counts["total"] += 1
            counts[label] += 1
            image_vectors.append(predictors["clip_image_embedding"])

    if counts != EXPECTED_COUNTS[split]:
        raise ValueError(f"{split} counts differ from the frozen Task 38 counts: {counts}")
    text_matrix = np.asarray(text_vectors, dtype=np.float32)
    image_matrix = np.asarray(image_vectors, dtype=np.float32)
    if text_matrix.shape != (counts["total"], 512) or image_matrix.shape != (counts["total"], 512):
        raise ValueError(f"{split} feature matrix dimensions are invalid")
    return text_matrix, image_matrix, labels, sample_ids, counts


def _validate_sources() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    metadata = json.loads((FEATURE_ROOT / "experiment_metadata.json").read_text(encoding="utf-8"))
    audit = json.loads((FEATURE_ROOT / "full/audit_report.json").read_text(encoding="utf-8"))
    config = json.loads((TASK38_ROOT / "configuration.json").read_text(encoding="utf-8"))
    validation = json.loads((TASK38_ROOT / "data_validation_report.json").read_text(encoding="utf-8"))
    selection = json.loads((TASK38_ROOT / "model_selection_summary.json").read_text(encoding="utf-8"))

    if metadata["schema_version"] != EXPECTED_SCHEMA:
        raise ValueError("Task 36C schema version is not rr-decision-v2")
    model = metadata["model"]
    if model["architecture"] != EXPECTED_MODEL or model["pretrained_configuration"] != EXPECTED_CHECKPOINT:
        raise ValueError("Task 36C encoder contract does not match the required OpenCLIP model")
    if model["checkpoint_sha256"] != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("Task 36C checkpoint metadata hash differs from the frozen contract")
    for split in SPLITS:
        relative = f"full/{split}.jsonl"
        expected = audit["output_files"][relative]
        path = FEATURE_ROOT / relative
        if path.stat().st_size != expected["size_bytes"] or sha256_file(path) != expected["sha256"]:
            raise ValueError(f"Task 36C {split} artifact failed its recorded integrity check")
        task38_record = validation["input_sha256_inventory"][relative]
        if task38_record["sha256"] != expected["sha256"]:
            raise ValueError(f"Task 38 records a different Task 36C {split} input")
    if validation.get("status") != "passed":
        raise ValueError("Task 38 source validation did not pass")
    if config["target"]["label_mapping"] != {"FAKE": 0, "REAL": 1}:
        raise ValueError("Task 38 class mapping is not FAKE=0, REAL=1")
    if config["feature_schema_version"] != EXPECTED_SCHEMA:
        raise ValueError("Task 38 feature schema is incompatible")
    if config["classifier"]["C_grid"] != list(C_GRID):
        raise ValueError("Task 38 regularization grid differs from expected training protocol")
    if selection.get("test_used_for_selection") is not False:
        raise ValueError("Task 38 test-set selection status is inconsistent")
    return metadata, config, selection


def _protected_inventory() -> Dict[str, Dict[str, Any]]:
    inventory: Dict[str, Dict[str, Any]] = {}
    for path in sorted(RESEARCH_ROOT.rglob("*")):
        if not path.is_file() or OUTPUT_ROOT in path.parents:
            continue
        relative = path.relative_to(RESEARCH_ROOT).as_posix()
        inventory[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    for relative, expected in KNOWN_PROTECTED_HASHES.items():
        actual = inventory.get(relative)
        if actual is None or actual["sha256"] != expected:
            raise ValueError(f"recorded protected artifact hash mismatch: {relative}")
    return inventory


def _metrics(y_true: np.ndarray, probabilities: np.ndarray) -> Dict[str, Any]:
    predictions = (probabilities >= 0.5).astype(np.int64)
    return {
        "threshold": 0.5,
        "threshold_source": "fixed Task 38 protocol threshold; not tuned on test",
        "positive_class": "REAL",
        "class_prevalence": {
            "FAKE": float(np.mean(y_true == 0)),
            "REAL": float(np.mean(y_true == 1)),
        },
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "precision_REAL": float(precision_score(y_true, predictions, pos_label=1, zero_division=0)),
        "recall_REAL": float(recall_score(y_true, predictions, pos_label=1, zero_division=0)),
        "f1_REAL": float(f1_score(y_true, predictions, pos_label=1, zero_division=0)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision_REAL": float(average_precision_score(y_true, probabilities)),
        "confusion_matrix_labels": ["FAKE", "REAL"],
        "confusion_matrix": confusion_matrix(y_true, predictions, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y_true,
            predictions,
            labels=[0, 1],
            target_names=["FAKE", "REAL"],
            output_dict=True,
            zero_division=0,
        ),
    }


def _model(c_value: float) -> LogisticRegression:
    return LogisticRegression(
        solver="lbfgs",
        penalty="l2",
        C=float(c_value),
        max_iter=2000,
        class_weight=None,
        random_state=42,
    )


def _write_predictions(path: Path, ids: List[str], labels: List[int], probabilities: np.ndarray) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    with path.open("x", encoding="utf-8") as output:
        for sample_id, label, probability in zip(ids, labels, probabilities):
            output.write(json.dumps({
                "sample_id": sample_id,
                "label": "REAL" if label else "FAKE",
                "probability_REAL": float(probability),
                "predicted_label": "REAL" if probability >= 0.5 else "FAKE",
                "threshold": 0.5,
            }, separators=(",", ":"), ensure_ascii=False) + "\n")


def train() -> Dict[str, Any]:
    if OUTPUT_ROOT.exists():
        raise FileExistsError(f"refusing to overwrite experiment directory: {OUTPUT_ROOT}")
    protected_before = _protected_inventory()
    metadata, task38_config, task38_selection = _validate_sources()
    data: Dict[str, Any] = {}
    split_counts: Dict[str, Any] = {}
    combined_ids = set()
    for split in SPLITS:
        text, image, labels, ids, counts = _load_records(split)
        duplicate_ids = combined_ids.intersection(ids)
        if duplicate_ids:
            raise ValueError(f"sample IDs overlap splits, e.g. {next(iter(duplicate_ids))}")
        combined_ids.update(ids)
        data[split] = {
            "text_only": text,
            "image_only": image,
            "y": np.asarray(labels, dtype=np.int64),
            "ids": ids,
        }
        split_counts[split] = counts

    OUTPUT_ROOT.mkdir(parents=True)
    started = time.perf_counter()
    config = {
        "experiment_id": OUTPUT_ROOT.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task36c_schema_version": EXPECTED_SCHEMA,
        "encoder": {
            "architecture": EXPECTED_MODEL,
            "pretrained_configuration": EXPECTED_CHECKPOINT,
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "embedding_dimensions": {"text": 512, "image": 512},
        },
        "target": {
            "name": task38_config["target"]["name"],
            "label_mapping": LABEL_TO_INT,
            "positive_class": "REAL",
            "factual_verification_claim": False,
        },
        "models": {
            modality: {
                "feature_set": list(FEATURES[modality]),
                "dimension": 512,
                "artifact": f"models/{modality}.joblib",
            }
            for modality in FEATURES
        },
        "classifier": task38_config["classifier"],
        "selection": {
            "fit_split": "train",
            "selection_split": "validation",
            "primary_metric": "ROC-AUC",
            "tie_breaker": "average precision for REAL, then smaller C",
            "candidate_C_values": list(C_GRID),
        },
        "probabilities": {
            "meaning": "scikit-learn LogisticRegression predict_proba scores for Fakeddit label classes",
            "calibrated": False,
            "threshold": 0.5,
            "threshold_tuned": False,
        },
        "split_counts": split_counts,
        "test_set_caveat": (
            "Task 38 previously evaluated this official test split for its fusion experiment. "
            "These modality-specific test metrics are additional comparisons on a previously "
            "examined split, not a pristine first-use evaluation."
        ),
        "limitations": [
            "Labels are Fakeddit distant-supervision FAKE/REAL labels, not verified factual truth.",
            "Model scores are uncalibrated and are not factual confidence.",
            "Task 36C selected a leakage-safe split, but task-level source and event shortcuts may remain.",
        ],
    }
    _write_json(OUTPUT_ROOT / "configuration.json", config)
    _write_json(OUTPUT_ROOT / "environment.json", {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scikit-learn", "joblib", "open_clip_torch", "torch")
        },
    })

    validation_results: Dict[str, Any] = {}
    selected_models: Dict[str, Any] = {}
    for modality in FEATURES:
        x_train = data["train"][modality]
        x_validation = data["validation"][modality]
        y_train = data["train"]["y"]
        y_validation = data["validation"]["y"]
        candidates = []
        fitted = {}
        for c_value in C_GRID:
            estimator = _model(c_value)
            estimator.fit(x_train, y_train)
            probabilities = estimator.predict_proba(x_validation)[:, 1]
            metrics = _metrics(y_validation, probabilities)
            candidates.append({"C": c_value, "metrics": metrics})
            fitted[c_value] = estimator
        candidates.sort(
            key=lambda row: (
                -row["metrics"]["roc_auc"],
                -row["metrics"]["average_precision_REAL"],
                row["C"],
            )
        )
        selected = candidates[0]
        estimator = fitted[selected["C"]]
        model_path = OUTPUT_ROOT / "models" / f"{modality}.joblib"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with model_path.open("xb") as model_file:
            joblib.dump(estimator, model_file)
        selected_models[modality] = estimator
        validation_results[modality] = {
            "candidate_metrics_by_C": candidates,
            "selected_C": selected["C"],
            "selected_metrics": selected["metrics"],
            "fit_examples": int(len(y_train)),
            "validation_examples": int(len(y_validation)),
            "training_feature_shape": list(x_train.shape),
        }
        validation_probabilities = estimator.predict_proba(x_validation)[:, 1]
        _write_predictions(
            OUTPUT_ROOT / f"{modality}_validation_predictions.jsonl",
            data["validation"]["ids"],
            data["validation"]["y"].tolist(),
            validation_probabilities,
        )

    test_results: Dict[str, Any] = {}
    for modality, estimator in selected_models.items():
        x_test = data["test"][modality]
        y_test = data["test"]["y"]
        probabilities = estimator.predict_proba(x_test)[:, 1]
        test_results[modality] = {
            "metrics": _metrics(y_test, probabilities),
            "test_examples": int(len(y_test)),
            "feature_shape": list(x_test.shape),
            "evaluation_status": "evaluated_once_after_validation_selection",
        }
        _write_predictions(
            OUTPUT_ROOT / f"{modality}_test_predictions.jsonl",
            data["test"]["ids"],
            y_test.tolist(),
            probabilities,
        )

    report = {
        "experiment_id": OUTPUT_ROOT.name,
        "training_completed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "method": "two independent L2 logistic regression models on frozen, normalized Task 36C embeddings",
        "validation": validation_results,
        "test": test_results,
        "task38_test_history": {
            "task38_experiment_id": task38_selection["experiment_id"],
            "previously_evaluated_on_same_test_split": True,
            "task38_model": task38_selection["selected_model"],
            "task38_test_used_for_model_selection": task38_selection["test_used_for_selection"],
            "interpretation": "Descriptive comparison only; not a first-use holdout.",
        },
    }
    _write_json(OUTPUT_ROOT / "metrics.json", report)

    protocol = """# Task 47 modality-specific classifier protocol

## Research target

Train separate text-only and image-only classifiers for Fakeddit's existing
two-way distant-supervision label. These models do not verify factual truth,
contradiction, or evidence support.

## Frozen inputs and splits

Use only the existing Task 36C `rr-decision-v2` features produced by
OpenCLIP `ViT-B-32-quickgelu` with the `openai` checkpoint. Both embeddings
are 512-dimensional and L2-normalized. Text and image features are evaluated
independently; no missing feature is filled or synthesized.

Fit on the official Task 36C train split, choose C from 0.01, 0.1, 1, and 10
using validation ROC-AUC (then average precision for REAL, then smaller C),
and evaluate the selected model once on the official test split. Use the
Task 38 L2 LogisticRegression, lbfgs solver, max_iter=2000, random_state=42,
and label mapping FAKE=0 / REAL=1. The decision threshold remains 0.5.

## Evaluation and limitations

Report prevalence, confusion matrix, precision, recall and F1 for both
classes, accuracy, balanced accuracy, ROC-AUC and average precision. No
probability calibration is applied. Task 38 has already evaluated the same
test split for its fusion model, so Task 47 test metrics are not a pristine
first-use evaluation. Dataset and event/source shortcuts may remain.
"""
    (OUTPUT_ROOT / "protocol.md").write_text(protocol, encoding="utf-8")

    protected_after = _protected_inventory()
    integrity = {
        "status": "PASS" if protected_before == protected_after else "FAIL",
        "protected_root": str(RESEARCH_ROOT.resolve()),
        "excluded_new_experiment_path": str(OUTPUT_ROOT.resolve()),
        "file_count_before": len(protected_before),
        "file_count_after": len(protected_after),
        "changed_paths": sorted(
            path
            for path in set(protected_before) | set(protected_after)
            if protected_before.get(path) != protected_after.get(path)
        ),
        "known_recorded_hashes": {
            path: {
                "expected_sha256": expected,
                "actual_sha256": protected_after[path]["sha256"],
                "match": protected_after[path]["sha256"] == expected,
            }
            for path, expected in KNOWN_PROTECTED_HASHES.items()
        },
    }
    _write_json(OUTPUT_ROOT / "protected_artifact_integrity.json", integrity)
    if integrity["status"] != "PASS":
        raise RuntimeError("protected research artifact integrity check failed")

    inventory_entries = []
    for path in sorted(OUTPUT_ROOT.rglob("*")):
        if path.is_file() and path.name != "sha256_inventory.json":
            inventory_entries.append({
                "path": path.relative_to(OUTPUT_ROOT).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            })
    _write_json(OUTPUT_ROOT / "sha256_inventory.json", {
        "experiment_id": OUTPUT_ROOT.name,
        "task36c_inputs": {
            split: {
                "path": str((FEATURE_ROOT / "full" / f"{split}.jsonl").resolve()),
                "sha256": sha256_file(FEATURE_ROOT / "full" / f"{split}.jsonl"),
                "size_bytes": (FEATURE_ROOT / "full" / f"{split}.jsonl").stat().st_size,
            }
            for split in SPLITS
        },
        "artifacts": inventory_entries,
    })
    return report


def main() -> None:
    report = train()
    print(json.dumps({
        "experiment_id": report["experiment_id"],
        "runtime_seconds": report["runtime_seconds"],
        "validation": {
            name: {
                "selected_C": result["selected_C"],
                "roc_auc": result["selected_metrics"]["roc_auc"],
            }
            for name, result in report["validation"].items()
        },
        "test": {
            name: result["metrics"]
            for name, result in report["test"].items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
