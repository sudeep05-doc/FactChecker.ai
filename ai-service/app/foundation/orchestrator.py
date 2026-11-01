"""Unified orchestration of existing foundation adapters into USR and CMREF."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from app.cmref import CMREF
from app.foundation.schemas import FoundationAssemblyResult, FoundationIssue
from app.models.image_encoder_schema import ImageEncodingResult, ImageEncodingStatus
from app.models.ocr_schema import OCRResult, OCRStatus
from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus
from app.models.whisper_schema import TranscriptionResult, TranscriptionStatus
from app.usr import (
    USRAudioTranscript,
    USRImage,
    USROCR,
    USRText,
    USRVideo,
    UnifiedSemanticRepresentation,
    UnifiedSemanticRepresentationBuilder,
)


@dataclass
class FoundationAdapterSet:
    """Injected callables around the existing model adapters."""

    text: Optional[Callable[[Any], Any]] = None
    image: Optional[Callable[[Any], Any]] = None
    ocr: Optional[Callable[[Any], Any]] = None
    audio: Optional[Callable[[Any], Any]] = None
    video: Optional[Callable[[Any], Any]] = None


class UnifiedFoundationOrchestrator:
    """Assemble adapter outputs while keeping embeddings and evidence distinct."""

    ORDER = ("text", "image", "ocr", "audio_transcript", "video_transcript")

    def __init__(
        self,
        usr_builder: Optional[UnifiedSemanticRepresentationBuilder] = None,
        cmref: Optional[CMREF] = None,
        adapters: Optional[FoundationAdapterSet] = None,
    ) -> None:
        self.usr_builder = usr_builder or UnifiedSemanticRepresentationBuilder()
        self.cmref = cmref
        self.adapters = adapters or FoundationAdapterSet()

    def run(
        self,
        request_id: UUID,
        *,
        text_input: Any = None,
        image_input: Any = None,
        ocr_input: Any = None,
        audio_input: Any = None,
        video_input: Any = None,
        text_content: Optional[str] = None,
        preprocessing_metadata: Optional[Dict[str, Any]] = None,
        embed_textual_evidence: bool = False,
    ) -> FoundationAssemblyResult:
        outputs: Dict[str, Any] = {}
        errors = []
        warnings = []
        provided = {
            "text": text_input,
            "image": image_input,
            "ocr": ocr_input,
            "audio_transcript": audio_input,
            "video_transcript": video_input,
        }
        adapter_names = {
            "text": "text",
            "image": "image",
            "ocr": "ocr",
            "audio_transcript": "audio",
            "video_transcript": "video",
        }
        for modality in self.ORDER:
            value = provided[modality]
            if value is None:
                continue
            adapter = getattr(self.adapters, adapter_names[modality])
            if adapter is None:
                outputs[modality] = value
                continue
            try:
                outputs[modality] = adapter(value)
            except Exception as error:
                errors.append(FoundationIssue(code="FOUNDATION_ADAPTER_FAILED", message=str(error), modality=modality))

        if embed_textual_evidence:
            warnings.append(FoundationIssue(
                code="TEXTUAL_EVIDENCE_EMBEDDING_UNSUPPORTED",
                message="OCR and transcript embeddings are not part of the current USR contract; structured evidence was preserved.",
                stage="usr",
            ))

        return self.assemble(
            request_id,
            text_output=outputs.get("text"),
            text_content=text_content,
            image_output=outputs.get("image"),
            ocr_output=outputs.get("ocr"),
            audio_output=outputs.get("audio_transcript"),
            video_output=outputs.get("video_transcript"),
            preprocessing_metadata=preprocessing_metadata,
            warnings=warnings,
            errors=errors,
        )

    def assemble(
        self,
        request_id: UUID,
        *,
        text_output: Any = None,
        text_content: Optional[str] = None,
        image_output: Any = None,
        ocr_output: Any = None,
        audio_output: Any = None,
        video_output: Any = None,
        preprocessing_metadata: Optional[Dict[str, Any]] = None,
        warnings: Optional[list[FoundationIssue]] = None,
        errors: Optional[list[FoundationIssue]] = None,
    ) -> FoundationAssemblyResult:
        values = {
            "text": text_output,
            "image": image_output,
            "ocr": ocr_output,
            "audio_transcript": audio_output,
            "video_transcript": video_output,
        }
        representations: Dict[str, Any] = {}
        provenance: Dict[str, Dict[str, Any]] = {}
        issue_errors = list(errors or [])
        issue_warnings = list(warnings or [])
        failed = []
        omitted = []

        for modality in self.ORDER:
            output = values[modality]
            if output is None:
                omitted.append(modality)
                continue
            try:
                representation, metadata = self._representation(modality, output, text_content)
                if representation is None:
                    failed.append(modality)
                    issue_errors.extend(_output_issues(modality, output))
                    continue
                representations[modality] = representation
                provenance[modality] = metadata
            except Exception as error:
                failed.append(modality)
                issue_errors.append(FoundationIssue(code="INVALID_FOUNDATION_OUTPUT", message=str(error), modality=modality))

        try:
            usr = self.usr_builder.build(
                request_id,
                text=representations.get("text"),
                image=representations.get("image"),
                ocr=representations.get("ocr"),
                audio=representations.get("audio_transcript"),
                video=representations.get("video_transcript"),
                modality_metadata=provenance,
                preprocessing_metadata=preprocessing_metadata or {},
            ) if representations else None
        except Exception as error:
            usr = None
            issue_errors.append(FoundationIssue(code="USR_ASSEMBLY_FAILED", message=str(error), stage="usr"))

        cmref_result = None
        if usr is not None and self.cmref is not None:
            try:
                cmref_result = self.cmref.reason(usr)
            except Exception as error:
                issue_errors.append(FoundationIssue(code="CMREF_FAILED", message=str(error), stage="cmref"))

        active = [modality for modality in self.ORDER if modality in representations]
        return FoundationAssemblyResult(
            request_id=request_id,
            active_modalities=active,
            successful_modalities=active,
            omitted_modalities=omitted,
            failed_modalities=sorted(set(failed)),
            usr=usr,
            cmref_result=cmref_result,
            provenance=provenance,
            processing_metadata={"ordering": list(self.ORDER), "textual_evidence_embedding": False},
            warnings=issue_warnings,
            errors=issue_errors,
        )

    @staticmethod
    def _representation(modality: str, output: Any, text_content: Optional[str]):
        if modality == "text":
            if isinstance(output, USRText):
                return output, output.metadata
            if isinstance(output, TextEncodingResult):
                if output.status != TextEncodingStatus.AVAILABLE or not text_content:
                    return None, {}
                return USRText(text=text_content, language=output.language, embedding={
                    "model_name": output.model_name,
                    "dimension": output.embedding_dimension,
                    "values": output.embedding,
                    "normalized": output.normalized,
                }, metadata={"processing": output.processing_metadata, "modality": "text"}), output.processing_metadata
        if modality == "image":
            if isinstance(output, USRImage):
                return output, output.metadata
            if isinstance(output, ImageEncodingResult):
                if output.encoding_status != ImageEncodingStatus.COMPLETED:
                    return None, {}
                return USRImage(image_paths=[output.image_path] if output.image_path else [], embedding={"model_name": output.model_name, "dimension": output.embedding_dimension, "values": output.embedding, "normalized": output.normalized}, metadata={"checkpoint": output.checkpoint, "processing": output.processing_metadata, "modality": "image"}), output.processing_metadata
        if modality == "ocr":
            if isinstance(output, USROCR):
                return output, output.metadata
            if isinstance(output, OCRResult):
                if output.ocr_status != OCRStatus.COMPLETED:
                    return None, {}
                return USROCR(extracted_text=output.extracted_text, raw_text=output.raw_text, normalized_text=output.extracted_text, detections=[item.model_dump() for item in output.detections], bounding_boxes=output.bounding_boxes, ocr_confidence=output.ocr_confidence, language_configuration=output.language_configuration, metadata={"processing": output.processing_metadata, "modality": "ocr", "ocr_confidence_is_truth_confidence": False}), output.processing_metadata
        if modality in {"audio_transcript", "video_transcript"}:
            if isinstance(output, (USRAudioTranscript, USRVideo)):
                return output, output.metadata
            if isinstance(output, TranscriptionResult):
                if output.transcription_status != TranscriptionStatus.COMPLETED:
                    return None, {}
                segments = [item.model_dump() for item in output.segments]
                metadata = {"processing": output.processing_metadata, "modality": modality, "transcription_confidence_is_truth_confidence": False}
                if modality == "audio_transcript":
                    return USRAudioTranscript(transcript=output.transcript, raw_transcript=output.raw_transcript, normalized_transcript=output.normalized_transcript, language=output.detected_language, segments=segments, metadata=metadata), output.processing_metadata
                return USRVideo(transcript=output.transcript, language=output.detected_language, transcript_segments=segments, metadata=metadata), output.processing_metadata
        raise ValueError(f"unsupported or invalid {modality} foundation output")


def _output_issues(modality: str, output: Any) -> list[FoundationIssue]:
    error_code = getattr(output, "error_code", None)
    error_message = getattr(output, "error_message", None)
    if error_code:
        return [FoundationIssue(code=error_code, message=error_message or "Adapter output was unavailable.", modality=modality)]
    source_errors = getattr(output, "errors", None) or []
    if source_errors:
        return [FoundationIssue(code=issue.code, message=issue.message, modality=modality) for issue in source_errors]
    return [FoundationIssue(code="FOUNDATION_OUTPUT_UNAVAILABLE", message="Adapter output was unavailable.", modality=modality)]
