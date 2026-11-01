"""Content Acquisition Layer orchestration."""

from app.cal.local_file import LocalFileAcquirer
from app.cal.schemas import AcquisitionError, AcquisitionStatus, CALResult
from app.cal.text import TextAcquirer
from app.cal.url import NewsURLAcquirer, YouTubeAcquirer
from app.schemas.verification import InputType, VerificationRequest


class ContentAcquisitionService:
    """Route every supported request through a common acquisition interface."""

    def __init__(self) -> None:
        self._acquirers = {
            InputType.TEXT: TextAcquirer(),
            InputType.IMAGE: LocalFileAcquirer(),
            InputType.PDF: LocalFileAcquirer(),
            InputType.AUDIO: LocalFileAcquirer(),
            InputType.VIDEO: LocalFileAcquirer(),
            InputType.NEWS_URL: NewsURLAcquirer(),
            InputType.YOUTUBE_URL: YouTubeAcquirer(),
        }

    def acquire(self, request: VerificationRequest) -> CALResult:
        acquirer = self._acquirers.get(request.input_type)
        if acquirer is None:
            return CALResult(
                request_id=request.request_id,
                input_type=str(request.input_type),
                source="unknown",
                acquisition_status=AcquisitionStatus.FAILED,
                errors=[
                    AcquisitionError(
                        code="UNSUPPORTED_INPUT_TYPE",
                        message="The input type is not supported by CAL.",
                        field="input_type",
                    )
                ],
            )

        return acquirer.acquire(request)
