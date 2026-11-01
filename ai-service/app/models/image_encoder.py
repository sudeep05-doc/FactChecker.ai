"""Lazy OpenCLIP image encoding with validated USR-compatible output."""

import io
import importlib.metadata
import math
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.config.settings import Settings, get_settings
from app.models.image_encoder_schema import (
    ImageEncodingIssue,
    ImageEncodingResult,
    ImageEncodingStatus,
)
from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus
from app.models.text_encoder import resolve_device
from app.preprocessing.image_schema import ImagePreprocessingResult, ImagePreprocessingStatus
from app.usr.models import USREmbedding, USRImage, USRText


DEFAULT_IMAGE_ENCODER_MODEL = "ViT-B-32"
DEFAULT_IMAGE_ENCODER_CHECKPOINT = "openai"


class OpenCLIPImageEncoder:
    """Reuse one lazily loaded OpenCLIP model and its associated transform."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        model_factory: Optional[Callable[..., Any]] = None,
        tokenizer_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.image_encoder_model
        self.checkpoint = self.settings.image_encoder_checkpoint
        self.requested_device = self.settings.image_encoder_device
        self.batch_size = self.settings.image_encoder_batch_size
        self.model_factory = model_factory
        self.tokenizer_factory = tokenizer_factory
        self._model: Optional[Any] = None
        self._preprocess: Optional[Callable[..., Any]] = None
        self._tokenizer: Optional[Any] = None
        self._loaded_model_config: Optional[Tuple[str, str]] = None
        self._tokenizer_model_name: Optional[str] = None
        self._resolved_device: Optional[str] = None
        self._model_load_lock = threading.Lock()
        if self.batch_size < 1:
            raise ValueError("image_encoder_batch_size must be positive")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._preprocess is not None

    @property
    def resolved_device(self) -> Optional[str]:
        return self._resolved_device

    def encode(self, image: Any) -> ImageEncodingResult:
        return self.encode_batch([image])[0]

    def encode_text(self, text: str, language: Optional[str] = None) -> TextEncodingResult:
        return self.encode_text_batch([text], language=language)[0]

    def encode_text_batch(
        self,
        texts: Iterable[str],
        language: Optional[str] = None,
    ) -> List[TextEncodingResult]:
        inputs = list(texts)
        results: List[Optional[TextEncodingResult]] = [None] * len(inputs)
        if not inputs:
            return [self._text_failure("", "TEXT_EMPTY", "No text input was provided.", language)]

        active_indices = []
        for index, text in enumerate(inputs):
            if not isinstance(text, str) or not text.strip():
                results[index] = self._text_failure(
                    text if isinstance(text, str) else "",
                    "TEXT_EMPTY",
                    "Text is empty or whitespace-only.",
                    language,
                    text_status="input_absent",
                )
            else:
                active_indices.append(index)
        if not active_indices:
            return [result for result in results if result is not None]

        try:
            tokenizer = self._get_tokenizer()
        except Exception as error:
            for index in active_indices:
                results[index] = self._text_failure(
                    inputs[index], "TEXT_TOKENIZER_UNAVAILABLE", str(error), language
                )
            return [result for result in results if result is not None]

        token_rows: List[List[int]] = []
        token_metadata: List[dict] = []
        source_indices: List[int] = []
        for index in active_indices:
            text = inputs[index]
            try:
                context_length = int(tokenizer.context_length)
                if context_length < 3:
                    raise ValueError("OpenCLIP tokenizer context length must be at least three")
                body_tokens = list(tokenizer.encode(text))
                token_count = len(body_tokens) + 2
                truncated = token_count > context_length
                if truncated:
                    body_tokens = body_tokens[:context_length - 2]
                tokens = [int(tokenizer.sot_token_id), *map(int, body_tokens), int(tokenizer.eot_token_id)]
                tokens.extend([0] * (context_length - len(tokens)))
                token_rows.append(tokens)
                source_indices.append(index)
                token_metadata.append({
                    "tokenizer_identity": f"open_clip.get_tokenizer:{self.model_name}",
                    "tokenizer_class": type(tokenizer).__name__,
                    "tokenizer_context_length": context_length,
                    "token_count_before_truncation": token_count,
                    "token_count_after_truncation": len(body_tokens) + 2,
                    "truncation_applied": truncated,
                    "truncation_policy": "preserve_start_end_tokens_truncate_body_to_context_minus_2-v1",
                })
            except Exception as error:
                results[index] = self._text_failure(
                    text,
                    "TEXT_TOKENIZATION_FAILED",
                    str(error),
                    language,
                    text_status="preprocessing_failed",
                )

        if token_rows:
            try:
                model, _ = self._get_model()
                if not hasattr(model, "encode_text"):
                    raise ValueError("configured OpenCLIP model does not expose encode_text")
                torch = _load_torch()
                tokens = torch.tensor(token_rows, dtype=torch.long)
                features = self._encode_text_features(model, tokens, torch)
                array = features.detach().float().cpu().numpy()
                if array.ndim != 2 or array.shape[0] != len(source_indices):
                    raise ValueError("OpenCLIP returned an invalid text batch shape")
                for row_index, source_index in enumerate(source_indices):
                    vector = array[row_index].astype(float).tolist()
                    norm = math.sqrt(sum(value * value for value in vector))
                    if not vector or not all(math.isfinite(value) for value in vector) or not math.isfinite(norm) or norm <= 1e-12:
                        results[source_index] = self._text_failure(
                            inputs[source_index],
                            "INVALID_TEXT_EMBEDDING",
                            "OpenCLIP returned an empty, non-finite, or zero-norm text embedding.",
                            language,
                        )
                        continue
                    vector = [value / norm for value in vector]
                    results[source_index] = TextEncodingResult(
                        model_name=self.model_name,
                        embedding_dimension=len(vector),
                        embedding=vector,
                        language=language,
                        normalized=True,
                        processing_metadata={
                            **token_metadata[row_index],
                            "device": self._resolved_device,
                            "requested_device": self.requested_device,
                            "checkpoint": self.checkpoint,
                            "open_clip_version": _distribution_version("open_clip_torch"),
                            "torch_version": torch.__version__,
                            "normalized_embedding": True,
                            "deterministic_inference": True,
                        },
                    )
            except Exception as error:
                for source_index in source_indices:
                    results[source_index] = self._text_failure(
                        inputs[source_index],
                        "TEXT_ENCODING_FAILED",
                        str(error),
                        language,
                        text_status="inference_failed",
                    )
        return [result for result in results if result is not None]

    def encode_batch(self, images: Iterable[Any]) -> List[ImageEncodingResult]:
        inputs = list(images)
        if not inputs:
            return [self._failure(None, "IMAGE_EMPTY", "No image input was provided.")]

        prepared: List[Tuple[int, ImagePreprocessingResult, Image.Image]] = []
        results: List[Optional[ImageEncodingResult]] = [None] * len(inputs)
        for index, image in enumerate(inputs):
            item, pil_image, failure = self._load_input(image)
            if failure is not None:
                results[index] = failure
            else:
                prepared.append((index, item, pil_image))

        if not prepared:
            return [result for result in results if result is not None]

        try:
            model, preprocess = self._get_model()
            torch = _load_torch()
            tensors = [preprocess(pil_image) for _, _, pil_image in prepared]
            tensor_batch = torch.stack(tensors)
            features = self._encode_features(model, tensor_batch, torch)
            if features.ndim == 1:
                features = features.reshape(1, -1)
            if features.ndim != 2 or features.shape[0] != len(prepared):
                raise ValueError("OpenCLIP returned an invalid batch shape")
            array = features.detach().float().cpu().numpy()
            if array.shape[1] < 1 or not np.isfinite(array).all():
                raise ValueError("OpenCLIP returned a non-finite or empty embedding")
            for row_index, (original_index, item, _) in enumerate(prepared):
                results[original_index] = self._success(item, array[row_index].tolist())
        except Exception as error:
            for original_index, item, _ in prepared:
                results[original_index] = self._failure(item, "IMAGE_ENCODING_FAILED", f"OpenCLIP encoding failed: {error}.")

        return [result for result in results if result is not None]

    def to_usr_image(self, image: Any) -> Optional[USRImage]:
        return self.to_usr_image_from_result(self.encode(image))

    def to_usr_text(self, text: str, language: Optional[str] = None) -> Optional[USRText]:
        return self.to_usr_text_from_result(text, self.encode_text(text, language=language))

    def to_usr_text_from_result(self, text: str, result: TextEncodingResult) -> Optional[USRText]:
        if result.status != TextEncodingStatus.AVAILABLE:
            return None
        return USRText(
            text=text,
            language=result.language,
            embedding=USREmbedding(
                model_name=result.model_name,
                dimension=result.embedding_dimension,
                values=result.embedding,
                normalized=result.normalized,
            ),
            metadata={
                "modality": "text",
                "checkpoint": self.checkpoint,
                "processing": result.processing_metadata,
            },
        )

    def to_usr_image_from_result(self, result: ImageEncodingResult) -> Optional[USRImage]:
        if result.encoding_status != ImageEncodingStatus.COMPLETED:
            return None
        return USRImage(
            image_paths=[result.image_path] if result.image_path else [],
            embedding=USREmbedding(
                model_name=result.model_name,
                dimension=result.embedding_dimension,
                values=result.embedding,
                normalized=result.normalized,
            ),
            metadata={
                "modality": result.modality,
                "checkpoint": result.checkpoint,
                "processing": result.processing_metadata,
            },
        )

    def _load_input(self, image: Any) -> Tuple[Optional[ImagePreprocessingResult], Optional[Image.Image], Optional[ImageEncodingResult]]:
        if isinstance(image, ImagePreprocessingResult):
            if image.preprocessing_status != ImagePreprocessingStatus.COMPLETED:
                return image, None, self._failure(image, "IMAGE_PREPROCESSING_FAILED", "The image was not successfully preprocessed.")
            if not image.processed_image_path:
                return image, None, self._failure(image, "IMAGE_PATH_UNAVAILABLE", "No processed image path was provided.")
            path = Path(image.processed_image_path)
            if not path.is_file():
                return image, None, self._failure(image, "IMAGE_NOT_FOUND", "The processed image path does not exist.")
            request_id = image.request_id
            image_path = str(path)
        else:
            request_id = uuid4()
            image_path = None

        try:
            if isinstance(image, bytes):
                if not image:
                    raise ValueError("image bytes are empty")
                opened = Image.open(io.BytesIO(image))
            elif isinstance(image, (str, Path)):
                path = Path(image).expanduser()
                if not path.is_file():
                    return None, None, self._failure_for(request_id, image_path, "IMAGE_NOT_FOUND", "The image path does not exist.")
                opened = Image.open(path)
                image_path = str(path)
            elif isinstance(image, Image.Image):
                opened = image
            elif isinstance(image, ImagePreprocessingResult):
                opened = Image.open(image.processed_image_path)
            else:
                return None, None, self._failure_for(request_id, image_path, "UNSUPPORTED_IMAGE_INPUT", "Expected a preprocessed image, path, bytes, or PIL image.")
            opened.load()
            pil_image = opened.convert("RGB")
            if isinstance(image, ImagePreprocessingResult):
                return image, pil_image, None
            generated = ImagePreprocessingResult(
                request_id=request_id,
                input_type="image",
                processed_image_path=image_path,
                width=pil_image.width,
                height=pil_image.height,
                format=pil_image.format,
                preprocessing_status=ImagePreprocessingStatus.COMPLETED,
            )
            return generated, pil_image, None
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
            return None, None, self._failure_for(request_id, image_path, "INVALID_IMAGE", f"Image could not be opened safely: {error}.")

    def _encode_features(self, model: Any, tensor_batch: Any, torch: Any) -> Any:
        if hasattr(model, "eval"):
            model.eval()
        started_at = time.perf_counter()
        try:
            tensor_batch = tensor_batch.to(self._resolved_device)
            with torch.no_grad():
                features = model.encode_image(tensor_batch)
        except RuntimeError:
            if self._resolved_device != "mps":
                raise
            self._resolved_device = "cpu"
            if hasattr(model, "to"):
                model = model.to("cpu")
            with torch.no_grad():
                features = model.encode_image(tensor_batch.to("cpu"))
        self._last_inference_time_ms = round((time.perf_counter() - started_at) * 1000, 3)
        features = features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        return features

    def _get_model(self) -> Tuple[Any, Callable[..., Any]]:
        config = (self.model_name, self.checkpoint)
        with self._model_load_lock:
            if self.is_loaded and self._loaded_model_config != config:
                raise ValueError("loaded OpenCLIP model does not match the configured model/checkpoint")
            if not self.is_loaded:
                self._resolved_device = resolve_device(self.requested_device)
                if self.model_factory:
                    self._model, self._preprocess = self.model_factory(self.model_name, self.checkpoint, self._resolved_device)
                else:
                    self._model, self._preprocess = _load_open_clip(self.model_name, self.checkpoint, self._resolved_device)
                self._loaded_model_config = config
        return self._model, self._preprocess

    def _get_tokenizer(self) -> Any:
        if self._tokenizer is not None and self._tokenizer_model_name != self.model_name:
            raise ValueError("loaded OpenCLIP tokenizer does not match the configured model")
        if self._tokenizer is None:
            if self.tokenizer_factory is not None:
                self._tokenizer = self.tokenizer_factory(self.model_name)
            else:
                import open_clip
                self._tokenizer = open_clip.get_tokenizer(self.model_name)
            self._tokenizer_model_name = self.model_name
        return self._tokenizer

    def _encode_text_features(self, model: Any, tokens: Any, torch: Any) -> Any:
        if hasattr(model, "eval"):
            model.eval()
        try:
            tokens = tokens.to(self._resolved_device)
            with torch.no_grad():
                features = model.encode_text(tokens, normalize=True)
        except RuntimeError:
            if self._resolved_device != "mps":
                raise
            self._resolved_device = "cpu"
            if hasattr(model, "to"):
                model = model.to("cpu")
            with torch.no_grad():
                features = model.encode_text(tokens.to("cpu"), normalize=True)
        return features

    def _text_failure(
        self,
        text: str,
        code: str,
        message: str,
        language: Optional[str],
        *,
        text_status: Optional[str] = None,
    ) -> TextEncodingResult:
        metadata = {
            "device": self._resolved_device,
            "requested_device": self.requested_device,
            "checkpoint": self.checkpoint,
        }
        if text_status is not None:
            metadata["text_status"] = text_status
        return TextEncodingResult(
            model_name=self.model_name,
            language=language,
            status=TextEncodingStatus.UNAVAILABLE,
            error_code=code,
            error_message=message,
            processing_metadata=metadata,
        )

    def _success(self, image: ImagePreprocessingResult, embedding: List[float]) -> ImageEncodingResult:
        norm = math.sqrt(sum(value * value for value in embedding))
        if not embedding or not all(np.isfinite(embedding)) or not math.isfinite(norm) or norm <= 1e-12:
            return self._failure(image, "INVALID_EMBEDDING", "Image embedding was empty, non-finite, or zero-norm.")
        return ImageEncodingResult.available(
            request_id=image.request_id,
            model_name=self.model_name,
            checkpoint=self.checkpoint,
            embedding_dimension=len(embedding),
            embedding=embedding,
            image_path=image.processed_image_path,
            normalized=True,
            processing_metadata={
                "device": self._resolved_device,
                "requested_device": self.requested_device,
                "normalized_embedding": True,
                "deterministic_inference": True,
                "batch_size": self.batch_size,
                "image_width": image.width,
                "image_height": image.height,
                "image_preprocessing": {
                    "factory": "open_clip.create_model_and_transforms",
                    "architecture": self.model_name,
                    "checkpoint": self.checkpoint,
                    "color_mode": "RGB",
                    "transform": repr(self._preprocess),
                },
                "open_clip_version": _distribution_version("open_clip_torch"),
                "torch_version": _load_torch().__version__,
                "inference_time_ms": getattr(self, "_last_inference_time_ms", None),
            },
        )

    def _failure(self, image: Optional[ImagePreprocessingResult], code: str, message: str) -> ImageEncodingResult:
        return self._failure_for(image.request_id if image else uuid4(), image.processed_image_path if image else None, code, message)

    def _failure_for(self, request_id: UUID, image_path: Optional[str], code: str, message: str) -> ImageEncodingResult:
        return ImageEncodingResult.unavailable(
            request_id=request_id,
            model_name=self.model_name,
            checkpoint=self.checkpoint,
            image_path=image_path,
            errors=[ImageEncodingIssue(code=code, message=message)],
            processing_metadata={"device": self._resolved_device, "requested_device": self.requested_device},
        )


def _load_open_clip(model_name: str, checkpoint: str, device: str) -> Tuple[Any, Callable[..., Any]]:
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=checkpoint, device=device)
    return model, preprocess


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _load_torch() -> Any:
    import torch
    return torch
