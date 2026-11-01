"""Dataset, prediction, configuration, and result contracts for evaluation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GroundTruthLabel(str, Enum):
    REAL = "REAL"
    FAKE = "FAKE"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class EvaluationStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class AblationComponent(str, Enum):
    ALIGNMENT = "alignment"
    CONSISTENCY = "consistency"
    CONTRADICTION = "contradiction"
    CONTEXTUAL = "contextual"
    REASONING_SCORE = "reasoning_score"
    DECISION_CALIBRATION = "decision_calibration"


class EvaluationSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1)
    label: GroundTruthLabel
    text: Optional[str] = None
    image: Optional[Any] = None
    ocr_text: Optional[str] = None
    audio: Optional[Any] = None
    video: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_reference: Optional[str] = None
    split: Optional[DatasetSplit] = None


class EvaluationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    modalities: List[str] = Field(min_length=1)
    enabled_components: List[AblationComponent] = Field(default_factory=list)
    description: Optional[str] = None

    @model_validator(mode="after")
    def unique_modalities(self) -> "EvaluationConfiguration":
        if len(set(self.modalities)) != len(self.modalities):
            raise ValueError("modalities must not contain duplicates")
        return self


class EvaluationPrediction(BaseModel):
    """Prediction supplied by the decision/calibration boundary."""

    model_config = ConfigDict(extra="forbid")

    prediction: Optional[GroundTruthLabel] = None
    probability_fake: Optional[float] = Field(default=None, ge=0, le=1)
    available_modalities: List[str] = Field(default_factory=list)
    omitted_modalities: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    reasoning_path: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: Optional[str] = None
    uncertainty: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    model_versions: Dict[str, str] = Field(default_factory=dict)
    processing_metadata: Dict[str, Any] = Field(default_factory=dict)


class RunMetadata(BaseModel):
    evaluation_run_id: UUID = Field(default_factory=uuid4)
    dataset_identifier: str
    dataset_version: Optional[str] = None
    split: DatasetSplit
    sample_count: int = Field(ge=0)
    random_seed: Optional[int] = None
    pipeline_version: Optional[str] = None
    model_versions: Dict[str, str] = Field(default_factory=dict)
    model_configuration: Dict[str, Any] = Field(default_factory=dict)
    preprocessing_configuration: Dict[str, Any] = Field(default_factory=dict)
    cmref_configuration: Dict[str, Any] = Field(default_factory=dict)
    decision_configuration: Dict[str, Any] = Field(default_factory=dict)
    device_runtime: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricValue(BaseModel):
    value: Optional[float] = None
    status: EvaluationStatus = EvaluationStatus.COMPLETED
    reason: Optional[str] = None


class ConfusionMatrix(BaseModel):
    labels: List[str] = [GroundTruthLabel.REAL.value, GroundTruthLabel.FAKE.value]
    true_real: int = 0
    false_fake: int = 0
    false_real: int = 0
    true_fake: int = 0
    evaluated_count: int = 0
    missing_prediction_count: int = 0


class ClassificationMetrics(BaseModel):
    accuracy: MetricValue = Field(default_factory=MetricValue)
    precision: MetricValue = Field(default_factory=MetricValue)
    recall: MetricValue = Field(default_factory=MetricValue)
    f1: MetricValue = Field(default_factory=MetricValue)
    specificity: MetricValue = Field(default_factory=MetricValue)
    roc_auc: MetricValue = Field(default_factory=MetricValue)
    pr_auc: MetricValue = Field(default_factory=MetricValue)
    confusion_matrix: ConfusionMatrix = Field(default_factory=ConfusionMatrix)


class ReliabilityBin(BaseModel):
    lower: float
    upper: float
    count: int
    mean_probability: Optional[float] = None
    empirical_frequency: Optional[float] = None
    absolute_gap: Optional[float] = None


class CalibrationMetrics(BaseModel):
    brier_score: MetricValue = Field(default_factory=MetricValue)
    expected_calibration_error: MetricValue = Field(default_factory=MetricValue)
    reliability_bins: List[ReliabilityBin] = Field(default_factory=list)


class ModalityStatistics(BaseModel):
    provided_count: Dict[str, int] = Field(default_factory=dict)
    used_count: Dict[str, int] = Field(default_factory=dict)
    omitted_count: Dict[str, int] = Field(default_factory=dict)
    missing_sample_count: int = 0


class ContradictionRecord(BaseModel):
    sample_id: str
    ground_truth: GroundTruthLabel
    modality_pair: Optional[str] = None
    evaluator_status: str
    evidence: Optional[Dict[str, Any]] = None
    prediction: Optional[GroundTruthLabel] = None
    probability_fake: Optional[float] = None


class ExplanationEvaluationRecord(BaseModel):
    sample_id: str
    generated: bool
    evidence_used: Dict[str, Any] = Field(default_factory=dict)
    modalities_referenced: List[str] = Field(default_factory=list)
    reasoning_path: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty_communicated: List[str] = Field(default_factory=list)
    unsupported_claims_detected: Optional[bool] = None
    human_evaluation: Optional[Dict[str, Any]] = None


class ErrorRecord(BaseModel):
    sample_id: str
    category: str
    ground_truth: GroundTruthLabel
    prediction: Optional[GroundTruthLabel] = None
    probability_fake: Optional[float] = None
    available_modalities: List[str] = Field(default_factory=list)
    omitted_modalities: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    run: RunMetadata
    configuration: EvaluationConfiguration
    status: EvaluationStatus
    sample_counts: Dict[str, int] = Field(default_factory=dict)
    modality_statistics: ModalityStatistics = Field(default_factory=ModalityStatistics)
    classification_metrics: ClassificationMetrics = Field(default_factory=ClassificationMetrics)
    calibration_metrics: CalibrationMetrics = Field(default_factory=CalibrationMetrics)
    ablation_results: List[Dict[str, Any]] = Field(default_factory=list)
    robustness_results: List[Dict[str, Any]] = Field(default_factory=list)
    contradiction_statistics: Dict[str, Any] = Field(default_factory=dict)
    explanation_records: List[ExplanationEvaluationRecord] = Field(default_factory=list)
    error_records: List[ErrorRecord] = Field(default_factory=list)
    confidence_intervals: Dict[str, Any] = Field(default_factory=dict)
    statistical_tests: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    unavailable_metrics: List[str] = Field(default_factory=list)
