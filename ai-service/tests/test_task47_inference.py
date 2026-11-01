import json
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.api.routes import task47_inference
from app.main import app
from app.pipeline.task47_inference import (
    EXPERIMENT_ROOT,
    EXPECTED_CHECKPOINT_SHA256,
    InferenceUnavailableError,
    InvalidInferenceInputError,
    Task47Inference,
)


client = TestClient(app)
RESEARCH_ROOT = Path(__file__).resolve().parents[1] / "data/research"
IMAGE_ROOT = RESEARCH_ROOT / "fakeddit/images"


def _minimal_text_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode())
        data.extend(item + b"\nendobj\n")
    xref_offset = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(data)


def test_saved_models_and_schema_pass_integrity_checks() -> None:
    config = json.loads((EXPERIMENT_ROOT / "configuration.json").read_text())
    inventory = json.loads((EXPERIMENT_ROOT / "sha256_inventory.json").read_text())
    classifier = Task47Inference()

    assert config["target"]["label_mapping"] == {"FAKE": 0, "REAL": 1}
    assert config["encoder"]["checkpoint_sha256"] == EXPECTED_CHECKPOINT_SHA256
    assert set(classifier.models) == {"text_only", "image_only"}
    assert all(model.n_features_in_ == 512 for model in classifier.models.values())
    assert all(np.array_equal(model.classes_, [0, 1]) for model in classifier.models.values())
    assert len(inventory["task36c_inputs"]) == 3


def test_empty_and_unsupported_inference_inputs_are_rejected() -> None:
    classifier = Task47Inference()

    try:
        classifier.predict_text("  ")
    except InvalidInferenceInputError:
        pass
    else:
        raise AssertionError("whitespace-only text was accepted")

    try:
        classifier.predict_image(b"bytes", "image/gif")
    except InvalidInferenceInputError:
        pass
    else:
        raise AssertionError("unsupported image MIME type was accepted")

    try:
        classifier.predict_pdf(b"")
    except InvalidInferenceInputError:
        pass
    else:
        raise AssertionError("empty PDF was accepted")


def test_real_text_image_and_pdf_inference() -> None:
    task47_inference._inference.cache_clear()
    text_response = client.post(
        "/api/v1/classify/text",
        json={"text": "A local example of a news report for classifier inference."},
    )
    assert text_response.status_code == 200, text_response.text
    text_result = text_response.json()
    assert text_result["status"] == "completed"
    assert text_result["is_mock"] is False
    assert text_result["model_id"].endswith("/text_only")
    assert text_result["feature_schema_version"] == "rr-decision-v2"
    assert text_result["prediction"] in {"FAKE", "REAL"}
    assert text_result["prediction_type"] == "dataset_classification"
    assert text_result["dataset_prediction"] == text_result["prediction"]
    assert text_result["dataset_identity"] == "Fakeddit 2-way distant-supervision label"
    assert text_result["model_identity"] == text_result["model_id"]
    assert text_result["confidence_semantics"] == "uncalibrated_dataset_score"
    assert text_result["evidence_status"] == "not_applicable"
    assert text_result["verdict"] is None
    assert set(text_result["class_scores"]) == {"FAKE", "REAL"}
    assert text_result["dataset_score"] == text_result["class_scores"][text_result["prediction"]]
    assert "not factual confidence" in text_result["score_semantics"]
    assert "confidence" not in text_result

    image_path = next(path for path in sorted(IMAGE_ROOT.iterdir()) if path.is_file())
    image_response = client.post(
        "/api/v1/classify/image",
        content=image_path.read_bytes(),
        headers={"content-type": "image/jpeg"},
    )
    assert image_response.status_code == 200, image_response.text
    assert image_response.json()["model_id"].endswith("/image_only")

    pdf_response = client.post(
        "/api/v1/classify/pdf",
        content=_minimal_text_pdf("A text based report extracted from a local PDF."),
        headers={"content-type": "application/pdf"},
    )
    assert pdf_response.status_code == 200, pdf_response.text
    pdf_result = pdf_response.json()
    assert pdf_result["model_id"].endswith("/text_only")
    assert pdf_result["input_type"] == "pdf"
    assert pdf_result["preprocessing"]["extracted_character_count"] > 0
    assert pdf_result["preprocessing"]["ocr"] == "not_supported"


def test_empty_pdf_and_wrong_mime_are_rejected() -> None:
    empty_response = client.post(
        "/api/v1/classify/pdf",
        content=b"",
        headers={"content-type": "application/pdf"},
    )
    assert empty_response.status_code == 422

    wrong_mime_response = client.post(
        "/api/v1/classify/image",
        content=b"not an image",
        headers={"content-type": "application/gif"},
    )
    assert wrong_mime_response.status_code == 415

    unreadable_image_response = client.post(
        "/api/v1/classify/image",
        content=b"not an encoded image",
        headers={"content-type": "image/jpeg"},
    )
    assert unreadable_image_response.status_code == 422

    corrupted_pdf_response = client.post(
        "/api/v1/classify/pdf",
        content=b"not a PDF document",
        headers={"content-type": "application/pdf"},
    )
    assert corrupted_pdf_response.status_code == 422

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    blank_pdf = BytesIO()
    writer.write(blank_pdf)
    no_text_pdf_response = client.post(
        "/api/v1/classify/pdf",
        content=blank_pdf.getvalue(),
        headers={"content-type": "application/pdf"},
    )
    assert no_text_pdf_response.status_code == 422
    assert "OCR" in no_text_pdf_response.json()["detail"]


def test_unavailable_model_returns_service_error(monkeypatch) -> None:
    task47_inference._inference.cache_clear()

    def unavailable():
        raise InferenceUnavailableError("test model unavailable")

    monkeypatch.setattr(task47_inference, "_inference", unavailable)
    response = client.post(
        "/api/v1/classify/text",
        json={"text": "This request must not receive a fallback prediction."},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "test model unavailable"
