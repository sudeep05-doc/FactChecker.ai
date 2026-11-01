import pytest

from app.config.settings import Settings
from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.models import SentenceTransformerTextEncoder, TextEncodingStatus
from app.rr import build_reasoning_representation
from app.usr import UnifiedSemanticRepresentationBuilder


class FakeSentenceTransformer:
    def __init__(self, model_name: str, device: str) -> None:
        self.model_name = model_name
        self.device = device
        self.eval_called = False

    def eval(self) -> None:
        self.eval_called = True

    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["show_progress_bar"] is False
        return [[float(index + 1), 0.0, 0.0, 0.0] for index in range(len(texts))]


def test_encoder_is_lazy_and_returns_structured_embedding() -> None:
    instances = []

    def factory(model_name: str, device: str):
        instance = FakeSentenceTransformer(model_name, device)
        instances.append(instance)
        return instance

    encoder = SentenceTransformerTextEncoder(
        settings=Settings(
            text_encoder_model="test-model",
            text_encoder_device="cpu",
        ),
        model_factory=factory,
    )

    assert encoder.is_loaded is False
    result = encoder.encode("A cleaned claim.", language="en")

    assert encoder.is_loaded is True
    assert len(instances) == 1
    assert result.model_name == "test-model"
    assert result.embedding_dimension == 4
    assert result.embedding == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert result.language == "en"
    assert result.processing_metadata["device"] == "cpu"
    assert result.processing_metadata["deterministic_inference"] is True
    assert result.processing_metadata["device"] == "cpu"
    assert result.normalized is True


def test_encoder_reuses_lazy_model() -> None:
    load_count = 0

    def factory(model_name: str, device: str):
        nonlocal load_count
        load_count += 1
        return FakeSentenceTransformer(model_name, device)

    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu"),
        model_factory=factory,
    )
    encoder.encode("A cleaned claim.")
    encoder.encode("A cleaned claim.")

    assert load_count == 1


def test_empty_text_is_unavailable_before_model_load() -> None:
    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu"),
        model_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("model should not load")
        ),
    )

    result = encoder.encode("   ")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_EMPTY"
    assert encoder.is_loaded is False


def test_whitespace_only_text_is_unavailable() -> None:
    result = SentenceTransformerTextEncoder(settings=Settings(text_encoder_device="cpu")).encode("\n\t")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_EMPTY"


def test_batch_encoding_returns_one_structured_result_per_input() -> None:
    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu", text_encoder_batch_size=2),
        model_factory=lambda *args, **kwargs: FakeSentenceTransformer(*args, **kwargs),
    )

    results = encoder.encode_batch(["one", "two"])

    assert len(results) == 2
    assert all(result.status == TextEncodingStatus.AVAILABLE for result in results)
    assert all(result.embedding_dimension == 4 for result in results)
    assert results[0].processing_metadata["batch_size"] == 2


def test_invalid_non_finite_model_output_is_unavailable() -> None:
    class InvalidModel(FakeSentenceTransformer):
        def encode(self, texts, **kwargs):
            return [[float("nan"), 0.0]]

    result = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu"),
        model_factory=lambda *args, **kwargs: InvalidModel(*args, **kwargs),
    ).encode("claim")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_ENCODING_UNAVAILABLE"
    assert result.embedding is None


def test_model_unavailable_is_structured_without_fabricated_embedding() -> None:
    result = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu"),
        model_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("model files are unavailable")
        ),
    ).encode("claim")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_ENCODING_UNAVAILABLE"
    assert result.embedding is None


def test_long_text_is_chunked_in_order_and_aggregated() -> None:
    calls = []

    class ChunkModel(FakeSentenceTransformer):
        def encode(self, texts, **kwargs):
            calls.append(list(texts))
            return [[1.0, 0.0] for _ in texts]

    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu", text_encoder_chunk_size=4),
        model_factory=lambda *args, **kwargs: ChunkModel(*args, **kwargs),
    )
    result = encoder.encode("abcdefghij")

    assert result.status == TextEncodingStatus.AVAILABLE
    assert result.processing_metadata["chunk_count"] == 3
    assert result.processing_metadata["chunking_strategy"] == "ordered_character_chunks_mean_normalized"
    assert calls == [["abcd", "efgh", "ij"]]


def test_usr_conversion_preserves_embedding_and_processing_metadata() -> None:
    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_model="test-model", text_encoder_device="cpu"),
        model_factory=lambda *args, **kwargs: FakeSentenceTransformer(*args, **kwargs),
    )

    representation = encoder.to_usr_text("A cleaned claim.", language="en")

    assert representation is not None
    assert representation.embedding.model_name == "test-model"
    assert representation.embedding.normalized is True
    assert representation.metadata["modality"] == "text"
    assert representation.metadata["processing"]["device"] == "cpu"


def test_empty_usr_conversion_returns_none() -> None:
    encoder = SentenceTransformerTextEncoder(settings=Settings(text_encoder_device="cpu"))

    assert encoder.to_usr_text("   ") is None


def test_text_only_usr_representation_remains_cmref_compatible() -> None:
    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu"),
        model_factory=lambda *args, **kwargs: FakeSentenceTransformer(*args, **kwargs),
    )
    representation = encoder.to_usr_text("A cleaned claim.", language="en")
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023",
        text=representation,
    )

    rr = build_reasoning_representation(CMREF(ProjectionRegistry(4)).reason(usr))

    assert rr.available_modalities == ["text"]
    assert rr.consistency.alignment is None
    assert rr.contradiction is None