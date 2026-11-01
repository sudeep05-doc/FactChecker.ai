from pathlib import Path

import pytest
import torch
from PIL import Image

from app.config.settings import Settings
from app.models import ImageEncodingStatus, OpenCLIPImageEncoder
from app.preprocessing import ImagePreprocessor
from tests.test_image_preprocessing import make_image_result


def test_openclip_encoder_is_lazy_and_returns_embedding(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (32, 24), color=(20, 40, 60)).save(image_path)
    image_result = ImagePreprocessor().process(make_image_result(image_path))

    load_count = 0

    def factory(model_name: str, checkpoint: str, device: str):
        nonlocal load_count
        load_count += 1

        class FakeModel:
            def eval(self):
                return self

            def encode_image(self, tensor):
                return torch.tensor([[3.0, 4.0, 0.0, 0.0]], device=tensor.device)

        def preprocess(image):
            return torch.zeros((3, 8, 8), dtype=torch.float32)

        return FakeModel(), preprocess

    encoder = OpenCLIPImageEncoder(
        settings=Settings(
            image_encoder_model="ViT-B-32",
            image_encoder_checkpoint="openai",
            image_encoder_device="cpu",
        ),
        model_factory=factory,
    )

    assert encoder.is_loaded is False
    result = encoder.encode(image_result)

    assert encoder.is_loaded is True
    assert load_count == 1
    assert result.encoding_status == ImageEncodingStatus.COMPLETED
    assert result.embedding_dimension == 4
    assert result.embedding == pytest.approx([0.6, 0.8, 0.0, 0.0])
    assert result.processing_metadata["device"] == "cpu"
    assert result.processing_metadata["normalized_embedding"] is True


def test_invalid_preprocessed_image_does_not_load_model() -> None:
    image_result = ImagePreprocessor().process(
        make_image_result(Path("/does/not/exist.png"))
    )
    encoder = OpenCLIPImageEncoder(
        settings=Settings(image_encoder_device="cpu"),
        model_factory=lambda *args: (_ for _ in ()).throw(
            AssertionError("model should not load")
        ),
    )

    result = encoder.encode(image_result)

    assert result.encoding_status == ImageEncodingStatus.FAILED
    assert result.errors[0].code == "IMAGE_PREPROCESSING_FAILED"