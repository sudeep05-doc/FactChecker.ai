"""Text content acquisition."""

from app.cal.schemas import AcquisitionStatus, CALResult
from app.schemas.verification import InputType, VerificationRequest


class TextAcquirer:
    """Normalize submitted text without changing its content."""

    def acquire(self, request: VerificationRequest) -> CALResult:
        text = request.content.text
        if text is None:
            return CALResult(
                request_id=request.request_id,
                input_type=InputType.TEXT.value,
                source="text",
                acquisition_status=AcquisitionStatus.FAILED,
                errors=[
                    {
                        "code": "TEXT_UNAVAILABLE",
                        "message": "Text content is not available.",
                        "field": "content.text",
                    }
                ],
            )

        return CALResult(
            request_id=request.request_id,
            input_type=InputType.TEXT.value,
            source="text",
            text_content=text,
            metadata={"character_count": len(text)},
            acquisition_status=AcquisitionStatus.COMPLETED,
        )