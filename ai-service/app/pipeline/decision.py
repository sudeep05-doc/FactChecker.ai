"""Independent decision/calibration boundary."""

from typing import Any, Callable, Optional

from app.pipeline.schemas import DecisionCalibrationResult
from app.rr.models import ReasoningRepresentation


class DecisionCalibration:
    """Interface for a future trained/calibrated decision component."""

    def decide(self, reasoning: ReasoningRepresentation) -> DecisionCalibrationResult:
        return DecisionCalibrationResult()


class DecisionCalibrationAdapter(DecisionCalibration):
    """Expose the trainable decision service through the pipeline contract."""

    def __init__(self, service: Any) -> None:
        self.service = service

    def decide(self, reasoning: ReasoningRepresentation) -> DecisionCalibrationResult:
        result = self.service.decide(reasoning)
        return DecisionCalibrationResult(
            prediction=result.prediction,
            raw_probability=result.raw_probability,
            calibrated_probability=result.calibrated_probability,
            confidence=result.confidence,
            status=result.status,
            reason=result.reason or "CALIBRATION_UNAVAILABLE",
            feature_schema_version=result.feature_schema_version,
            provenance=result.provenance,
            metadata={
                "lifecycle": result.lifecycle.value,
                "classifier": result.classifier_metadata,
                "calibration": result.calibration_metadata,
            },
        )


class CallableDecisionCalibration(DecisionCalibration):
    """Adapter for an injected calibrated decision callable used by tests/future models."""

    def __init__(self, function: Callable[[ReasoningRepresentation], Any]) -> None:
        self.function = function

    def decide(self, reasoning: ReasoningRepresentation) -> DecisionCalibrationResult:
        result = self.function(reasoning)
        if isinstance(result, DecisionCalibrationResult):
            return result
        if not isinstance(result, dict):
            raise ValueError("decision calibrator must return a dictionary or DecisionCalibrationResult")
        return DecisionCalibrationResult(**result)