from uuid import uuid4

import pytest

from app.usr import (
    USRAudioTranscript,
    USREmbedding,
    USRImage,
    USRModality,
    USROCR,
    USRText,
    USRVideo,
    UnifiedSemanticRepresentation,
    UnifiedSemanticRepresentationBuilder,
)


REQUEST_ID = uuid4()


def embedding(name: str = "test-model", values=None) -> USREmbedding:
    values = values or [0.1, 0.2, 0.3]
    return USREmbedding(model_name=name, dimension=len(values), values=values)


def test_text_only_usr() -> None:
    result = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="A cleaned claim.", language="en", embedding=embedding()),
    )

    assert result.available_modalities == [USRModality.TEXT]
    assert result.text.embedding.dimension == 3


def test_image_only_usr() -> None:
    result = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        image=USRImage(image_paths=["/tmp/image.png"], embedding=embedding("clip")),
    )

    assert result.available_modalities == [USRModality.IMAGE]
    assert result.image.image_paths == ["/tmp/image.png"]


def test_text_and_image_usr() -> None:
    result = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="Claim", embedding=embedding()),
        image=USRImage(embedding=embedding("clip")),
    )

    assert set(result.available_modalities) == {USRModality.TEXT, USRModality.IMAGE}


def test_audio_only_usr() -> None:
    result = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        audio=USRAudioTranscript(
            transcript="Spoken claim.",
            language="en",
            segments=[{"start_seconds": 0.0, "end_seconds": 1.0, "text": "Spoken claim."}],
        ),
    )

    assert result.available_modalities == [USRModality.AUDIO_TRANSCRIPT]
    assert result.audio.transcript == "Spoken claim."


def test_multimodal_usr() -> None:
    result = UnifiedSemanticRepresentationBuilder().build(
        REQUEST_ID,
        text=USRText(text="Claim"),
        image=USRImage(image_paths=["image.png"]),
        ocr=USROCR(extracted_text="Claim text", ocr_confidence=0.9),
        audio=USRAudioTranscript(transcript="Spoken claim"),
        video=USRVideo(
            transcript="Video speech",
            frame_paths=["frame-1.jpg", "frame-2.jpg"],
        ),
        modality_metadata={"source": "test"},
        preprocessing_metadata={"image": {"width": 224}},
    )

    assert set(result.available_modalities) == {
        USRModality.TEXT,
        USRModality.IMAGE,
        USRModality.OCR,
        USRModality.AUDIO_TRANSCRIPT,
        USRModality.VIDEO_TRANSCRIPT,
        USRModality.VIDEO_FRAMES,
    }


def test_empty_usr_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        UnifiedSemanticRepresentationBuilder().build(REQUEST_ID)


def test_embedding_dimension_and_finite_values_are_validated() -> None:
    with pytest.raises(ValueError, match="dimension"):
        USREmbedding(model_name="bad", dimension=2, values=[0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="finite"):
        USREmbedding(model_name="bad", dimension=1, values=[float("nan")])


def test_available_modalities_must_match_representations() -> None:
    with pytest.raises(ValueError, match="available_modalities"):
        UnifiedSemanticRepresentation(
            request_id=REQUEST_ID,
            available_modalities=[USRModality.TEXT],
            image=USRImage(image_paths=["image.png"]),
        )