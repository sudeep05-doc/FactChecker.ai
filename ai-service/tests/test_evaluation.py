import json
from pathlib import Path

import pytest

from app.evaluation import (
    ABLATION_CONFIGURATIONS,
    BASELINE_CONFIGURATIONS,
    EvaluationConfiguration,
    EvaluationPrediction,
    EvaluationRunner,
    EvaluationSample,
    GroundTruthLabel,
    DatasetSplit,
    calibration_metrics,
    classification_metrics,
    confusion_matrix,
    get_configuration,
    load_jsonl,
    load_samples,
)


def sample(sample_id, label, *, text="claim", image=None, ocr_text=None, split=DatasetSplit.TEST):
    return EvaluationSample(
        sample_id=sample_id,
        label=label,
        text=text,
        image=image,
        ocr_text=ocr_text,
        split=split,
    )


def prediction(label=None, probability=None, **kwargs):
    return EvaluationPrediction(prediction=label, probability_fake=probability, **kwargs)


def binary_fixture():
    samples = [
        sample("1", GroundTruthLabel.REAL),
        sample("2", GroundTruthLabel.REAL),
        sample("3", GroundTruthLabel.FAKE),
        sample("4", GroundTruthLabel.FAKE),
    ]
    predictions = [
        prediction(GroundTruthLabel.REAL, 0.1),
        prediction(GroundTruthLabel.FAKE, 0.8),
        prediction(GroundTruthLabel.FAKE, 0.9),
        prediction(GroundTruthLabel.REAL, 0.2),
    ]
    return samples, predictions


def test_valid_binary_classification_metrics():
    metrics = classification_metrics(*binary_fixture())

    assert metrics.accuracy.value == 0.5
    assert metrics.precision.value == pytest.approx(0.5)
    assert metrics.recall.value == pytest.approx(0.5)
    assert metrics.f1.value == pytest.approx(0.5)
    assert metrics.specificity.value == pytest.approx(0.5)
    assert metrics.roc_auc.value is not None
    assert metrics.pr_auc.value is not None


def test_confusion_matrix_counts_real_and_fake_classes():
    matrix = confusion_matrix(*binary_fixture())

    assert matrix.true_real == 1
    assert matrix.false_fake == 1
    assert matrix.false_real == 1
    assert matrix.true_fake == 1
    assert matrix.evaluated_count == 4


def test_missing_prediction_is_not_counted_as_correct_or_zero_metric():
    samples = [sample("1", GroundTruthLabel.REAL), sample("2", GroundTruthLabel.FAKE)]
    metrics = classification_metrics(samples, [prediction(None), prediction(GroundTruthLabel.FAKE)])

    assert metrics.confusion_matrix.missing_prediction_count == 1
    assert metrics.accuracy.value == 1.0
    assert metrics.precision.value == 1.0
    assert metrics.recall.value == 1.0


def test_missing_probability_makes_auc_and_calibration_unavailable():
    samples, predictions = binary_fixture()
    predictions[0].probability_fake = None
    predictions[1].probability_fake = None
    predictions[2].probability_fake = None
    predictions[3].probability_fake = None

    metrics = classification_metrics(samples, predictions)
    calibration = calibration_metrics(samples, predictions)

    assert metrics.roc_auc.value is None
    assert metrics.roc_auc.reason == "PROBABILITY_SCORES_UNAVAILABLE_OR_SINGLE_CLASS"
    assert metrics.pr_auc.value is None
    assert calibration.brier_score.value is None
    assert calibration.expected_calibration_error.value is None


def test_absent_class_keeps_auc_and_specificity_explicitly_unavailable():
    samples = [sample("1", GroundTruthLabel.REAL), sample("2", GroundTruthLabel.REAL)]
    predictions = [prediction(GroundTruthLabel.REAL, 0.1), prediction(GroundTruthLabel.REAL, 0.2)]

    metrics = classification_metrics(samples, predictions)

    assert metrics.roc_auc.value is None
    assert metrics.specificity.value == 1.0
    assert metrics.recall.value is None
    assert "SINGLE_CLASS" in metrics.roc_auc.reason


def test_brier_score_and_ece_use_decision_probabilities_only():
    samples, predictions = binary_fixture()
    calibration = calibration_metrics(samples, predictions, bin_count=2)

    assert calibration.brier_score.value == pytest.approx((0.01 + 0.64 + 0.01 + 0.64) / 4)
    assert calibration.expected_calibration_error.value is not None
    assert calibration.reliability_bins


def test_dataset_loading_requires_explicit_matching_split(tmp_path: Path):
    records = [sample("1", GroundTruthLabel.REAL).model_dump(mode="json")]
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps(records[0]) + "\n", encoding="utf-8")

    assert load_jsonl(path, DatasetSplit.TEST)[0].sample_id == "1"
    with pytest.raises(ValueError, match="split"):
        load_samples([sample("1", GroundTruthLabel.REAL, split=DatasetSplit.TRAIN)], DatasetSplit.TEST)


def test_baselines_and_ablation_configurations_are_declared_and_switchable():
    assert {"text_only", "image_only", "text_image", "text_image_ocr", "all_available"} <= BASELINE_CONFIGURATIONS.keys()
    assert {"baseline_text", "baseline_image", "multimodal_no_alignment", "multimodal_alignment", "multimodal_alignment_consistency", "multimodal_full_reasoning"} <= ABLATION_CONFIGURATIONS.keys()
    assert "alignment" not in [component.value for component in get_configuration("multimodal_no_alignment").enabled_components]
    assert "alignment" in [component.value for component in get_configuration("multimodal_alignment").enabled_components]


def test_missing_modalities_are_recorded_without_negative_evidence():
    samples = [sample("1", GroundTruthLabel.REAL, image=None, ocr_text=None)]
    predictions = [prediction(GroundTruthLabel.REAL, 0.2, available_modalities=["text"], omitted_modalities=["image", "ocr"])]
    result = EvaluationRunner(lambda *_: predictions[0]).evaluate(samples, get_configuration("text_only"), dataset_identifier="mock", split=DatasetSplit.TEST)

    assert result.modality_statistics.provided_count == {"text": 1}
    assert result.modality_statistics.omitted_count == {"image": 1, "ocr": 1}
    assert "MISSING_MODALITY_EVIDENCE_PRESENT" not in result.warnings
    assert result.sample_counts == {"REAL": 1}


def test_contradiction_case_is_recorded_against_ground_truth():
    samples = [sample("1", GroundTruthLabel.REAL)]
    predictions = [prediction(GroundTruthLabel.REAL, 0.4, evidence={"contradiction": {"score": 0.8, "status": "available"}})]
    result = EvaluationRunner(lambda *_: predictions[0]).evaluate(samples, get_configuration("text_only"), dataset_identifier="mock")

    assert result.contradiction_statistics["available_count"] == 1
    assert result.contradiction_statistics["records"][0]["ground_truth"] == "REAL"


def test_error_categorization_covers_misclassification_missing_modality_and_failure():
    samples = [sample("1", GroundTruthLabel.REAL)]
    predictions = [prediction(GroundTruthLabel.FAKE, 0.9, omitted_modalities=["image"], errors=["PREPROCESSING_FAILURE"])]
    result = EvaluationRunner(lambda *_: predictions[0]).evaluate(samples, get_configuration("text_only"), dataset_identifier="mock")
    categories = {record.category for record in result.error_records}

    assert {"false_positive", "missing_modality", "preprocessing_failure"} <= categories


def test_mock_end_to_end_result_is_serializable_and_records_reproducibility():
    samples = [
        sample("1", GroundTruthLabel.REAL, image="image-1"),
        sample("2", GroundTruthLabel.FAKE, image="image-2", ocr_text="text"),
    ]

    def execute(item, configuration):
        return EvaluationPrediction(
            prediction=GroundTruthLabel.FAKE if item.label == GroundTruthLabel.FAKE else GroundTruthLabel.REAL,
            probability_fake=0.9 if item.label == GroundTruthLabel.FAKE else 0.1,
            available_modalities=[modality for modality in configuration.modalities if getattr(item, modality if modality != "ocr" else "ocr_text") is not None],
            explanation="mock explanation",
            evidence={"contradiction": None},
        )

    result = EvaluationRunner(execute).evaluate(
        samples,
        get_configuration("all_available"),
        dataset_identifier="mock-dataset",
        dataset_version="v1",
        split=DatasetSplit.TEST,
        random_seed=7,
        pipeline_version="pipeline-v1",
        model_versions={"encoder": "mock-v1"},
        cmref_configuration={"working_dimension": 2},
        decision_configuration={"calibration": "mock"},
        device_runtime="cpu",
    )
    payload = result.model_dump(mode="json")

    assert result.status.value == "completed"
    assert result.run.dataset_identifier == "mock-dataset"
    assert result.run.random_seed == 7
    assert result.classification_metrics.accuracy.value == 1.0
    assert len(result.explanation_records) == 2
    assert payload["run"]["split"] == "test"
    json.dumps(payload)


def test_train_validation_samples_cannot_be_evaluated_as_test():
    with pytest.raises(ValueError, match="split"):
        EvaluationRunner(lambda *_: prediction(GroundTruthLabel.REAL, 0.1)).evaluate(
            [sample("train", GroundTruthLabel.REAL, split=DatasetSplit.TRAIN)],
            get_configuration("text_only"),
            dataset_identifier="mock",
            split=DatasetSplit.TEST,
        )


def test_training_evaluation_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="allow_training"):
        EvaluationRunner(lambda *_: prediction(GroundTruthLabel.REAL, 0.1)).evaluate(
            [sample("train", GroundTruthLabel.REAL, split=DatasetSplit.TRAIN)],
            get_configuration("text_only"), dataset_identifier="mock", split=DatasetSplit.TRAIN,
        )
    result = EvaluationRunner(lambda *_: prediction(GroundTruthLabel.REAL, 0.1)).evaluate(
        [sample("train", GroundTruthLabel.REAL, split=DatasetSplit.TRAIN)],
        get_configuration("text_only"), dataset_identifier="mock", split=DatasetSplit.TRAIN, allow_training=True,
    )
    assert result.run.split == DatasetSplit.TRAIN


def test_ablation_runner_returns_independent_structured_results():
    samples = [sample("1", GroundTruthLabel.REAL), sample("2", GroundTruthLabel.FAKE)]
    results = EvaluationRunner(lambda item, _: prediction(item.label, 0.9 if item.label == GroundTruthLabel.FAKE else 0.1)).evaluate_ablation(
        samples, [get_configuration("baseline_text"), get_configuration("multimodal_alignment")], dataset_identifier="mock"
    )

    assert [result.configuration.name for result in results] == ["baseline_text", "multimodal_alignment"]
    assert all(result.ablation_results for result in results)


def test_error_analysis_records_high_confidence_and_contradiction():
    result = EvaluationRunner(lambda *_: prediction(
        GroundTruthLabel.FAKE, 0.95, evidence={"contradiction": {"score": 0.7}}
    )).evaluate([sample("1", GroundTruthLabel.REAL)], get_configuration("text_only"), dataset_identifier="mock")
    categories = {record.category for record in result.error_records}

    assert "incorrect_high_confidence_prediction" in categories
    assert "contradiction_case" in categories


def test_error_analysis_records_low_confidence_correct_prediction():
    result = EvaluationRunner(lambda *_: prediction(GroundTruthLabel.REAL, 0.45)).evaluate(
        [sample("1", GroundTruthLabel.REAL)], get_configuration("text_only"), dataset_identifier="mock"
    )

    assert any(record.category == "low_confidence_correct_prediction" for record in result.error_records)


def test_calibration_and_unsupported_prediction_errors_are_retained():
    result = EvaluationRunner(lambda *_: prediction(
        GroundTruthLabel.REAL, 0.1, errors=["CALIBRATION_UNAVAILABLE", "UNSUPPORTED_PREDICTION"]
    )).evaluate([sample("1", GroundTruthLabel.REAL)], get_configuration("text_only"), dataset_identifier="mock")
    categories = {record.category for record in result.error_records}

    assert "calibration_issue" in categories
    assert "unsupported_prediction" in categories


def test_unavailable_decision_is_structured_not_fabricated():
    result = EvaluationRunner(lambda *_: prediction(None, None, errors=["CALIBRATION_UNAVAILABLE"])).evaluate(
        [sample("1", GroundTruthLabel.FAKE)], get_configuration("text_only"), dataset_identifier="mock"
    )

    assert result.status.value == "partial"
    assert result.classification_metrics.accuracy.value is None
    assert result.calibration_metrics.brier_score.value is None
    assert any(record.category == "unavailable_decision" for record in result.error_records)
    assert "CALIBRATION_UNAVAILABLE" in result.error_records[0].details["errors"]


def test_no_available_modality_is_reported_as_missing_evidence():
    result = EvaluationRunner(lambda *_: prediction(None, None)).evaluate(
        [sample("1", GroundTruthLabel.REAL, text=None)],
        get_configuration("text_only"),
        dataset_identifier="mock",
    )

    assert result.modality_statistics.missing_sample_count == 1
    assert "MISSING_MODALITY_EVIDENCE_PRESENT" in result.warnings
    assert result.confidence_intervals == {}
    assert result.statistical_tests == []
