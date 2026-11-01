"""Dataset -> RR features -> train -> validation calibration -> held-out test."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

from app.decision import DecisionCalibrationService
from app.decision.features import FEATURE_SCHEMA_VERSION
from app.evaluation.configurations import BASELINE_CONFIGURATIONS
from app.evaluation.datasets import split_samples
from app.evaluation.metrics import calibration_metrics, classification_metrics
from app.evaluation.schemas import (
    DatasetSplit, EvaluationConfiguration, EvaluationPrediction, EvaluationSample,
    GroundTruthLabel,
)
from app.rr.models import ReasoningRepresentation


class FeatureCache:
    """Optional JSON cache keyed by sample and configuration provenance."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path else None
        self.values: Dict[str, Dict[str, Any]] = {}
        if self.path and self.path.is_file():
            self.values = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, sample_id: str, configuration_hash: str) -> Optional[dict]:
        value = self.values.get(sample_id)
        return value if value and value.get("configuration_hash") == configuration_hash else None

    def put(self, sample_id: str, configuration_hash: str, payload: dict) -> None:
        self.values[sample_id] = {"configuration_hash": configuration_hash, **payload}

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.values, indent=2, sort_keys=True), encoding="utf-8")


class ResearchRunResult:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self, mode: str = "python") -> dict:
        return self.payload

    def write_json(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.payload, indent=2, sort_keys=True), encoding="utf-8")


class ResearchEvaluationPipeline:
    """Run a supplied RR provider without bypassing the CMREF/RR architecture."""

    def __init__(self, rr_provider: Callable[[EvaluationSample, EvaluationConfiguration], ReasoningRepresentation], decision: Optional[DecisionCalibrationService] = None, cache: Optional[FeatureCache] = None) -> None:
        self.rr_provider = rr_provider
        self.decision = decision or DecisionCalibrationService()
        self.cache = cache or FeatureCache()

    def run(
        self,
        samples: Iterable[EvaluationSample],
        *,
        dataset_identifier: str,
        dataset_version: str,
        configuration: EvaluationConfiguration,
        seed: int = 42,
        splits: Optional[Dict[DatasetSplit, List[EvaluationSample]]] = None,
        model_metadata: Optional[dict] = None,
        cmref_configuration: Optional[dict] = None,
    ) -> ResearchRunResult:
        records = list(samples)
        split_map = splits or split_samples(records, seed=seed)
        self._validate_splits(split_map)
        configuration_hash = _configuration_hash(configuration, model_metadata or {}, cmref_configuration or {})
        vectors = {split: self._features(records_for_split, configuration, configuration_hash) for split, records_for_split in split_map.items()}
        labels = {split: [record.label.value for record in records_for_split] for split, records_for_split in split_map.items()}
        self.decision.fit(vectors[DatasetSplit.TRAIN], labels[DatasetSplit.TRAIN])
        self.decision.calibrate(vectors[DatasetSplit.VALIDATION], labels[DatasetSplit.VALIDATION])
        predictions = self._predictions(split_map[DatasetSplit.TEST], vectors[DatasetSplit.TEST], configuration)
        classification = classification_metrics(split_map[DatasetSplit.TEST], predictions)
        calibration = calibration_metrics(split_map[DatasetSplit.TEST], predictions)
        payload = {
            "evaluation_run_id": str(uuid4()),
            "dataset": {"identifier": dataset_identifier, "version": dataset_version, "sample_count": len(records)},
            "split": {"seed": seed, "train_size": len(split_map[DatasetSplit.TRAIN]), "validation_size": len(split_map[DatasetSplit.VALIDATION]), "test_size": len(split_map[DatasetSplit.TEST]), "class_distribution": {split.value: _distribution(split_map[split]) for split in split_map}},
            "models": model_metadata or {},
            "feature_schema": {"version": FEATURE_SCHEMA_VERSION, "names": vectors[DatasetSplit.TEST][0].names},
            "classifier": self.decision.classifier.metadata(FEATURE_SCHEMA_VERSION),
            "calibration": self.decision.calibrator.metadata,
            "modality_configuration": configuration.model_dump(mode="json"),
            "metrics": {"classification": classification.model_dump(mode="json"), "calibration": calibration.model_dump(mode="json")},
            "reproducibility": {"cmref_configuration": cmref_configuration or {}, "timestamp": datetime.now(timezone.utc).isoformat(), "configuration_hash": configuration_hash},
            "test_sample_ids": [record.sample_id for record in split_map[DatasetSplit.TEST]],
            "warnings": ["SYNTHETIC_OR_SUPPLIED_DATASET_RESULTS_REQUIRE_RESEARCHER_REVIEW"],
        }
        return ResearchRunResult(payload)

    def _features(self, records, configuration, configuration_hash):
        values = []
        for record in records:
            cached = self.cache.get(record.sample_id, configuration_hash)
            if cached:
                values.append(self.decision.extract(ReasoningRepresentation.model_validate(cached["rr"])))
                continue
            rr = self.rr_provider(record, configuration)
            vector = self.decision.extract(rr)
            self.cache.put(record.sample_id, configuration_hash, {"rr": rr.model_dump(mode="json"), "feature_vector": vector.model_dump(mode="json")})
            values.append(vector)
        return values

    def _predictions(self, records, vectors, configuration):
        probabilities = self.decision.predict_proba(vectors, calibrated=True)
        labels = self.decision.predict(vectors)
        return [EvaluationPrediction(prediction=GroundTruthLabel(label), probability_fake=probability, available_modalities=_modalities(record), processing_metadata={"configuration": configuration.name}) for record, label, probability in zip(records, labels, probabilities)]

    @staticmethod
    def _validate_splits(splits):
        expected = set(DatasetSplit)
        if set(splits) != expected or any(not splits[split] for split in expected):
            raise ValueError("train, validation, and test splits must all be non-empty")
        ids = [record.sample_id for records in splits.values() for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("train, validation, and test splits must not overlap")


def _configuration_hash(configuration, model_metadata, cmref_configuration):
    payload = json.dumps({"configuration": configuration.model_dump(mode="json"), "models": model_metadata, "cmref": cmref_configuration}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _distribution(records):
    return {label: sum(record.label.value == label for record in records) for label in ("REAL", "FAKE")}


def _modalities(record):
    fields = {"text": "text", "image": "image", "ocr": "ocr_text", "audio": "audio", "video": "video"}
    return [name for name, field in fields.items() if getattr(record, field) is not None]