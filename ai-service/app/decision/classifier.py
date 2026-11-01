"""Trainable lightweight LogisticRegression decision classifier."""

from datetime import datetime, timezone
from typing import Any, Iterable, List

import numpy as np
from sklearn.linear_model import LogisticRegression

from app.decision.schemas import DecisionLifecycle


LABELS = ("REAL", "FAKE")


class DecisionClassifier:
    def __init__(self, random_state: int = 42, **kwargs: Any) -> None:
        self.random_state = random_state
        self.configuration = {"random_state": random_state, **kwargs}
        self.model = LogisticRegression(random_state=random_state, **kwargs)
        self.lifecycle = DecisionLifecycle.UNFITTED
        self.training_sample_count = 0

    @property
    def is_fitted(self) -> bool:
        return self.lifecycle != DecisionLifecycle.UNFITTED

    def fit(self, features: Iterable[Iterable[float]], labels: Iterable[str]) -> "DecisionClassifier":
        matrix = _matrix(features)
        values = list(labels)
        if not values:
            raise ValueError("training data must not be empty")
        _validate_labels(values)
        if matrix.shape[0] != len(values):
            raise ValueError("feature and label counts must match")
        self.model.fit(matrix, values)
        self.training_sample_count = len(values)
        self.lifecycle = DecisionLifecycle.TRAINED
        return self

    def predict(self, features: Iterable[Iterable[float]]) -> List[str]:
        self._require_fitted()
        return list(self.model.predict(_matrix(features)))

    def predict_proba(self, features: Iterable[Iterable[float]]) -> np.ndarray:
        self._require_fitted()
        probabilities = self.model.predict_proba(_matrix(features))
        return _fake_probability(probabilities, self.model.classes_)

    def metadata(self, feature_schema_version: str) -> dict:
        return {
            "classifier_type": "sklearn.linear_model.LogisticRegression",
            "classifier_version": "scikit-learn",
            "feature_schema_version": feature_schema_version,
            "training_status": self.lifecycle.value,
            "class_labels": list(self.model.classes_) if self.is_fitted else list(LABELS),
            "training_sample_count": self.training_sample_count,
            "random_state": self.random_state,
            "configuration": self.configuration,
            "trained_at": datetime.now(timezone.utc).isoformat() if self.is_fitted else None,
        }

    def _require_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError("decision classifier is UNFITTED")


def _matrix(features: Iterable[Iterable[float]]) -> np.ndarray:
    matrix = np.asarray(list(features), dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("features must be a non-empty two-dimensional matrix")
    if not np.isfinite(matrix).all():
        raise ValueError("features must contain only finite values")
    return matrix


def _validate_labels(labels: List[str]) -> None:
    if any(label not in LABELS for label in labels):
        raise ValueError("labels must be exactly REAL or FAKE")
    if len(set(labels)) < 2:
        raise ValueError("training data must contain both REAL and FAKE labels")


def _fake_probability(probabilities: np.ndarray, classes: Iterable[str]) -> np.ndarray:
    classes = list(classes)
    if "FAKE" not in classes:
        raise ValueError("classifier does not contain canonical FAKE class")
    return probabilities[:, classes.index("FAKE")]
