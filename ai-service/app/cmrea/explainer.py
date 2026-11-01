"""RR-only explainability and confidence-calibration boundary."""

from math import isfinite
from math import isclose
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional

from app.cmrea.models import (
    CMREAResult,
    DiagnosticSignal,
    ModalityWeight,
    ReasoningPathEvent,
)
from app.rr.models import ReasoningRepresentation


CalibrationFunction = Callable[[ReasoningRepresentation], Dict[str, Any]]


class ExplainabilityService:
    """Consume RR only; never access applications, media, or model downloads."""

    def __init__(self, calibrator: Optional[CalibrationFunction] = None) -> None:
        self.calibrator = calibrator

    def explain(
        self,
        reasoning_representation: ReasoningRepresentation,
        calibration: Optional[Dict[str, Any]] = None,
        decision_result: Optional[Dict[str, Any]] = None,
    ) -> CMREAResult:
        started_at = perf_counter()
        if decision_result is not None or calibration is not None:
            calibrated = decision_result if decision_result is not None else calibration
            calibrated = _validate_decision_result(calibrated)
        else:
            calibrated = self._calibrate(reasoning_representation)
        modality_weights = _modality_weights(reasoning_representation)
        diagnostic_signals = _diagnostic_signals(reasoning_representation)
        path = _reasoning_path(reasoning_representation)
        uncertainty = _uncertainty_reasons(reasoning_representation, calibrated)

        return CMREAResult(
            request_id=reasoning_representation.request_id,
            prediction=calibrated.get("prediction"),
            confidence=calibrated.get("confidence"),
            confidence_status=("calibrated" if calibrated.get("confidence") is not None else "unavailable"),
            modality_weights=modality_weights,
            diagnostic_signals=diagnostic_signals,
            reasoning_path=path,
            explanation=_explanation(
                reasoning_representation,
                calibrated.get("prediction"),
                calibrated.get("confidence"),
                uncertainty,
            ),
            uncertainty_reasons=uncertainty,
            processing_metadata={
                "calibration_configured": self.calibrator is not None,
                "decision_metadata": calibrated.get("metadata", {}),
                "decision_status": calibrated.get("status"),
                "feature_schema_version": calibrated.get("feature_schema_version"),
                "rr_timestamp": reasoning_representation.timestamp.isoformat(),
                "explanation_time_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        )

    def _calibrate(self, rr: ReasoningRepresentation) -> Dict[str, Any]:
        if self.calibrator is None:
            return {}
        result = self.calibrator(rr)
        if not isinstance(result, dict):
            raise ValueError("calibrator must return a dictionary")
        confidence = result.get("confidence")
        prediction = result.get("prediction")
        return _validate_decision_result({
            "prediction": prediction,
            "confidence": confidence,
            "status": "CALIBRATED" if confidence is not None else "UNAVAILABLE",
        })


def _modality_weights(rr: ReasoningRepresentation) -> List[ModalityWeight]:
    weights = rr.modality_weights
    total = sum(value for modality, value in weights.items() if modality in rr.available_modalities)
    if total <= 0:
        return []
    return [
        ModalityWeight(
            modality=modality,
            configured_weight=weight,
            normalized_weight=weight / total,
            interpretation="configured_heuristic_weight_not_classifier_attribution",
        )
        for modality, weight in sorted(weights.items())
        if modality in rr.available_modalities
    ]


def _validate_decision_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("decision result must be a dictionary")
    prediction = result.get("prediction")
    if prediction is not None and not isinstance(prediction, str):
        raise ValueError("decision prediction must be a string or null")
    confidence = result.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("predicted-class confidence must be finite and in [0, 1]") from error
        if not isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("predicted-class confidence must be finite and in [0, 1]")
        if str(result.get("status", "")).upper() != "CALIBRATED":
            raise ValueError("predicted-class confidence requires calibrated decision status")
        if prediction is None:
            raise ValueError("predicted-class confidence requires a prediction")
    calibrated_fake = result.get("calibrated_probability")
    if calibrated_fake is not None:
        try:
            calibrated_fake = float(calibrated_fake)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("calibrated FAKE probability must be finite and in [0, 1]") from error
        if not isfinite(calibrated_fake) or not 0 <= calibrated_fake <= 1:
            raise ValueError("calibrated FAKE probability must be finite and in [0, 1]")
        if confidence is not None and prediction in {"FAKE", "REAL"}:
            expected_confidence = (
                calibrated_fake if prediction == "FAKE" else 1.0 - calibrated_fake
            )
            if not isclose(confidence, expected_confidence, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(
                    "confidence must match the calibrated probability of the predicted class"
                )
    return {
        **result,
        "prediction": prediction,
        "confidence": confidence,
        "calibrated_probability": calibrated_fake,
    }


def _diagnostic_signals(rr: ReasoningRepresentation) -> List[DiagnosticSignal]:
    signals: List[DiagnosticSignal] = []
    if rr.consistency.score is not None:
        signals.append(DiagnosticSignal(signal="consistency_score", measurement=rr.consistency.score, source="consistency_evaluator", interpretation="evaluator_measurement_not_truth"))
    if rr.contradiction is not None:
        signals.append(DiagnosticSignal(signal="contradiction_score", measurement=rr.contradiction, source="contradiction_evaluator", interpretation="evaluator_measurement_not_truth"))
    for feature in rr.contextual_features:
        signals.append(DiagnosticSignal(signal=feature.name, measurement=feature.value, source="contextual_feature", interpretation="diagnostic_measurement_not_classifier_attribution_or_truth"))
    if rr.reasoning_score is not None:
        signals.append(DiagnosticSignal(signal="reasoning_score", measurement=rr.reasoning_score, source="reasoning", interpretation="diagnostic_measurement_not_classifier_attribution_or_truth"))
    if rr.decision_evidence is not None:
        signals.append(DiagnosticSignal(signal="decision_evidence", measurement=rr.decision_evidence, source="decision_evidence", interpretation="diagnostic_measurement_not_classifier_attribution_or_truth"))
    return signals


def _reasoning_path(rr: ReasoningRepresentation) -> List[ReasoningPathEvent]:
    events = [
        ReasoningPathEvent(
            event="modalities_observed",
            source="available_modalities",
            details={"modalities": rr.available_modalities},
        )
    ]
    if rr.omitted_modalities:
        events.append(ReasoningPathEvent(
            event="modalities_omitted",
            source="omitted_modalities",
            details={"modalities": rr.omitted_modalities},
        ))
    for pair in rr.pairwise_alignments:
        events.append(ReasoningPathEvent(
            event="modalities_aligned",
            source="pairwise_alignment",
            details={
                "left": pair.left_modality,
                "right": pair.right_modality,
                "signed_cosine": pair.signed_cosine,
                "bounded_alignment": pair.bounded_alignment,
            },
        ))
    for pair in rr.pairwise_similarities:
        events.append(ReasoningPathEvent(
            event="cosine_similarity_recorded",
            source="pairwise_similarity",
            details={
                "left": pair.left_modality,
                "right": pair.right_modality,
                "cosine_similarity": pair.cosine_similarity,
                "interpretation": "semantic_similarity_not_consistency_or_truth",
            },
        ))
    if rr.consistency.score is not None:
        events.append(ReasoningPathEvent(event="consistency_assessed", source="consistency", details={"score": rr.consistency.score}))
    if rr.contradiction is not None:
        events.append(ReasoningPathEvent(event="contradiction_assessed", source="contradiction", details={"score": rr.contradiction}))
    if rr.contextual_features:
        events.append(ReasoningPathEvent(
            event="contextual_features_assessed",
            source="contextual_features",
            details={"features": [feature.name for feature in rr.contextual_features]},
        ))
    if rr.reasoning_score is not None:
        events.append(ReasoningPathEvent(event="reasoning_score_available", source="reasoning_score", details={"score": rr.reasoning_score}))
    return events


def _uncertainty_reasons(rr: ReasoningRepresentation, calibrated: Dict[str, Any]) -> List[str]:
    reasons = list(rr.undefined_score_reasons)
    if calibrated.get("confidence") is None:
        reasons.append("CONFIDENCE_CALIBRATION_UNAVAILABLE")
    if not rr.available_modalities:
        reasons.append("NO_AVAILABLE_MODALITIES")
    return sorted(set(reasons))


def _explanation(
    rr: ReasoningRepresentation,
    prediction: Optional[str],
    confidence: Optional[float],
    uncertainty: List[str],
) -> str:
    if not rr.available_modalities:
        return "No processed modalities are available, so no model assessment can be provided. This system does not independently verify factual truth."
    modality_text = ", ".join(rr.available_modalities)
    similarity_note = (
        " Cosine similarity was recorded as semantic similarity, not as consistency or truth."
        if rr.pairwise_similarities
        else ""
    )
    prediction_text = f"The model prediction is {prediction}." if prediction is not None else "No model prediction is available."
    confidence_text = (
        f" Calibrated predicted-class confidence is {confidence:.3f}."
        if confidence is not None
        else " Calibrated predicted-class confidence is unavailable."
    )
    uncertainty_text = " The result is uncertain because required inputs or calibration are unavailable." if uncertainty else ""
    limitations = (
        " Configured modality weights are heuristic; recorded signals are measurements, "
        "not classifier attributions or evidence that a claim is true."
        " This output is not independent factual verification."
    )
    return (
        f"{prediction_text} Available modalities: {modality_text}."
        f"{confidence_text}{uncertainty_text}{similarity_note}{limitations}"
    )
