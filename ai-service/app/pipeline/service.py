"""Dependency-injected CAL through CMREA verification orchestration."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Dict, Optional

from app.cal import ContentAcquisitionService
from app.cmrea import ExplainabilityService
from app.cmref import CMREF
from app.pipeline.decision import DecisionCalibration
from app.pipeline.schemas import (
    DecisionCalibrationResult,
    PipelineIssue,
    PipelineStatus,
    VerificationPipelineResult,
)
from app.preprocessing import PreprocessingService
from app.rr import build_reasoning_representation
from app.usr import (
    USRAudioTranscript,
    USRImage,
    USROCR,
    USRText,
    USRVideo,
    UnifiedSemanticRepresentationBuilder,
)
from app.schemas.verification import VerificationRequest


@dataclass
class FoundationAdapters:
    """Optional modality adapters; no model is downloaded by orchestration."""

    text: Optional[Callable[[Any], Any]] = None
    image: Optional[Callable[[Any], Any]] = None
    ocr: Optional[Callable[[Any], Any]] = None
    audio: Optional[Callable[[Any], Any]] = None
    video: Optional[Callable[[Any], Any]] = None
    youtube_description: Optional[Callable[[Any], Any]] = None
    multimodal: Optional[Callable[[Any], Dict[str, Any]]] = None


class VerificationPipeline:
    """Run CAL -> preprocessing -> foundation adapters -> USR -> CMREF -> RR -> decision -> CMREA."""

    def __init__(
        self,
        acquisition: Optional[Any] = None,
        preprocessing: Optional[Any] = None,
        foundation: Optional[FoundationAdapters] = None,
        usr_builder: Optional[UnifiedSemanticRepresentationBuilder] = None,
        cmref: Optional[CMREF] = None,
        decision: Optional[DecisionCalibration] = None,
        cmrea: Optional[ExplainabilityService] = None,
        pipeline_version: str = "pipeline-v1",
    ) -> None:
        self.acquisition = acquisition or ContentAcquisitionService()
        self.preprocessing = preprocessing or PreprocessingService()
        self.foundation = foundation or FoundationAdapters()
        self.usr_builder = usr_builder or UnifiedSemanticRepresentationBuilder()
        self.cmref = cmref
        self.decision = decision or DecisionCalibration()
        self.cmrea = cmrea or ExplainabilityService()
        self.pipeline_version = pipeline_version

    def analyze(self, request: VerificationRequest) -> VerificationPipelineResult:
        started_at = perf_counter()
        errors = []
        warnings = []
        omitted = []
        available = []
        try:
            acquired = self.acquisition.acquire(request)
        except Exception as error:
            return self._failure(request, "ACQUISITION_FAILURE", str(error), "cal")

        if getattr(acquired, "errors", None):
            for issue in acquired.errors:
                warnings.append(PipelineIssue(code=issue.code, message=issue.message, modality=request.input_type.value, stage="cal"))
        if getattr(acquired, "acquisition_status", None).value != "completed":
            return self._failure(request, "ACQUISITION_FAILURE", "Content acquisition did not complete.", "cal", warnings)
        if request.input_type.value == "youtube_url":
            warnings.append(PipelineIssue(
                code="YOUTUBE_DESCRIPTION_ONLY",
                message="Only the acquired YouTube description is routed for text analysis; video and audio are not downloaded or analyzed.",
                modality="youtube_url",
                stage="cal",
            ))

        try:
            prepared = self.preprocessing.process(acquired)
        except Exception as error:
            return self._failure(request, "PREPROCESSING_FAILURE", str(error), "preprocessing", warnings)
        if getattr(prepared, "errors", None):
            for issue in prepared.errors:
                errors.append(PipelineIssue(code=issue.code, message=issue.message, modality=request.input_type.value, stage="preprocessing"))
        if getattr(prepared, "preprocessing_status", None).value != "completed":
            return self._failure(request, "PREPROCESSING_FAILURE", "Preprocessing did not complete.", "preprocessing", warnings, errors)

        representations = {}
        self._adapt_representation(request.input_type.value, prepared, representations, errors, omitted)
        if not representations:
            return self._failure(request, "MODEL_INFERENCE_FAILURE", "No foundation representation was available.", "models", warnings, errors, omitted)

        try:
            usr = self.usr_builder.build(request.request_id, **representations, preprocessing_metadata={"source": "pipeline"})
            available = [item.value for item in usr.available_modalities]
        except Exception as error:
            return self._failure(request, "INVALID_REPRESENTATION", str(error), "usr", warnings, errors, omitted)

        if self.cmref is None:
            return self._failure(request, "CMREF_UNAVAILABLE", "CMREF is not configured.", "cmref", warnings, errors, omitted, available)

        try:
            cmref_result = self.cmref.reason(usr)
            rr = build_reasoning_representation(cmref_result)
            for issue in cmref_result.issues:
                errors.append(
                    PipelineIssue(
                        code=issue.code,
                        message=issue.message,
                        modality=issue.modality,
                        stage="cmref",
                    )
                )
        except Exception as error:
            return self._failure(request, "CMREF_FAILURE", str(error), "cmref", warnings, errors, omitted, available)

        try:
            decision_result = self.decision.decide(rr)
        except Exception as error:
            decision_result = DecisionCalibrationResult(reason="DECISION_COMPONENT_FAILURE", metadata={"error": str(error)})
            errors.append(PipelineIssue(code="DECISION_COMPONENT_FAILURE", message=str(error), stage="decision"))

        try:
            explainable = self.cmrea.explain(
                rr,
                calibration=decision_result.model_dump(mode="json"),
            )
        except Exception as error:
            return self._failure(request, "CMREA_FAILURE", str(error), "cmrea", warnings, errors, omitted, available)

        if decision_result.prediction is None and decision_result.confidence is None:
            uncertainty = list(explainable.uncertainty_reasons)
            uncertainty.append(decision_result.reason or "CALIBRATION_UNAVAILABLE")
        else:
            uncertainty = explainable.uncertainty_reasons
        status = PipelineStatus.COMPLETED if not errors else PipelineStatus.PARTIAL
        return VerificationPipelineResult(
            request_id=request.request_id,
            status=status,
            available_modalities=available,
            omitted_modalities=sorted(set(omitted + rr.omitted_modalities)),
            prediction=explainable.prediction,
            calibrated_confidence=explainable.confidence,
            reasoning_score=rr.reasoning_score,
            modality_weights=[item.model_dump() for item in explainable.modality_weights],
            diagnostic_signals=[item.model_dump() for item in explainable.diagnostic_signals],
            reasoning_path=[item.model_dump() for item in explainable.reasoning_path],
            explanation=explainable.explanation,
            uncertainty=sorted(set(uncertainty + rr.undefined_score_reasons)),
            evidence=rr.model_dump(mode="json"),
            errors=errors,
            warnings=warnings,
            model_versions=rr.model_versions,
            configuration_versions={},
            processing_metadata={"pipeline_version": self.pipeline_version, "elapsed_ms": round((perf_counter() - started_at) * 1000, 3)},
        )

    def _adapt_representation(self, input_type, prepared, representations, errors, omitted):
        if input_type == "youtube_url":
            omitted.extend(["youtube_audio", "youtube_video"])
            adapter = self.foundation.youtube_description
            if adapter is None:
                omitted.append("youtube_description")
                errors.append(PipelineIssue(
                    code="YOUTUBE_DESCRIPTION_ADAPTER_UNAVAILABLE",
                    message="No adapter is configured to analyze the acquired YouTube description as text.",
                    modality="youtube_url",
                    stage="models",
                ))
                return
            try:
                self._merge_representations({"text": adapter(prepared)}, input_type, representations)
            except Exception as error:
                omitted.append("youtube_description")
                errors.append(PipelineIssue(
                    code="YOUTUBE_DESCRIPTION_ADAPTER_FAILURE",
                    message=str(error),
                    modality="youtube_url",
                    stage="models",
                ))
            return
        if self.foundation.multimodal is not None:
            try:
                adapted = self.foundation.multimodal(prepared)
                if not isinstance(adapted, dict):
                    raise ValueError("multimodal foundation adapter must return a dictionary")
                self._merge_representations(adapted, input_type, representations)
            except Exception as error:
                errors.append(PipelineIssue(code="MODEL_INFERENCE_FAILURE", message=str(error), stage="models"))
            return

        adapter = getattr(self.foundation, "text" if input_type in {"text", "pdf", "news_url"} else input_type, None)
        if input_type == "image":
            adapter = self.foundation.image
        elif input_type == "audio":
            adapter = self.foundation.audio
        elif input_type == "video":
            adapter = self.foundation.video
        if adapter is None:
            omitted.append(input_type)
            errors.append(PipelineIssue(code="MODEL_INFERENCE_UNAVAILABLE", message="No foundation adapter is configured.", modality=input_type, stage="models"))
            return
        try:
            key = "text" if input_type in {"text", "pdf", "news_url"} else input_type
            self._merge_representations({key: adapter(prepared)}, input_type, representations)
        except Exception as error:
            omitted.append(input_type)
            errors.append(PipelineIssue(code="MODEL_INFERENCE_FAILURE", message=str(error), modality=input_type, stage="models"))

        if input_type == "image" and self.foundation.ocr is not None:
            try:
                self._merge_representations({"ocr": self.foundation.ocr(prepared)}, input_type, representations)
            except Exception as error:
                omitted.append("ocr")
                errors.append(PipelineIssue(code="MODEL_INFERENCE_FAILURE", message=str(error), modality="ocr", stage="models"))

    @staticmethod
    def _merge_representations(adapted, input_type, representations):
        allowed = {"text", "image", "ocr", "audio", "video"}
        for key, value in adapted.items():
            if key not in allowed:
                raise ValueError(f"unsupported foundation representation: {key}")
            if value is None:
                raise ValueError(f"foundation adapter returned no {key} representation")
            representations[key] = value

    def _failure(self, request, code, message, stage, warnings=None, errors=None, omitted=None, available=None):
        return VerificationPipelineResult(
            request_id=request.request_id,
            status=PipelineStatus.FAILED,
            available_modalities=available or [],
            omitted_modalities=omitted or [request.input_type.value],
            explanation="The submitted content could not be processed completely, so a reliable assessment is unavailable.",
            uncertainty=[code],
            errors=[*(errors or []), PipelineIssue(code=code, message=message, modality=request.input_type.value, stage=stage)],
            warnings=warnings or [],
            processing_metadata={"pipeline_version": self.pipeline_version},
        )
