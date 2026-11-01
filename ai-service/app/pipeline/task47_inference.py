"""Verified Task 47 modality-specific Fakeddit inference."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from app.config.settings import Settings
from app.decision.features_v2 import OPENCLIP_CHECKPOINT, OPENCLIP_DIMENSION, OPENCLIP_MODEL
from app.models import OpenCLIPImageEncoder
from app.models.image_encoder_schema import ImageEncodingStatus
from app.models.text_encoder_schema import TextEncodingStatus
from app.preprocessing.pdf import PDFPreprocessor
from app.cal.schemas import AcquisitionStatus, CALResult


EXPERIMENT_ID = "task47-modality-specific-classifiers-20261029"
AI_SERVICE_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = (
    AI_SERVICE_ROOT
    / "data/research/fakeddit-experiments"
    / EXPERIMENT_ID
)
EXPECTED_CHECKPOINT_SHA256 = "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"
EXPECTED_MODEL_SHA256 = {
    "text_only": "b21d0bf39b65a553daf6a979da8b572d9b4ec2cd523d020765a9ee5571c29d2a",
    "image_only": "011405847db2e44199b00154935bf48d4d5dee1c70428060c94de4f68950276b",
}
LIMITATION_NOTICE = (
    "This model predicts Fakeddit's distant-supervision FAKE/REAL dataset labels. "
    "It does not verify factual truth, and its uncalibrated classifier scores are not factual confidence."
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PDF_TEXT_CHARACTERS = 1_000_000
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class InferenceUnavailableError(RuntimeError):
    """Raised when a verified model or encoder cannot be loaded or used."""


class InvalidInferenceInputError(ValueError):
    """Raised when an input is invalid for this inference route."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_model_manifest() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    config_path = EXPERIMENT_ROOT / "configuration.json"
    inventory_path = EXPERIMENT_ROOT / "sha256_inventory.json"
    if not config_path.is_file() or not inventory_path.is_file():
        raise InferenceUnavailableError(
            "Task 47 modality-specific model artifacts are not available."
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise InferenceUnavailableError("Task 47 configuration has an unexpected experiment ID.")
    if config.get("task36c_schema_version") != "rr-decision-v2":
        raise InferenceUnavailableError("Task 47 feature schema is incompatible.")
    if config.get("encoder", {}).get("architecture") != OPENCLIP_MODEL:
        raise InferenceUnavailableError("Task 47 encoder architecture is incompatible.")
    if config.get("encoder", {}).get("pretrained_configuration") != OPENCLIP_CHECKPOINT:
        raise InferenceUnavailableError("Task 47 checkpoint configuration is incompatible.")
    if config.get("encoder", {}).get("checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA256:
        raise InferenceUnavailableError("Task 47 checkpoint hash contract is incompatible.")
    entries = {
        item["path"]: item
        for item in inventory.get("artifacts", [])
        if isinstance(item, dict) and "path" in item
    }
    for name in ("text_only", "image_only"):
        relative = config.get("models", {}).get(name, {}).get("artifact")
        entry = entries.get(relative)
        path = EXPERIMENT_ROOT / str(relative)
        if not relative or entry is None or not path.is_file():
            raise InferenceUnavailableError(f"Task 47 {name} model artifact is missing.")
        if entry.get("sha256") != EXPECTED_MODEL_SHA256[name]:
            raise InferenceUnavailableError(f"Task 47 {name} model manifest hash is unexpected.")
        if path.stat().st_size != entry.get("size_bytes") or _sha256(path) != entry.get("sha256"):
            raise InferenceUnavailableError(f"Task 47 {name} model artifact failed SHA-256 verification.")
    return config, entries


class Task47Inference:
    """Load verified estimators and lazily create the frozen Task 36C encoder."""

    def __init__(
        self,
        *,
        checkpoint_path: Optional[Path] = None,
        encoder: Optional[OpenCLIPImageEncoder] = None,
    ) -> None:
        self.config, self.inventory = _load_model_manifest()
        self.models: Dict[str, LogisticRegression] = {}
        for name in ("text_only", "image_only"):
            relative = self.config["models"][name]["artifact"]
            estimator = joblib.load(EXPERIMENT_ROOT / relative)
            if not isinstance(estimator, LogisticRegression):
                raise InferenceUnavailableError(f"Task 47 {name} artifact is not LogisticRegression.")
            if estimator.n_features_in_ != OPENCLIP_DIMENSION:
                raise InferenceUnavailableError(f"Task 47 {name} model is not 512-dimensional.")
            if not np.array_equal(estimator.classes_, np.asarray([0, 1])):
                raise InferenceUnavailableError(f"Task 47 {name} class order is not FAKE=0, REAL=1.")
            if (
                estimator.solver != "lbfgs"
                or estimator.penalty != "l2"
                or estimator.max_iter != 2000
                or estimator.C != 10.0
            ):
                raise InferenceUnavailableError(f"Task 47 {name} classifier configuration is unexpected.")
            self.models[name] = estimator

        self.checkpoint_path = checkpoint_path or Path(
            os.environ.get(
                "TASK36C_OPENCLIP_CHECKPOINT",
                str(Path.home() / ".cache/clip/ViT-B-32.pt"),
            )
        ).expanduser()
        if not self.checkpoint_path.is_file():
            raise InferenceUnavailableError(
                f"Verified Task 36C OpenCLIP checkpoint is missing: {self.checkpoint_path}"
            )
        if _sha256(self.checkpoint_path) != EXPECTED_CHECKPOINT_SHA256:
            raise InferenceUnavailableError("Local OpenCLIP checkpoint SHA-256 does not match Task 36C.")
        self.encoder = encoder or OpenCLIPImageEncoder(
            settings=Settings(
                image_encoder_model=OPENCLIP_MODEL,
                image_encoder_checkpoint=OPENCLIP_CHECKPOINT,
                image_encoder_device="auto",
                image_encoder_batch_size=1,
            ),
            model_factory=self._load_local_openclip,
        )

    def _load_local_openclip(self, model_name: str, checkpoint_label: str, device: str) -> Tuple[Any, Any]:
        if model_name != OPENCLIP_MODEL or checkpoint_label != OPENCLIP_CHECKPOINT:
            raise InferenceUnavailableError("Requested OpenCLIP configuration differs from Task 36C.")
        import open_clip
        import torch

        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=None,
            device="cpu",
        )
        scripted_checkpoint = torch.jit.load(
            str(self.checkpoint_path),
            map_location="cpu",
        )
        state_dict = scripted_checkpoint.state_dict()
        for metadata_key in ("input_resolution", "context_length", "vocab_size"):
            state_dict.pop(metadata_key, None)
        model.load_state_dict(state_dict, strict=True)
        del scripted_checkpoint
        model.to(device)
        model.eval()
        return model, preprocess

    def predict_text(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise InvalidInferenceInputError("Text must contain at least one non-whitespace character.")
        encoded = self.encoder.encode_text(text, language="en")
        if encoded.status != TextEncodingStatus.AVAILABLE or encoded.embedding is None:
            raise InferenceUnavailableError(
                f"OpenCLIP text encoding failed: {encoded.error_code or 'unknown error'}."
            )
        return self._predict(
            "text_only",
            np.asarray(encoded.embedding, dtype=np.float32),
            preprocessing={
                "encoder": OPENCLIP_MODEL,
                "checkpoint": OPENCLIP_CHECKPOINT,
                "embedding_dimension": encoded.embedding_dimension,
                "normalized": encoded.normalized,
                "tokenization": encoded.processing_metadata,
            },
        )

    def predict_image(self, image_bytes: bytes, content_type: str) -> Dict[str, Any]:
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise InvalidInferenceInputError("Image must be JPEG, PNG, or WebP.")
        if not image_bytes:
            raise InvalidInferenceInputError("Image upload is empty.")
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise InvalidInferenceInputError("Image exceeds the 25 MB upload limit.")
        encoded = self.encoder.encode(image_bytes)
        if encoded.encoding_status != ImageEncodingStatus.COMPLETED or encoded.embedding is None:
            if encoded.errors and encoded.errors[0].code in {
                "INVALID_IMAGE",
                "IMAGE_NOT_FOUND",
                "UNSUPPORTED_IMAGE_INPUT",
            }:
                raise InvalidInferenceInputError("Uploaded bytes are not a readable image.")
            raise InferenceUnavailableError(
                f"OpenCLIP image encoding failed: "
                f"{encoded.errors[0].code if encoded.errors else 'unknown error'}."
            )
        return self._predict(
            "image_only",
            np.asarray(encoded.embedding, dtype=np.float32),
            preprocessing={
                "encoder": OPENCLIP_MODEL,
                "checkpoint": OPENCLIP_CHECKPOINT,
                "embedding_dimension": encoded.embedding_dimension,
                "normalized": encoded.normalized,
                "image_preprocessing": encoded.processing_metadata.get("image_preprocessing"),
            },
        )

    def predict_pdf(self, pdf_bytes: bytes) -> Dict[str, Any]:
        if not pdf_bytes:
            raise InvalidInferenceInputError("PDF upload is empty.")
        if len(pdf_bytes) > MAX_UPLOAD_BYTES:
            raise InvalidInferenceInputError("PDF exceeds the 25 MB upload limit.")
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_file:
            temporary_file.write(pdf_bytes)
            temporary_file.flush()
            result = PDFPreprocessor().process(
                CALResult(
                    request_id=uuid4(),
                    input_type="pdf",
                    source=temporary_file.name,
                    metadata={"file_path": temporary_file.name},
                    acquisition_status=AcquisitionStatus.COMPLETED,
                )
            )
            if result.preprocessing_status.value != "completed":
                issue = result.errors[0] if result.errors else None
                raise InvalidInferenceInputError(
                    issue.message if issue else "PDF could not be processed."
                )
            extracted = result.extracted_text.strip()
            if not extracted:
                raise InvalidInferenceInputError(
                    "PDF contains no extractable text; scanned PDFs require OCR, which is not supported."
                )
            if len(extracted) > MAX_PDF_TEXT_CHARACTERS:
                raise InvalidInferenceInputError(
                    "PDF extracted text exceeds the 1,000,000-character processing limit."
                )
            prediction = self.predict_text(extracted)
            prediction["input_type"] = "pdf"
            prediction["limitation_notice"] += (
                " PDF support extracts embedded text only; scanned PDFs and OCR are not supported."
            )
            prediction["preprocessing"]["pdf_page_count"] = result.page_count
            prediction["preprocessing"]["extracted_character_count"] = len(extracted)
            prediction["preprocessing"]["ocr"] = "not_supported"
            return prediction

    def _predict(self, model_name: str, embedding: np.ndarray, *, preprocessing: Dict[str, Any]) -> Dict[str, Any]:
        if embedding.shape != (OPENCLIP_DIMENSION,) or not np.isfinite(embedding).all():
            raise InferenceUnavailableError("OpenCLIP returned an invalid embedding shape or values.")
        norm = float(np.linalg.norm(embedding))
        if abs(norm - 1.0) > 1e-4:
            raise InferenceUnavailableError("OpenCLIP returned a non-normalized embedding.")
        estimator = self.models[model_name]
        if estimator.n_features_in_ != embedding.shape[0]:
            raise InferenceUnavailableError("Embedding dimension does not match the selected classifier.")
        scores = estimator.predict_proba(embedding.reshape(1, -1))[0]
        fake_score = float(scores[list(estimator.classes_).index(0)])
        real_score = float(scores[list(estimator.classes_).index(1)])
        threshold = float(self.config["probabilities"]["threshold"])
        prediction = "REAL" if real_score >= threshold else "FAKE"
        class_scores = {
            "FAKE": fake_score,
            "REAL": real_score,
        }
        return {
            "status": "completed",
            "is_mock": False,
            "prediction_type": "dataset_classification",
            "evidence_status": "not_applicable",
            "verdict": None,
            "prediction": prediction,
            "dataset_prediction": prediction,
            "dataset_identity": "Fakeddit 2-way distant-supervision label",
            "model_identity": f"{EXPERIMENT_ID}/{model_name}",
            "dataset_score": class_scores[prediction],
            "class_scores": class_scores,
            "confidence_semantics": "uncalibrated_dataset_score",
            "explanation_provenance": "dataset_classifier",
            "score_semantics": (
                "Uncalibrated LogisticRegression predict_proba scores for Fakeddit labels; "
                "not factual confidence."
            ),
            "decision_threshold": threshold,
            "model_id": f"{EXPERIMENT_ID}/{model_name}",
            "experiment_id": EXPERIMENT_ID,
            "feature_schema_version": "rr-decision-v2",
            "processing_status": "completed",
            "limitation_notice": LIMITATION_NOTICE,
            "preprocessing": preprocessing,
        }
