"""Verification API route."""

from fastapi import APIRouter

from app.pipeline.mock import MockVerificationPipeline
from app.schemas.verification import VerificationRequest, VerificationResponse

router = APIRouter(tags=["verification"])
pipeline = MockVerificationPipeline()


@router.post("/verify", response_model=VerificationResponse)
def verify(request: VerificationRequest) -> VerificationResponse:
    """Validate and pass a request through the temporary mock pipeline."""

    return pipeline.analyze(request)