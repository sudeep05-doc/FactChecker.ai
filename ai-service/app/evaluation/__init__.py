"""Research-oriented, dataset-agnostic evaluation framework."""

from app.evaluation.configurations import ABLATION_CONFIGURATIONS, BASELINE_CONFIGURATIONS, get_configuration
from app.evaluation.datasets import load_jsonl, load_samples
from app.evaluation.metrics import calibration_metrics, classification_metrics, confusion_matrix
from app.evaluation.datasets import split_samples
from app.evaluation.research import FeatureCache, ResearchEvaluationPipeline, ResearchRunResult
from app.evaluation.fakeddit import FakedditAdapter, FakedditFieldMap, FakedditPreparationError, FakedditPreparationResult
from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import *

__all__ = [
    "ABLATION_CONFIGURATIONS", "BASELINE_CONFIGURATIONS", "EvaluationRunner",
    "calibration_metrics", "classification_metrics", "confusion_matrix",
    "get_configuration", "load_jsonl", "load_samples", "split_samples",
    "FeatureCache", "ResearchEvaluationPipeline", "ResearchRunResult",
    "FakedditAdapter", "FakedditFieldMap", "FakedditPreparationError", "FakedditPreparationResult",
]
