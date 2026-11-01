"""Lightweight evaluation execution, robustness, contradiction, and error analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

from app.evaluation.metrics import calibration_metrics, classification_metrics
from app.evaluation.schemas import (
    ContradictionRecord, DatasetSplit, ErrorRecord, EvaluationConfiguration,
    EvaluationPrediction, EvaluationResult, EvaluationSample, EvaluationStatus,
    ExplanationEvaluationRecord, ModalityStatistics, RunMetadata,
)


PredictionExecutor = Callable[[EvaluationSample, EvaluationConfiguration], EvaluationPrediction]


@dataclass
class EvaluationRunner:
    executor: PredictionExecutor

    def evaluate(self, samples: Iterable[EvaluationSample], configuration: EvaluationConfiguration, *, dataset_identifier: str, dataset_version: str | None = None, split: DatasetSplit = DatasetSplit.TEST, random_seed: int | None = None, pipeline_version: str | None = None, model_versions: Dict[str, str] | None = None, model_configuration: Dict | None = None, preprocessing_configuration: Dict | None = None, cmref_configuration: Dict | None = None, decision_configuration: Dict | None = None, device_runtime: str | None = None, allow_training: bool = False) -> EvaluationResult:
        selected = list(samples)
        if not selected:
            raise ValueError("evaluation dataset split is empty")
        if split == DatasetSplit.TRAIN and not allow_training:
            raise ValueError("training split evaluation requires allow_training=True")
        if any(sample.split != split for sample in selected):
            raise ValueError("evaluation split must be explicit and match every sample")
        predictions = [self.executor(sample, configuration) for sample in selected]
        run = RunMetadata(dataset_identifier=dataset_identifier, dataset_version=dataset_version, split=split, sample_count=len(selected), random_seed=random_seed, pipeline_version=pipeline_version, model_versions=model_versions or {}, model_configuration=model_configuration or {}, preprocessing_configuration=preprocessing_configuration or {}, cmref_configuration=cmref_configuration or {}, decision_configuration=decision_configuration or {}, device_runtime=device_runtime)
        result = EvaluationResult(run=run, configuration=configuration, status=EvaluationStatus.COMPLETED)
        result.sample_counts = dict(Counter(sample.label.value for sample in selected))
        result.classification_metrics = classification_metrics(selected, predictions)
        result.calibration_metrics = calibration_metrics(selected, predictions)
        result.modality_statistics = self._modality_statistics(selected, predictions)
        result.contradiction_statistics, contradiction_records = self._contradictions(selected, predictions)
        result.error_records = self._errors(selected, predictions)
        result.explanation_records = [self._explanation(sample, prediction) for sample, prediction in zip(selected, predictions)]
        result.warnings.extend(self._warnings(result, predictions))
        result.unavailable_metrics = [name for name, metric in result.classification_metrics.model_dump().items() if isinstance(metric, dict) and metric.get("status") == EvaluationStatus.UNAVAILABLE.value]
        result.status = EvaluationStatus.PARTIAL if result.unavailable_metrics or any(prediction.prediction is None for prediction in predictions) else EvaluationStatus.COMPLETED
        result.contradiction_statistics["records"] = [record.model_dump(mode="json") for record in contradiction_records]
        return result

    def evaluate_ablation(self, samples: Iterable[EvaluationSample], configurations: Iterable[EvaluationConfiguration], **kwargs) -> List[EvaluationResult]:
        """Run declared configurations independently for later table/plot use."""
        selected = list(samples)
        results = []
        for configuration in configurations:
            result = self.evaluate(selected, configuration, **kwargs)
            result.ablation_results = [{
                "configuration": configuration.name,
                "enabled_components": [component.value for component in configuration.enabled_components],
                "classification_metrics": result.classification_metrics.model_dump(mode="json"),
                "calibration_metrics": result.calibration_metrics.model_dump(mode="json"),
            }]
            results.append(result)
        return results

    @staticmethod
    def _modality_statistics(samples, predictions):
        provided = Counter()
        used = Counter()
        omitted = Counter()
        missing = 0
        for sample, prediction in zip(samples, predictions):
            sample_fields = {"text": "text", "image": "image", "ocr": "ocr_text", "audio": "audio", "video": "video"}
            sample_modalities = [name for name, field in sample_fields.items() if getattr(sample, field) is not None]
            for modality in sample_modalities:
                provided[modality] += 1
            for modality in prediction.available_modalities:
                used[modality] += 1
            for modality in prediction.omitted_modalities:
                omitted[modality] += 1
            missing += not prediction.available_modalities
        return ModalityStatistics(provided_count=dict(provided), used_count=dict(used), omitted_count=dict(omitted), missing_sample_count=missing)

    @staticmethod
    def _contradictions(samples, predictions):
        records = []
        for sample, prediction in zip(samples, predictions):
            contradiction = prediction.evidence.get("contradiction")
            status = "available" if contradiction is not None else "unavailable"
            records.append(ContradictionRecord(sample_id=sample.sample_id, ground_truth=sample.label, modality_pair=None, evaluator_status=status, evidence=contradiction if isinstance(contradiction, dict) else ({"value": contradiction} if contradiction is not None else None), prediction=prediction.prediction, probability_fake=prediction.probability_fake))
        available = sum(record.evaluator_status == "available" for record in records)
        return {"total_samples": len(records), "available_count": available, "unavailable_count": len(records) - available}, records

    @staticmethod
    def _errors(samples, predictions):
        records = []
        for sample, prediction in zip(samples, predictions):
            if prediction.prediction is None:
                records.append(ErrorRecord(sample_id=sample.sample_id, category="unavailable_decision", ground_truth=sample.label, available_modalities=prediction.available_modalities, omitted_modalities=prediction.omitted_modalities, details={"errors": prediction.errors}))
                continue
            if prediction.prediction != sample.label:
                category = "false_positive" if prediction.prediction.value == "FAKE" else "false_negative"
                records.append(ErrorRecord(sample_id=sample.sample_id, category=category, ground_truth=sample.label, prediction=prediction.prediction, probability_fake=prediction.probability_fake, available_modalities=prediction.available_modalities, omitted_modalities=prediction.omitted_modalities))
                if prediction.probability_fake is not None and max(prediction.probability_fake, 1 - prediction.probability_fake) >= 0.8:
                    records.append(ErrorRecord(sample_id=sample.sample_id, category="incorrect_high_confidence_prediction", ground_truth=sample.label, prediction=prediction.prediction, probability_fake=prediction.probability_fake))
            elif prediction.probability_fake is not None and min(prediction.probability_fake, 1 - prediction.probability_fake) < 0.6:
                records.append(ErrorRecord(sample_id=sample.sample_id, category="low_confidence_correct_prediction", ground_truth=sample.label, prediction=prediction.prediction, probability_fake=prediction.probability_fake))
            if prediction.evidence.get("contradiction") is not None:
                records.append(ErrorRecord(sample_id=sample.sample_id, category="contradiction_case", ground_truth=sample.label, prediction=prediction.prediction, probability_fake=prediction.probability_fake, details={"contradiction": prediction.evidence["contradiction"]}))
            if prediction.omitted_modalities:
                records.append(ErrorRecord(sample_id=sample.sample_id, category="missing_modality", ground_truth=sample.label, prediction=prediction.prediction, omitted_modalities=prediction.omitted_modalities))
            if prediction.errors:
                error_categories = []
                if any("PREPROCESS" in error for error in prediction.errors):
                    error_categories.append("preprocessing_failure")
                if any("CALIBRATION" in error for error in prediction.errors):
                    error_categories.append("calibration_issue")
                if any("UNSUPPORTED" in error for error in prediction.errors):
                    error_categories.append("unsupported_prediction")
                for category in error_categories:
                    records.append(ErrorRecord(sample_id=sample.sample_id, category=category, ground_truth=sample.label, prediction=prediction.prediction, details={"errors": prediction.errors}))
        return records

    @staticmethod
    def _explanation(sample, prediction):
        return ExplanationEvaluationRecord(sample_id=sample.sample_id, generated=prediction.explanation is not None, evidence_used=prediction.evidence, modalities_referenced=prediction.available_modalities, reasoning_path=prediction.reasoning_path, uncertainty_communicated=prediction.uncertainty)

    @staticmethod
    def _warnings(result, predictions):
        warnings = []
        if any(prediction.probability_fake is None for prediction in predictions):
            warnings.append("PROBABILITY_SCORES_UNAVAILABLE_FOR_SOME_SAMPLES")
        if result.modality_statistics.missing_sample_count:
            warnings.append("MISSING_MODALITY_EVIDENCE_PRESENT")
        return warnings
