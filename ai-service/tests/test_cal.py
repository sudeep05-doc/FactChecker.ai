from pathlib import Path
from uuid import uuid4

from app.cal import AcquisitionStatus, CALResult, ContentAcquisitionService
from app.schemas.verification import InputType, VerificationRequest


def test_text_acquisition_normalizes_content() -> None:
    request = VerificationRequest(
        request_id=uuid4(),
        input_type=InputType.TEXT,
        content={"text": "A claim submitted for acquisition."},
    )

    result = ContentAcquisitionService().acquire(request)

    assert result.acquisition_status == AcquisitionStatus.COMPLETED
    assert result.text_content == "A claim submitted for acquisition."
    assert result.image_paths == []
    assert result.errors == []


def test_image_acquisition_returns_local_path(tmp_path: Path) -> None:
    image_path = tmp_path / "claim.png"
    image_path.write_bytes(b"image bytes are not parsed by CAL")
    request = VerificationRequest(
        input_type=InputType.IMAGE,
        content={
            "file_reference": str(image_path),
            "file_name": "claim.png",
            "mime_type": "image/png",
        },
    )

    result = ContentAcquisitionService().acquire(request)

    assert result.acquisition_status == AcquisitionStatus.COMPLETED
    assert result.image_paths == [str(image_path)]
    assert result.metadata["size_bytes"] == image_path.stat().st_size


def test_invalid_local_file_returns_error() -> None:
    request = VerificationRequest(
        input_type=InputType.PDF,
        content={"file_reference": "/does/not/exist.pdf"},
    )

    result = ContentAcquisitionService().acquire(request)

    assert result.acquisition_status == AcquisitionStatus.FAILED
    assert result.errors[0].code == "FILE_NOT_FOUND"


def test_unsupported_input_type_is_rejected_by_request_schema() -> None:
    try:
        VerificationRequest(
            input_type="spreadsheet",
            content={"text": "unsupported"},
        )
    except ValueError as error:
        assert "input_type" in str(error)
    else:
        raise AssertionError("Unsupported input type should be rejected.")
