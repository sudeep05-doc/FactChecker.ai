"""Lazy SentenceTransformer text encoding with validated USR-compatible output."""

import time
from typing import Any, Callable, Iterable, List, Optional

import numpy as np

from app.config.settings import Settings, get_settings
from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus
from app.usr.models import USREmbedding, USRText


DEFAULT_TEXT_ENCODER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerTextEncoder:
    """Reuse one lazily loaded SentenceTransformer per encoder instance."""

    def __init__(self, settings: Optional[Settings] = None, model_factory: Optional[Callable[..., Any]] = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.text_encoder_model
        self.requested_device = self.settings.text_encoder_device
        self.batch_size = self.settings.text_encoder_batch_size
        self.chunk_size = self.settings.text_encoder_chunk_size
        self.model_factory = model_factory
        self._model: Optional[Any] = None
        self._resolved_device: Optional[str] = None
        if self.batch_size < 1:
            raise ValueError("text_encoder_batch_size must be positive")
        if self.chunk_size < 1:
            raise ValueError("text_encoder_chunk_size must be positive")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def resolved_device(self) -> Optional[str]:
        return self._resolved_device

    def encode(self, cleaned_text: str, language: Optional[str] = None) -> TextEncodingResult:
        if not cleaned_text or not cleaned_text.strip():
            return self._unavailable("TEXT_EMPTY", "Text is empty or whitespace-only.", language)
        chunks = _chunk_text(cleaned_text, self.chunk_size)
        results = self.encode_batch(chunks, language=language)
        return self._aggregate_chunk_results(cleaned_text, chunks, results, language)

    def encode_batch_with_chunking(
        self,
        texts: Iterable[str],
        language: Optional[str] = None,
    ) -> List[TextEncodingResult]:
        values = list(texts)
        results: List[Optional[TextEncodingResult]] = [None] * len(values)
        short_indices = []
        for index, text in enumerate(values):
            if not text or not text.strip():
                results[index] = self._unavailable("TEXT_EMPTY", "Text is empty or whitespace-only.", language)
            elif len(text) > self.chunk_size:
                results[index] = self.encode(text, language=language)
            else:
                short_indices.append(index)

        if short_indices:
            encoded = self.encode_batch((values[index] for index in short_indices), language=language)
            if len(encoded) != len(short_indices):
                fallback = encoded[0] if encoded else self._unavailable(
                    "TEXT_ENCODING_UNAVAILABLE",
                    "No encoding result returned for the batch.",
                    language,
                )
                encoded = [
                    self._unavailable(
                        fallback.error_code or "TEXT_ENCODING_UNAVAILABLE",
                        fallback.error_message or "The encoder returned an invalid batch result count.",
                        language,
                    )
                    for _ in short_indices
                ]
            for index, result in zip(short_indices, encoded):
                results[index] = self._aggregate_chunk_results(values[index], [values[index]], [result], language)

        return [result for result in results if result is not None]

    def _aggregate_chunk_results(
        self,
        cleaned_text: str,
        chunks: List[str],
        results: List[TextEncodingResult],
        language: Optional[str],
    ) -> TextEncodingResult:
        if not results or any(result.status != TextEncodingStatus.AVAILABLE for result in results):
            return next(
                (result for result in results if result.status != TextEncodingStatus.AVAILABLE),
                None,
            ) or self._unavailable("TEXT_ENCODING_UNAVAILABLE", "No encoding result returned.", language)
        vectors = np.asarray([result.embedding for result in results], dtype=np.float32)
        aggregate = vectors.mean(axis=0)
        norm = float(np.linalg.norm(aggregate))
        if not np.isfinite(norm) or norm == 0:
            return self._unavailable("TEXT_ENCODING_INVALID", "Aggregated embedding has an invalid norm.", language)
        aggregate = (aggregate / norm).tolist()
        result = TextEncodingResult(
            model_name=self.model_name,
            embedding_dimension=len(aggregate),
            embedding=aggregate,
            language=language,
            normalized=True,
            processing_metadata=dict(results[0].processing_metadata),
        )
        result.processing_metadata.update({
            "chunk_count": len(chunks),
            "chunking_strategy": "ordered_character_chunks_mean_normalized",
            "input_character_count": len(cleaned_text),
        })
        return result

    def encode_batch(self, texts: Iterable[str], language: Optional[str] = None) -> List[TextEncodingResult]:
        values = list(texts)
        if not values or any(not text or not text.strip() for text in values):
            return [self._unavailable("TEXT_EMPTY", "Batch contains empty or whitespace-only text.", language)]
        try:
            model = self._get_model()
            started_at = time.perf_counter()
            if hasattr(model, "eval"):
                model.eval()
            vectors = model.encode(
                values,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            array = np.asarray(vectors, dtype=np.float32)
            if array.ndim == 1:
                array = array.reshape(1, -1)
            if array.ndim != 2 or array.shape[0] != len(values):
                raise ValueError("encoder returned an invalid batch shape")
            if array.shape[1] < 1 or not np.isfinite(array).all():
                raise ValueError("encoder returned a non-finite or empty embedding")
            metadata = {
                    "device": self._resolved_device,
                    "requested_device": self.requested_device,
                    "normalized_embeddings": True,
                    "deterministic_inference": True,
                    "batch_size": self.batch_size,
                    "encoded_text_count": len(values),
                    "inference_time_ms": round((time.perf_counter() - started_at) * 1000, 3),
            }
            return [
                TextEncodingResult(
                    model_name=self.model_name,
                    embedding_dimension=array.shape[1],
                    embedding=row.tolist(),
                    language=language,
                    normalized=True,
                    processing_metadata=metadata,
                )
                for row in array
            ]
        except Exception as error:
            return [self._unavailable("TEXT_ENCODING_UNAVAILABLE", str(error), language)]

    def to_usr_text(self, cleaned_text: str, language: Optional[str] = None) -> Optional[USRText]:
        return self.to_usr_text_from_result(cleaned_text, self.encode(cleaned_text, language=language))

    def to_usr_text_from_result(
        self,
        cleaned_text: str,
        result: TextEncodingResult,
    ) -> Optional[USRText]:
        if result.status != TextEncodingStatus.AVAILABLE:
            return None
        return USRText(
            text=cleaned_text,
            language=result.language,
            embedding=USREmbedding(
                model_name=result.model_name,
                dimension=result.embedding_dimension,
                values=result.embedding,
                normalized=result.normalized,
            ),
            metadata={"processing": result.processing_metadata, "modality": result.modality},
        )

    def _unavailable(self, code: str, message: str, language: Optional[str]) -> TextEncodingResult:
        return TextEncodingResult(
            model_name=self.model_name,
            language=language,
            status=TextEncodingStatus.UNAVAILABLE,
            error_code=code,
            error_message=message,
            processing_metadata={"device": self._resolved_device, "requested_device": self.requested_device},
        )

    def _get_model(self) -> Any:
        if self._model is None:
            self._resolved_device = resolve_device(self.requested_device)
            factory = self.model_factory or _load_sentence_transformer_class()
            self._model = factory(self.model_name, device=self._resolved_device)
        return self._model


def _chunk_text(text: str, chunk_size: int) -> List[str]:
    """Split in stable character order without silently discarding content."""

    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]


def resolve_device(requested_device: str) -> str:
    """Resolve auto/MPS requests while retaining a CPU fallback."""

    normalized = requested_device.strip().lower()
    if normalized == "cpu":
        return "cpu"
    try:
        import torch
        mps_available = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    except ImportError:
        mps_available = False
    if normalized == "mps":
        return "mps" if mps_available else "cpu"
    if normalized == "auto":
        return "mps" if mps_available else "cpu"
    raise ValueError(f"Unsupported text encoder device: {requested_device}")


def _load_sentence_transformer_class() -> Callable[..., Any]:
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer
