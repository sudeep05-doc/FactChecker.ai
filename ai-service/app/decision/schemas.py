"""Decision-layer feature, lifecycle, and output contracts."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DecisionLifecycle(str, Enum):
    UNFITTED = "unfitted"
    TRAINED = "trained"
    CALIBRATED = "calibrated"
    READY = "ready"


class FeatureVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    names: List[str]
    values: List[float]
    missing: Dict[str, bool] = Field(default_factory=dict)
    schema_version: str
    provenance: Dict[str, str] = Field(default_factory=dict)


class DecisionResult(BaseModel):
    """Decision output; class probabilities and predicted-class confidence are distinct."""

    prediction: Optional[str] = None
    raw_probability: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Uncalibrated classifier probability of FAKE; probability of REAL is 1 minus this value.",
    )
    calibrated_probability: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Calibrated probability of FAKE; probability of REAL is 1 minus this value.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Calibrated probability of the predicted class, not a factual truth score; null when calibration is unavailable.",
    )
    status: str = "CALIBRATION_UNAVAILABLE"
    lifecycle: DecisionLifecycle = DecisionLifecycle.UNFITTED
    reason: Optional[str] = "CALIBRATION_UNAVAILABLE"
    classifier_metadata: Dict[str, Any] = Field(default_factory=dict)
    calibration_metadata: Dict[str, Any] = Field(default_factory=dict)
    feature_schema_version: str = "rr-decision-v1"
    provenance: Dict[str, Any] = Field(default_factory=dict)
