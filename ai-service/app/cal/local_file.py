"""Local-file acquisition for image, PDF, audio, and video inputs."""

from pathlib import Path
from typing import Dict

from app.cal.schemas import AcquisitionError, AcquisitionStatus, CALResult
from app.schemas.verification import InputType, VerificationRequest


_FILE_TYPES = {
    InputType.IMAGE: "image",
    InputType.PDF: "pdf",
    InputType.AUDIO: "audio",
    InputType.VIDEO: "video",
}


class LocalFileAcquirer:
    """Validate a local file and expose its path without parsing file contents."""

    def acquire(self, request: VerificationRequest) -> CALResult:
        input_type = request.input_type
        file_reference = request.content.file_reference
        source = file_reference or "local_file"
        common = {
            "request_id": request.request_id,
            "input_type": input_type.value,
            "source": source,
        }

        if not file_reference:
            return CALResult(
                **common,
                acquisition_status=AcquisitionStatus.FAILED,
                errors=[
                    AcquisitionError(
                        code="FILE_REFERENCE_UNAVAILABLE",
                        message="A local file reference is required.",
                        field="content.file_reference",
                    )
                ],
            )

        path = Path(file_reference).expanduser()
        if not path.is_file():
            return CALResult(
                **common,
                acquisition_status=AcquisitionStatus.FAILED,
                errors=[
                    AcquisitionError(
                        code="FILE_NOT_FOUND",
                        message="The referenced local file does not exist.",
                        field="content.file_reference",
                    )
                ],
            )

        metadata: Dict[str, object] = {
            "file_path": str(path),
            "file_name": request.content.file_name or path.name,
            "mime_type": request.content.mime_type,
            "size_bytes": path.stat().st_size,
        }
        result = CALResult(
            **common,
            metadata=metadata,
            acquisition_status=AcquisitionStatus.COMPLETED,
        )

        if input_type == InputType.IMAGE:
            result.image_paths = [str(path)]
        elif input_type == InputType.AUDIO:
            result.audio_path = str(path)
        elif input_type == InputType.VIDEO:
            result.video_path = str(path)

        return result


def supported_local_file_type(input_type: InputType) -> bool:
    return input_type in _FILE_TYPES