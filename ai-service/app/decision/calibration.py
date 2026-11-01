"""Explicit validation-set sigmoid probability calibration."""

import numpy as np
from sklearn.linear_model import LogisticRegression


class SigmoidCalibrator:
    def __init__(self) -> None:
        self.model = LogisticRegression(random_state=42)
        self.fitted = False

    def fit(self, raw_probabilities, labels) -> "SigmoidCalibrator":
        probabilities = np.asarray(list(raw_probabilities), dtype=float).reshape(-1, 1)
        values = list(labels)
        if len(values) == 0 or probabilities.shape[0] != len(values):
            raise ValueError("validation probabilities and labels must be non-empty and aligned")
        if set(values) != {"REAL", "FAKE"}:
            raise ValueError("validation calibration requires both REAL and FAKE labels")
        if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
            raise ValueError("raw probabilities must be finite and bounded")
        self.model.fit(probabilities, values)
        self.fitted = True
        return self

    def predict_fake_probability(self, raw_probability: float) -> float:
        if not self.fitted:
            raise RuntimeError("calibrator is not fitted")
        value = float(self.model.predict_proba([[raw_probability]])[0, list(self.model.classes_).index("FAKE")])
        return min(1.0, max(0.0, value))

    @property
    def metadata(self) -> dict:
        return {"method": "sigmoid", "fitted": self.fitted, "calibration_classes": list(self.model.classes_) if self.fitted else []}
