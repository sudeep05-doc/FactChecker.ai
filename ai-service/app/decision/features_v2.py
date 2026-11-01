"""Versioned shared-space features for text-image semantic similarity."""

import math
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.rr.models import ReasoningRepresentation


FEATURE_SCHEMA_VERSION = "rr-decision-v2"
OPENCLIP_MODEL = "ViT-B-32-quickgelu"
OPENCLIP_CHECKPOINT = "openai"
OPENCLIP_DIMENSION = 512
PREDICTOR_ALLOWLIST = (
    "clip_text_embedding",
    "clip_image_embedding",
    "clip_text_image_cosine",
)


class ModalityStatus(str, Enum):
    AVAILABLE = "available"
    INPUT_ABSENT = "input_absent"
    UNAVAILABLE = "unavailable"


class RRDecisionV2Features(BaseModel):
    """Predictor inputs and audit metadata, kept in separate fields."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = FEATURE_SCHEMA_VERSION
    clip_text_embedding: Optional[List[float]] = None
    clip_image_embedding: Optional[List[float]] = None
    clip_text_image_cosine: Optional[float] = Field(default=None, ge=-1, le=1)
    text_status: ModalityStatus
    image_status: ModalityStatus
    text_provenance: Dict[str, Any]
    image_provenance: Dict[str, Any]

    @model_validator(mode="after")
    def validate_feature_contract(self) -> "RRDecisionV2Features":
        if self.schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {FEATURE_SCHEMA_VERSION}")
        self._validate_modality("text", self.clip_text_embedding, self.text_status, self.text_provenance)
        self._validate_modality("image", self.clip_image_embedding, self.image_status, self.image_provenance)
        if self.text_provenance.get("status") != self.text_status.value:
            raise ValueError("text provenance status does not match text_status")
        if self.image_provenance.get("status") != self.image_status.value:
            raise ValueError("image provenance status does not match image_status")
        if self.clip_text_embedding is not None and self.clip_image_embedding is not None:
            if (
                self.text_provenance.get("shared_model_instance") is not True
                or self.image_provenance.get("shared_model_instance") is not True
            ):
                raise ValueError("text and image features must come from the same model instance")
            if self.clip_text_image_cosine is None:
                raise ValueError("cosine similarity is required when both embeddings are available")
            expected = sum(
                left * right
                for left, right in zip(self.clip_text_embedding, self.clip_image_embedding)
            )
            if not math.isclose(self.clip_text_image_cosine, expected, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError("cosine similarity does not match the normalized embeddings")
        elif self.clip_text_image_cosine is not None:
            raise ValueError("cosine similarity must be null unless both embeddings are available")
        return self

    @staticmethod
    def _validate_modality(
        modality: str,
        embedding: Optional[List[float]],
        status: ModalityStatus,
        provenance: Dict[str, Any],
    ) -> None:
        if (
            provenance.get("model_name") != OPENCLIP_MODEL
            or provenance.get("checkpoint") != OPENCLIP_CHECKPOINT
            or provenance.get("weights_verified") is not False
            or provenance.get("checkpoint_weights_sha256") is not None
        ):
            raise ValueError(f"{modality} provenance does not match the configured OpenCLIP checkpoint")
        if status != ModalityStatus.AVAILABLE and not provenance.get("error_code"):
            raise ValueError(f"unavailable {modality} modality requires an error code")
        if status == ModalityStatus.AVAILABLE:
            if embedding is None or len(embedding) != OPENCLIP_DIMENSION:
                raise ValueError(f"available {modality} embedding must have {OPENCLIP_DIMENSION} dimensions")
            if not all(math.isfinite(value) for value in embedding):
                raise ValueError(f"{modality} embedding values must be finite")
            norm = math.sqrt(sum(value * value for value in embedding))
            if not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
                raise ValueError(f"{modality} embedding must be L2-normalized")
            if provenance.get("dimension") != OPENCLIP_DIMENSION:
                raise ValueError(f"{modality} provenance does not match the configured OpenCLIP model")
        elif embedding is not None:
            raise ValueError(f"{modality} embedding must be null when status is {status.value}")

    @property
    def predictor_features(self) -> Dict[str, Any]:
        """Return only explicitly allowlisted fields; provenance never enters predictors."""
        return {name: getattr(self, name) for name in PREDICTOR_ALLOWLIST}


def extract_rr_decision_v2_features(
    *,
    text_embedding: Optional[List[float]],
    image_embedding: Optional[List[float]],
    text_status: ModalityStatus,
    image_status: ModalityStatus,
    text_provenance: Dict[str, Any],
    image_provenance: Dict[str, Any],
    reasoning_representation: Optional[ReasoningRepresentation] = None,
) -> RRDecisionV2Features:
    cosine = None
    if text_embedding is not None and image_embedding is not None:
        if reasoning_representation is None or len(reasoning_representation.pairwise_similarities) != 1:
            raise ValueError("shared-space RR similarity evidence is required for both modalities")
        similarity = reasoning_representation.pairwise_similarities[0]
        if (
            {similarity.left_modality, similarity.right_modality} != {"text", "image"}
            or similarity.left_model != OPENCLIP_MODEL
            or similarity.right_model != OPENCLIP_MODEL
            or similarity.cosine_similarity < -1
            or similarity.cosine_similarity > 1
        ):
            raise ValueError("RR similarity evidence does not match the shared OpenCLIP space")
        cosine = similarity.cosine_similarity
    return RRDecisionV2Features(
        clip_text_embedding=text_embedding,
        clip_image_embedding=image_embedding,
        clip_text_image_cosine=cosine,
        text_status=text_status,
        image_status=image_status,
        text_provenance=text_provenance,
        image_provenance=image_provenance,
    )
