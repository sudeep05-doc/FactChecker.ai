"""Trainable decision and calibration service over RR-derived features."""

from math import isfinite
from typing import Iterable, List, Optional

from app.decision.calibration import SigmoidCalibrator
from app.decision.classifier import DecisionClassifier
from app.decision.features import FEATURE_SCHEMA_VERSION, extract_features
from app.decision.schemas import DecisionLifecycle, DecisionResult, FeatureVector
from app.rr.models import ReasoningRepresentation


class DecisionCalibrationService:
    def __init__(self, classifier: Optional[DecisionClassifier] = None) -> None:
        self.classifier = classifier or DecisionClassifier()
        self.calibrator: Optional[SigmoidCalibrator] = None
        self.lifecycle = DecisionLifecycle.UNFITTED

    def extract(self, rr: ReasoningRepresentation) -> FeatureVector:
        return extract_features(rr)

    def fit(self, feature_vectors: Iterable[FeatureVector], labels: Iterable[str]) -> "DecisionCalibrationService":
        vectors = list(feature_vectors)
        self._validate_vectors(vectors)
        self.classifier.fit([vector.values for vector in vectors], labels)
        self.lifecycle = DecisionLifecycle.TRAINED
        self.calibrator = None
        return self

    def calibrate(self, feature_vectors: Iterable[FeatureVector], labels: Iterable[str]) -> "DecisionCalibrationService":
        if not self.classifier.is_fitted:
            raise RuntimeError("classifier must be fitted before calibration")
        vectors = list(feature_vectors)
        self._validate_vectors(vectors)
        raw = self.classifier.predict_proba([vector.values for vector in vectors])
        self.calibrator = SigmoidCalibrator().fit(raw, labels)
        self.lifecycle = DecisionLifecycle.READY
        return self

    def decide(self, rr: ReasoningRepresentation) -> DecisionResult:
        vector = self.extract(rr)
        if not self.classifier.is_fitted:
            return DecisionResult(feature_schema_version=FEATURE_SCHEMA_VERSION, lifecycle=DecisionLifecycle.UNFITTED, status="UNAVAILABLE", reason="DECISION_UNFITTED", provenance={"features": vector.model_dump()})
        raw = _single_probability(
            self.classifier.predict_proba([vector.values]),
            "uncalibrated FAKE probability",
        )
        prediction = "FAKE" if raw >= 0.5 else "REAL"
        if self.calibrator is None:
            return DecisionResult(prediction=prediction, raw_probability=raw, lifecycle=DecisionLifecycle.TRAINED, status="CALIBRATION_UNAVAILABLE", reason="CALIBRATION_UNAVAILABLE", classifier_metadata=self.classifier.metadata(FEATURE_SCHEMA_VERSION), feature_schema_version=FEATURE_SCHEMA_VERSION, provenance={"features": vector.model_dump()})
        calibrated_fake = _validated_probability(
            self.calibrator.predict_fake_probability(raw),
            "calibrated FAKE probability",
        )
        prediction = "FAKE" if calibrated_fake >= 0.5 else "REAL"
        confidence = calibrated_fake if prediction == "FAKE" else 1.0 - calibrated_fake
        return DecisionResult(prediction=prediction, raw_probability=raw, calibrated_probability=calibrated_fake, confidence=confidence, lifecycle=DecisionLifecycle.READY, status="CALIBRATED", reason=None, classifier_metadata=self.classifier.metadata(FEATURE_SCHEMA_VERSION), calibration_metadata=self.calibrator.metadata, feature_schema_version=FEATURE_SCHEMA_VERSION, provenance={"features": vector.model_dump()})

    def predict(self, feature_vectors: Iterable[FeatureVector]) -> List[str]:
        vectors = list(feature_vectors)
        self._validate_vectors(vectors)
        return self.classifier.predict([vector.values for vector in vectors])

    def predict_proba(self, feature_vectors: Iterable[FeatureVector], calibrated: bool = False) -> List[float]:
        """Return raw or calibrated probability of FAKE for each feature vector."""

        vectors = list(feature_vectors)
        self._validate_vectors(vectors)
        raw = [float(value) for value in self.classifier.predict_proba([vector.values for vector in vectors])]
        if calibrated:
            if self.calibrator is None:
                raise RuntimeError("calibration is unavailable")
            return [self.calibrator.predict_fake_probability(value) for value in raw]
        return raw

    def metadata(self) -> dict:
        return {
            "lifecycle": self.lifecycle.value,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "classifier": self.classifier.metadata(FEATURE_SCHEMA_VERSION),
            "calibration": self.calibrator.metadata if self.calibrator is not None else {"fitted": False},
        }

    @staticmethod
    def _validate_vectors(vectors: List[FeatureVector]) -> None:
        if not vectors:
            raise ValueError("feature vectors must not be empty")
        if any(vector.schema_version != FEATURE_SCHEMA_VERSION for vector in vectors):
            raise ValueError("feature schema versions must match")
        dimensions = {len(vector.values) for vector in vectors}
        if len(dimensions) != 1:
            raise ValueError("feature dimensions must match")


def _validated_probability(value: float, label: str) -> float:
    try:
        probability = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be finite and in [0, 1]") from error
    if not isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{label} must be finite and in [0, 1]")
    return probability


def _single_probability(values: Iterable[float], label: str) -> float:
    try:
        result = list(values)
    except TypeError as error:
        raise ValueError(f"{label} is unavailable") from error
    if len(result) != 1:
        raise ValueError(f"{label} must contain exactly one value")
    return _validated_probability(result[0], label)
