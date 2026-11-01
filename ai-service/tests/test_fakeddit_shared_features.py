from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

import pytest
import torch
from PIL import Image
from pydantic import ValidationError
from open_clip import get_model_config
from open_clip.pretrained import get_pretrained_cfg

from app.config.settings import Settings
from app.decision.features_v2 import (
    FEATURE_SCHEMA_VERSION,
    OPENCLIP_CHECKPOINT,
    OPENCLIP_DIMENSION,
    OPENCLIP_MODEL,
    ModalityStatus,
    RRDecisionV2Features,
)
from app.evaluation.fakeddit_shared_features import build_shared_space_feature_artifact
from app.models import OpenCLIPImageEncoder, TextEncodingStatus


class FakeTokenizer:
    context_length = 5
    sot_token_id = 1
    eot_token_id = 2

    def encode(self, text):
        return [10, 11, 12, 13, 14]


class FakeSharedModel:
    def __init__(self, text_vector=None, image_vector=None):
        default_vector = [0.0, 1.0] + [0.0] * (OPENCLIP_DIMENSION - 2)
        self.text_vector = text_vector if text_vector is not None else default_vector
        self.image_vector = image_vector if image_vector is not None else default_vector
        self.image_calls = 0
        self.text_calls = 0
        self.text_tokens = None
        self.text_normalize_arguments = []

    def eval(self):
        return self

    def encode_text(self, tokens, normalize=False):
        self.text_calls += 1
        self.text_normalize_arguments.append(normalize)
        self.text_tokens = tokens.detach().cpu().tolist()
        return torch.tensor([self.text_vector for _ in range(tokens.shape[0])], device=tokens.device)

    def encode_image(self, tensors):
        self.image_calls += 1
        return torch.tensor([self.image_vector for _ in range(tensors.shape[0])], device=tensors.device)


class FakePreprocess:
    def __call__(self, image):
        return torch.ones((3, 8, 8), dtype=torch.float32)


def make_encoder(model=None):
    model = model or FakeSharedModel()
    loads = []
    tokenizer_loads = []

    def model_factory(model_name, checkpoint, device):
        loads.append((model_name, checkpoint, device))
        return model, FakePreprocess()

    def tokenizer_factory(model_name):
        tokenizer_loads.append(model_name)
        return FakeTokenizer()

    encoder = OpenCLIPImageEncoder(
        settings=Settings(
            image_encoder_model=OPENCLIP_MODEL,
            image_encoder_checkpoint=OPENCLIP_CHECKPOINT,
            image_encoder_device="cpu",
            image_encoder_batch_size=2,
        ),
        model_factory=model_factory,
        tokenizer_factory=tokenizer_factory,
    )
    return encoder, model, loads, tokenizer_loads


def make_sample(tmp_path: Path, **changes):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (12, 9), color=(20, 40, 60)).save(image_path)
    sample = {
        "sample_id": "sample-1",
        "split": "test",
        "label": "REAL",
        "source_reference": "source-1",
        "text": "A test claim.",
        "metadata": {"local_image_path": str(image_path)},
    }
    sample.update(changes)
    return sample, image_path


def test_v2_openclip_configuration_matches_official_checkpoint_activation():
    model_config = get_model_config(OPENCLIP_MODEL)
    pretrained_config = get_pretrained_cfg(OPENCLIP_MODEL, OPENCLIP_CHECKPOINT)
    legacy_config = get_model_config("ViT-B-32")
    legacy_pretrained_config = get_pretrained_cfg("ViT-B-32", OPENCLIP_CHECKPOINT)

    assert model_config["quick_gelu"] is True
    assert pretrained_config["quick_gelu"] is True
    assert model_config["embed_dim"] == OPENCLIP_DIMENSION
    assert pretrained_config["url"] == legacy_pretrained_config["url"]
    assert OPENCLIP_MODEL == "ViT-B-32-quickgelu"


def test_text_and_image_share_one_clip_model_and_truncate_explicitly(tmp_path: Path):
    encoder, model, loads, tokenizer_loads = make_encoder()
    sample, _ = make_sample(tmp_path)

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert loads == [(OPENCLIP_MODEL, OPENCLIP_CHECKPOINT, "cpu")]
    assert tokenizer_loads == [OPENCLIP_MODEL]
    assert model.text_calls == model.image_calls == 1
    assert model.text_normalize_arguments == [True]
    assert model.text_tokens == [[1, 10, 11, 12, 2]]
    assert artifact["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert set(artifact["predictor_features"]) == {
        "clip_text_embedding",
        "clip_image_embedding",
        "clip_text_image_cosine",
    }
    assert artifact["predictor_features"]["clip_text_image_cosine"] == pytest.approx(1.0)
    assert artifact["modality_provenance"]["text"]["processing"]["truncation_applied"] is True
    assert artifact["modality_provenance"]["text"]["weights_verified"] is False
    rr = artifact["reasoning_representation"]
    assert rr["pairwise_alignments"] == []
    assert rr["pairwise_similarities"][0]["cosine_similarity"] == pytest.approx(1.0)
    assert rr["consistency"]["alignment"] is None
    assert rr["consistency"]["score"] is None
    assert rr["consistency"]["contextual"] is None
    assert rr["consistency"]["status"] == "unavailable"
    assert rr["consistency"]["unavailable_reason"] == "CONSISTENCY_EVALUATOR_UNAVAILABLE"


def test_empty_text_and_missing_image_are_null_with_explicit_status(tmp_path: Path):
    encoder, _, _, _ = make_encoder()
    sample, _ = make_sample(tmp_path, text=" ", metadata={})

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert artifact["predictor_features"]["clip_text_embedding"] is None
    assert artifact["predictor_features"]["clip_image_embedding"] is None
    assert artifact["predictor_features"]["clip_text_image_cosine"] is None
    assert artifact["modality_status"] == {
        "text": ModalityStatus.INPUT_ABSENT.value,
        "image": ModalityStatus.INPUT_ABSENT.value,
    }
    assert artifact["reasoning_representation"] is None


def test_failed_text_inference_preserves_available_image_only(tmp_path: Path):
    model = FakeSharedModel(text_vector=[float("nan")] + [0.0] * (OPENCLIP_DIMENSION - 1))
    encoder, _, _, _ = make_encoder(model)
    sample, _ = make_sample(tmp_path)

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert artifact["modality_status"]["text"] == ModalityStatus.UNAVAILABLE.value
    assert artifact["modality_status"]["image"] == ModalityStatus.AVAILABLE.value
    assert artifact["predictor_features"]["clip_text_embedding"] is None
    assert artifact["predictor_features"]["clip_image_embedding"] is not None
    assert artifact["predictor_features"]["clip_text_image_cosine"] is None
    assert artifact["modality_provenance"]["text"]["error_code"] == "INVALID_TEXT_EMBEDDING"
    assert artifact["reasoning_representation"]["pairwise_similarities"] == []


def test_zero_norm_image_embedding_is_unavailable(tmp_path: Path):
    model = FakeSharedModel(image_vector=[0.0] * OPENCLIP_DIMENSION)
    encoder, _, _, _ = make_encoder(model)
    sample, _ = make_sample(tmp_path)

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert artifact["modality_status"]["image"] == ModalityStatus.UNAVAILABLE.value
    assert artifact["predictor_features"]["clip_image_embedding"] is None
    assert artifact["modality_provenance"]["image"]["error_code"] == "INVALID_EMBEDDING"


def test_encoder_text_batch_reports_empty_and_available_statuses():
    encoder, _, _, _ = make_encoder()

    empty, available = encoder.encode_text_batch(["  ", "claim"])

    assert empty.status == TextEncodingStatus.UNAVAILABLE
    assert empty.error_code == "TEXT_EMPTY"
    assert available.status == TextEncodingStatus.AVAILABLE
    assert available.normalized is True
    assert available.embedding_dimension == OPENCLIP_DIMENSION


def test_empty_input_status_does_not_depend_on_tokenizer_availability():
    encoder, _, _, _ = make_encoder()
    encoder.tokenizer_factory = lambda model_name: (_ for _ in ()).throw(RuntimeError("tokenizer missing"))

    empty, unavailable = encoder.encode_text_batch(["  ", "claim"])

    assert empty.error_code == "TEXT_EMPTY"
    assert empty.processing_metadata["text_status"] == "input_absent"
    assert unavailable.error_code == "TEXT_TOKENIZER_UNAVAILABLE"


def test_corrupt_image_is_unavailable_with_an_error_code(tmp_path: Path):
    encoder, _, _, _ = make_encoder()
    sample, image_path = make_sample(tmp_path)
    image_path.write_bytes(b"invalid image")

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert artifact["modality_status"]["text"] == ModalityStatus.AVAILABLE.value
    assert artifact["modality_status"]["image"] == ModalityStatus.UNAVAILABLE.value
    assert artifact["predictor_features"]["clip_image_embedding"] is None
    assert artifact["modality_provenance"]["image"]["error_code"] == "INVALID_IMAGE"


def test_missing_image_path_is_unavailable_not_input_absent(tmp_path: Path):
    encoder, _, _, _ = make_encoder()
    sample = {
        "sample_id": "missing-image",
        "text": "A test claim.",
        "metadata": {"local_image_path": "images/not-found.png"},
    }

    artifact = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)

    assert artifact["modality_status"]["image"] == ModalityStatus.UNAVAILABLE.value
    assert artifact["modality_provenance"]["image"]["error_code"] == "IMAGE_NOT_FOUND"


def test_v2_schema_rejects_dimension_norm_and_cosine_mismatches():
    vector = [0.0, 1.0] + [0.0] * (OPENCLIP_DIMENSION - 2)
    provenance = {
        "status": "available",
        "model_name": OPENCLIP_MODEL,
        "checkpoint": OPENCLIP_CHECKPOINT,
        "dimension": OPENCLIP_DIMENSION,
        "weights_verified": False,
        "shared_model_instance": True,
    }
    valid = {
        "clip_text_embedding": vector,
        "clip_image_embedding": vector,
        "clip_text_image_cosine": 1.0,
        "text_status": "available",
        "image_status": "available",
        "text_provenance": provenance,
        "image_provenance": provenance,
    }
    assert RRDecisionV2Features(**valid).predictor_features["clip_text_image_cosine"] == 1.0

    with pytest.raises(ValidationError):
        RRDecisionV2Features(**{**valid, "clip_text_embedding": vector[:-1]})
    with pytest.raises(ValidationError):
        RRDecisionV2Features(**{**valid, "clip_text_embedding": [0.0] * OPENCLIP_DIMENSION})
    with pytest.raises(ValidationError):
        RRDecisionV2Features(**{**valid, "clip_text_embedding": [float("nan")] + vector[1:]})
    with pytest.raises(ValidationError):
        RRDecisionV2Features(**{**valid, "clip_text_image_cosine": 0.5})
    with pytest.raises(ValidationError):
        RRDecisionV2Features(**{**valid, "label": "REAL"})


def test_feature_values_are_invariant_to_label_and_non_predictor_metadata(tmp_path: Path):
    encoder, _, _, _ = make_encoder()
    sample, _ = make_sample(tmp_path)
    changed_metadata = {
        **sample,
        "sample_id": "different-id",
        "label": "FAKE",
        "split": "train",
        "source_reference": "other-source",
        "metadata": {
            **sample["metadata"],
            "group_id": "unrelated-group",
            "url": "https://example.invalid/other",
        },
    }

    original = build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)
    changed = build_shared_space_feature_artifact(changed_metadata, data_dir=tmp_path, encoder=encoder)

    assert original["predictor_features"] == changed["predictor_features"]
    assert "label" not in original["predictor_features"]
    assert "sample_id" not in original["predictor_features"]


def test_model_checkpoint_mismatch_is_rejected(tmp_path: Path):
    encoder, _, _, _ = make_encoder()
    encoder.checkpoint = "different"
    sample, _ = make_sample(tmp_path)

    with pytest.raises(ValueError, match="requires ViT-B-32-quickgelu"):
        build_shared_space_feature_artifact(sample, data_dir=tmp_path, encoder=encoder)


def test_loaded_encoder_rejects_checkpoint_reconfiguration():
    encoder, _, _, _ = make_encoder()
    assert encoder.encode_text("claim").status == TextEncodingStatus.AVAILABLE

    encoder.checkpoint = "different"
    result = encoder.encode_text("claim")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_ENCODING_FAILED"
    assert "does not match" in result.error_message


def test_concurrent_first_calls_load_one_shared_model():
    encoder, _, loads, _ = make_encoder()
    original_factory = encoder.model_factory

    def slow_factory(*args):
        time.sleep(0.05)
        return original_factory(*args)

    encoder.model_factory = slow_factory
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(encoder.encode_text, ["claim"] * 4))

    assert all(result.status == TextEncodingStatus.AVAILABLE for result in results)
    assert loads == [(OPENCLIP_MODEL, OPENCLIP_CHECKPOINT, "cpu")]
