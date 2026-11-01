"""Offline rr-decision-v2 shared OpenCLIP features for Fakeddit samples."""

from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import NAMESPACE_URL, uuid5

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.config.settings import Settings
from app.decision.features_v2 import (
    FEATURE_SCHEMA_VERSION,
    OPENCLIP_CHECKPOINT,
    OPENCLIP_DIMENSION,
    OPENCLIP_MODEL,
    ModalityStatus,
    extract_rr_decision_v2_features,
)
from app.models import OpenCLIPImageEncoder
from app.models.image_encoder_schema import ImageEncodingStatus
from app.models.text_encoder_schema import TextEncodingStatus
from app.rr import build_reasoning_representation
from app.usr import UnifiedSemanticRepresentationBuilder


def build_shared_space_feature_artifact(
    sample: dict,
    *,
    data_dir: Union[str, Path],
    encoder: Optional[OpenCLIPImageEncoder] = None,
    device: str = "auto",
) -> Dict[str, Any]:
    """Build one isolated feature artifact; this does not train or run a classifier."""
    sample_id = str(sample.get("sample_id") or "").strip()
    if not sample_id:
        raise ValueError("sample requires a non-empty sample_id")
    encoder = encoder or OpenCLIPImageEncoder(
        settings=Settings(
            image_encoder_model=OPENCLIP_MODEL,
            image_encoder_checkpoint=OPENCLIP_CHECKPOINT,
            image_encoder_device=device,
        )
    )
    if encoder.model_name != OPENCLIP_MODEL or encoder.checkpoint != OPENCLIP_CHECKPOINT:
        raise ValueError("rr-decision-v2 requires ViT-B-32-quickgelu with the openai checkpoint")

    sample_metadata = sample.get("metadata") or {}
    clean_title = str(sample.get("text") or sample_metadata.get("clean_title") or "")
    text_result = encoder.encode_text(clean_title, language="en")
    text_available = text_result.status == TextEncodingStatus.AVAILABLE
    text_usr = encoder.to_usr_text_from_result(clean_title, text_result) if text_available else None
    text_status = (
        ModalityStatus.AVAILABLE
        if text_available
        else ModalityStatus.INPUT_ABSENT
        if text_result.error_code == "TEXT_EMPTY"
        else ModalityStatus.UNAVAILABLE
    )
    text_embedding = text_result.embedding if text_available else None
    text_provenance = _modality_provenance(
        encoder,
        status=text_status.value,
        dimension=text_result.embedding_dimension,
        processing=text_result.processing_metadata,
        error_code=text_result.error_code,
        error_message=text_result.error_message,
    )

    image_value = sample_metadata.get("local_image_path") or sample.get("local_image_path")
    image_path = _resolve_image_path(sample, Path(data_dir))
    image_result = encoder.encode(str(image_path)) if image_path is not None else None
    image_available = (
        image_result is not None
        and image_result.encoding_status == ImageEncodingStatus.COMPLETED
    )
    image_usr = encoder.to_usr_image_from_result(image_result) if image_available else None
    image_status = (
        ModalityStatus.AVAILABLE
        if image_available
        else ModalityStatus.INPUT_ABSENT
        if not image_value
        else ModalityStatus.UNAVAILABLE
    )
    image_embedding = image_result.embedding if image_available else None
    if image_result is not None and image_result.errors:
        image_error_code = image_result.errors[0].code
        image_error_message = image_result.errors[0].message
    elif not image_value:
        image_error_code = "IMAGE_INPUT_ABSENT"
        image_error_message = "No local image path was provided."
    elif image_path is None:
        image_error_code = "IMAGE_NOT_FOUND"
        image_error_message = "The provided local image path could not be resolved."
    else:
        image_error_code = None
        image_error_message = None
    image_provenance = _modality_provenance(
        encoder,
        status=image_status.value,
        dimension=image_result.embedding_dimension if image_available else None,
        processing=image_result.processing_metadata if image_result is not None else {},
        error_code=image_error_code,
        error_message=image_error_message,
        image_path=str(image_path) if image_path is not None else None,
    )

    rr = None
    if text_usr is not None or image_usr is not None:
        usr = UnifiedSemanticRepresentationBuilder().build(
            uuid5(NAMESPACE_URL, sample_id),
            text=text_usr,
            image=image_usr,
        )
        cmref_result = CMREF(
            ProjectionRegistry(OPENCLIP_DIMENSION),
            alignment_mode="similarity_only",
        ).reason(usr)
        rr = build_reasoning_representation(cmref_result)

    features = extract_rr_decision_v2_features(
        text_embedding=text_embedding,
        image_embedding=image_embedding,
        text_status=text_status,
        image_status=image_status,
        text_provenance=text_provenance,
        image_provenance=image_provenance,
        reasoning_representation=rr,
    )
    split = sample.get("split")
    return {
        "sample_identity": {
            "sample_id": sample_id,
            "source_reference": sample.get("source_reference") or sample_id,
            "split": split,
        },
        "label": sample.get("label"),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "predictor_features": features.predictor_features,
        "modality_status": {
            "text": features.text_status.value,
            "image": features.image_status.value,
        },
        "modality_provenance": {
            "text": features.text_provenance,
            "image": features.image_provenance,
        },
        "reasoning_representation": rr.model_dump(mode="json") if rr is not None else None,
    }


def _modality_provenance(
    encoder: OpenCLIPImageEncoder,
    *,
    status: str,
    dimension: Optional[int],
    processing: Dict[str, Any],
    error_code: Optional[str],
    error_message: Optional[str],
    image_path: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "model_name": encoder.model_name,
        "checkpoint": encoder.checkpoint,
        "checkpoint_weights_sha256": None,
        "weights_verified": False,
        "dimension": dimension,
        "shared_model_instance": True,
        "processing": processing,
        "error_code": error_code,
        "error_message": error_message,
        "image_path": image_path,
    }


def _resolve_image_path(sample: dict, data_dir: Path) -> Optional[Path]:
    metadata = sample.get("metadata") or {}
    image_value = metadata.get("local_image_path") or sample.get("local_image_path")
    if not image_value:
        return None
    candidate = Path(str(image_value)).expanduser()
    if not candidate.is_absolute():
        candidate = data_dir / candidate
    return candidate.resolve() if candidate.is_file() else None
