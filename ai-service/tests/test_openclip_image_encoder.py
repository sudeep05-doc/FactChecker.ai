from pathlib import Path

import pytest
import torch
from PIL import Image

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.config.settings import Settings
from app.models import ImageEncodingStatus, OpenCLIPImageEncoder
from app.preprocessing import ImagePreprocessor
from app.rr import build_reasoning_representation
from app.usr import USRText, UnifiedSemanticRepresentationBuilder, USREmbedding
from tests.test_image_preprocessing import make_image_result


class FakeOpenCLIPModel:
    def __init__(self, values=(3.0, 4.0, 0.0, 0.0)):
        self.values = values
        self.calls = 0

    def eval(self):
        return self

    def encode_image(self, tensor):
        self.calls += 1
        return torch.tensor([self.values for _ in range(tensor.shape[0])], device=tensor.device)


def make_encoder(tmp_path: Path, model=None, batch_size=2):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (32, 24), color=(20, 40, 60)).save(image_path)
    image_result = ImagePreprocessor().process(make_image_result(image_path))
    model = model or FakeOpenCLIPModel()
    loads = []

    def factory(model_name, checkpoint, device):
        loads.append((model_name, checkpoint, device))

        def preprocess(image):
            return torch.ones((3, 8, 8), dtype=torch.float32)

        return model, preprocess

    encoder = OpenCLIPImageEncoder(
        settings=Settings(
            image_encoder_model="ViT-B-32",
            image_encoder_checkpoint="openai",
            image_encoder_device="cpu",
            image_encoder_batch_size=batch_size,
        ),
        model_factory=factory,
    )
    return encoder, image_result, image_path, loads, model


def test_valid_image_embedding_and_metadata(tmp_path: Path):
    encoder, image_result, _, loads, _ = make_encoder(tmp_path)

    result = encoder.encode(image_result)

    assert result.encoding_status == ImageEncodingStatus.COMPLETED
    assert result.modality == "image"
    assert result.embedding == pytest.approx([0.6, 0.8, 0.0, 0.0])
    assert result.embedding_dimension == 4
    assert result.model_name == "ViT-B-32"
    assert result.checkpoint == "openai"
    assert result.normalized is True
    assert result.processing_metadata["device"] == "cpu"
    assert loads == [("ViT-B-32", "openai", "cpu")]


def test_invalid_preprocessing_does_not_load_model(tmp_path: Path):
    encoder, _, _, loads, _ = make_encoder(tmp_path)
    invalid = ImagePreprocessor().process(make_image_result(Path("/missing.png")))

    result = encoder.encode(invalid)

    assert result.encoding_status == ImageEncodingStatus.FAILED
    assert result.errors[0].code == "IMAGE_PREPROCESSING_FAILED"
    assert loads == []


def test_missing_empty_and_corrupted_images_are_structured(tmp_path: Path):
    encoder, _, _, _, _ = make_encoder(tmp_path)

    missing = encoder.encode(tmp_path / "missing.png")
    empty = encoder.encode(b"")
    corrupted_path = tmp_path / "corrupt.png"
    corrupted_path.write_bytes(b"not-an-image")
    corrupted = encoder.encode(corrupted_path)

    assert missing.errors[0].code == "IMAGE_NOT_FOUND"
    assert empty.errors[0].code == "INVALID_IMAGE"
    assert corrupted.errors[0].code == "INVALID_IMAGE"
    assert all(result.embedding is None for result in (missing, empty, corrupted))


def test_invalid_non_finite_embedding_is_unavailable(tmp_path: Path):
    encoder, image_result, _, _, _ = make_encoder(tmp_path, model=FakeOpenCLIPModel((float("nan"), 0.0, 0.0, 0.0)))

    result = encoder.encode(image_result)

    assert result.encoding_status == ImageEncodingStatus.FAILED
    assert result.errors[0].code == "IMAGE_ENCODING_FAILED"
    assert result.embedding is None


def test_lazy_loading_and_model_reuse(tmp_path: Path):
    encoder, image_result, _, loads, model = make_encoder(tmp_path)

    assert encoder.is_loaded is False
    encoder.encode(image_result)
    encoder.encode(image_result)

    assert encoder.is_loaded is True
    assert len(loads) == 1
    assert model.calls == 2


def test_batch_encoding_preserves_order_and_invalid_slot(tmp_path: Path):
    encoder, image_result, image_path, _, _ = make_encoder(tmp_path)
    invalid = ImagePreprocessor().process(make_image_result(Path("/missing.png")))

    results = encoder.encode_batch([image_result, invalid, image_result])

    assert len(results) == 3
    assert results[0].encoding_status == ImageEncodingStatus.COMPLETED
    assert results[1].errors[0].code == "IMAGE_PREPROCESSING_FAILED"
    assert results[2].encoding_status == ImageEncodingStatus.COMPLETED
    assert results[0].image_path == results[2].image_path == str(image_path)


def test_model_unavailable_is_structured(tmp_path: Path):
    encoder, image_result, _, _, _ = make_encoder(tmp_path)
    encoder.model_factory = lambda *args: (_ for _ in ()).throw(RuntimeError("weights unavailable"))

    result = encoder.encode(image_result)

    assert result.encoding_status == ImageEncodingStatus.FAILED
    assert result.errors[0].code == "IMAGE_ENCODING_FAILED"
    assert result.embedding is None


def test_usr_conversion_preserves_model_checkpoint_and_processing_metadata(tmp_path: Path):
    encoder, image_result, _, _, _ = make_encoder(tmp_path)

    representation = encoder.to_usr_image(image_result)

    assert representation is not None
    assert representation.embedding.model_name == "ViT-B-32"
    assert representation.embedding.normalized is True
    assert representation.metadata["checkpoint"] == "openai"
    assert representation.metadata["modality"] == "image"
    assert representation.metadata["processing"]["device"] == "cpu"


def test_image_only_cmref_preserves_undefined_cross_modal_scores(tmp_path: Path):
    encoder, image_result, _, _, _ = make_encoder(tmp_path)
    image = encoder.to_usr_image(image_result)
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023", image=image
    )

    rr = build_reasoning_representation(CMREF(ProjectionRegistry(4)).reason(usr))

    assert rr.available_modalities == ["image"]
    assert rr.consistency.alignment is None
    assert rr.contradiction is None


def test_text_and_image_can_enter_usr_and_cmref_together(tmp_path: Path):
    encoder, image_result, _, _, _ = make_encoder(tmp_path)
    image = encoder.to_usr_image(image_result)
    text = USRText(
        text="A claim",
        embedding=USREmbedding(model_name="text", dimension=4, values=[1.0, 0.0, 0.0, 0.0]),
    )
    usr = UnifiedSemanticRepresentationBuilder().build(
        "00000000-0000-4000-8000-000000000023", text=text, image=image
    )

    rr = build_reasoning_representation(CMREF(ProjectionRegistry(4)).reason(usr))

    assert set(rr.available_modalities) == {"text", "image"}
    assert len(rr.pairwise_similarities) == 1


def test_image_input_as_bytes_is_supported(tmp_path: Path):
    encoder, _, _, _, _ = make_encoder(tmp_path)
    buffer = __import__("io").BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="PNG")

    result = encoder.encode(buffer.getvalue())

    assert result.encoding_status == ImageEncodingStatus.COMPLETED
    assert result.image_path is None
