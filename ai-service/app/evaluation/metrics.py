"""Dataset-independent classification metrics with explicit unavailable states."""

from typing import Iterable, List, Optional, Sequence, Tuple

from app.evaluation.schemas import (
    CalibrationMetrics, ClassificationMetrics, ConfusionMatrix, EvaluationPrediction,
    EvaluationSample, EvaluationStatus, MetricValue, ReliabilityBin, GroundTruthLabel,
)


def _metric(value: Optional[float], reason: Optional[str] = None) -> MetricValue:
    if value is None:
        return MetricValue(value=None, status=EvaluationStatus.UNAVAILABLE, reason=reason)
    return MetricValue(value=value)


def _pairs(samples: Sequence[EvaluationSample], predictions: Sequence[EvaluationPrediction]):
    return [(sample, prediction) for sample, prediction in zip(samples, predictions) if prediction.prediction is not None]


def confusion_matrix(samples: Sequence[EvaluationSample], predictions: Sequence[EvaluationPrediction]) -> ConfusionMatrix:
    matrix = ConfusionMatrix()
    matrix.missing_prediction_count = sum(prediction.prediction is None for prediction in predictions)
    for sample, prediction in _pairs(samples, predictions):
        matrix.evaluated_count += 1
        if sample.label == GroundTruthLabel.REAL and prediction.prediction == GroundTruthLabel.REAL:
            matrix.true_real += 1
        elif sample.label == GroundTruthLabel.REAL:
            matrix.false_fake += 1
        elif prediction.prediction == GroundTruthLabel.REAL:
            matrix.false_real += 1
        else:
            matrix.true_fake += 1
    return matrix


def classification_metrics(samples: Sequence[EvaluationSample], predictions: Sequence[EvaluationPrediction]) -> ClassificationMetrics:
    if len(samples) != len(predictions):
        raise ValueError("samples and predictions must have the same length")
    matrix = confusion_matrix(samples, predictions)
    n = matrix.evaluated_count
    accuracy = (matrix.true_real + matrix.true_fake) / n if n else None
    precision_denominator = matrix.true_fake + matrix.false_real
    recall_denominator = matrix.true_fake + matrix.false_fake
    specificity_denominator = matrix.true_real + matrix.false_real
    precision = matrix.true_fake / precision_denominator if precision_denominator else None
    recall = matrix.true_fake / recall_denominator if recall_denominator else None
    specificity = matrix.true_real / specificity_denominator if specificity_denominator else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None
    scores = [(sample.label, prediction.probability_fake) for sample, prediction in zip(samples, predictions) if prediction.probability_fake is not None]
    roc_auc = _roc_auc(scores) if scores else None
    pr_auc = _pr_auc(scores) if scores else None
    reason = "NO_EVALUATED_PREDICTIONS" if n == 0 else "REQUIRED_CLASS_ABSENT_OR_NO_POSITIVE_PREDICTIONS"
    return ClassificationMetrics(
        accuracy=_metric(accuracy, reason if accuracy is None else None),
        precision=_metric(precision, reason if precision is None else None),
        recall=_metric(recall, reason if recall is None else None),
        f1=_metric(f1, reason if f1 is None else None),
        specificity=_metric(specificity, reason if specificity is None else None),
        roc_auc=_metric(roc_auc, "PROBABILITY_SCORES_UNAVAILABLE_OR_SINGLE_CLASS" if roc_auc is None else None),
        pr_auc=_metric(pr_auc, "PROBABILITY_SCORES_UNAVAILABLE_OR_SINGLE_CLASS" if pr_auc is None else None),
        confusion_matrix=matrix,
    )


def _roc_auc(scores: Sequence[Tuple[GroundTruthLabel, float]]) -> Optional[float]:
    labels = [label == GroundTruthLabel.FAKE for label, _ in scores]
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(scores, key=lambda item: item[1])
    rank_sum = sum(index for index, (label, _) in enumerate(ordered, start=1) if label == GroundTruthLabel.FAKE)
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _pr_auc(scores: Sequence[Tuple[GroundTruthLabel, float]]) -> Optional[float]:
    positives = sum(label == GroundTruthLabel.FAKE for label, _ in scores)
    if not positives or positives == len(scores):
        return None
    ordered = sorted(scores, key=lambda item: item[1], reverse=True)
    found = 0
    previous_recall = 0.0
    area = 0.0
    for index, (label, _) in enumerate(ordered, start=1):
        if label == GroundTruthLabel.FAKE:
            found += 1
            recall = found / positives
            precision = found / index
            area += (recall - previous_recall) * precision
            previous_recall = recall
    return area


def calibration_metrics(samples: Sequence[EvaluationSample], predictions: Sequence[EvaluationPrediction], bin_count: int = 10) -> CalibrationMetrics:
    if len(samples) != len(predictions):
        raise ValueError("samples and predictions must have the same length")
    pairs = [(sample.label == GroundTruthLabel.FAKE, prediction.probability_fake) for sample, prediction in zip(samples, predictions) if prediction.probability_fake is not None]
    if not pairs:
        unavailable = _metric(None, "PROBABILITY_SCORES_UNAVAILABLE")
        return CalibrationMetrics(brier_score=unavailable, expected_calibration_error=unavailable)
    brier = sum((probability - int(label)) ** 2 for label, probability in pairs) / len(pairs)
    bins: List[ReliabilityBin] = []
    weighted_gap = 0.0
    for bin_index in range(bin_count):
        lower = bin_index / bin_count
        upper = (bin_index + 1) / bin_count
        members = [(label, probability) for label, probability in pairs if lower <= probability < upper or (bin_index == bin_count - 1 and probability == upper)]
        if not members:
            continue
        mean_probability = sum(probability for _, probability in members) / len(members)
        frequency = sum(label for label, _ in members) / len(members)
        gap = abs(mean_probability - frequency)
        weighted_gap += len(members) / len(pairs) * gap
        bins.append(ReliabilityBin(lower=lower, upper=upper, count=len(members), mean_probability=mean_probability, empirical_frequency=frequency, absolute_gap=gap))
    return CalibrationMetrics(brier_score=_metric(brier), expected_calibration_error=_metric(weighted_gap), reliability_bins=bins)
