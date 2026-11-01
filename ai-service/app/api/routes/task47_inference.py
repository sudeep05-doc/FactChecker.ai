"""HTTP endpoints for verified Task 47 modality-specific inference."""

from functools import lru_cache
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.pipeline.task47_inference import (
    ALLOWED_IMAGE_TYPES,
    MAX_UPLOAD_BYTES,
    InferenceUnavailableError,
    InvalidInferenceInputError,
    Task47Inference,
)


router = APIRouter(prefix="/api/v1/classify", tags=["task47-inference"])


class TextInferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000)


@lru_cache(maxsize=1)
def _inference() -> Task47Inference:
    return Task47Inference()


async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File exceeds the 25 MB upload limit.")
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from error
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds the 25 MB upload limit.")
    return bytes(content)


def _execute(callable_: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        return callable_(*args, **kwargs)
    except InvalidInferenceInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except InferenceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/text")
def classify_text(request: TextInferenceRequest) -> Dict[str, Any]:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="Text must contain at least one non-whitespace character.")
    result = _execute(lambda: _inference().predict_text(request.text))
    result["input_type"] = "text"
    return result


@router.post("/image")
async def classify_image(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Image must be JPEG, PNG, or WebP.")
    image_bytes = await _read_limited_body(request)
    result = _execute(lambda: _inference().predict_image(image_bytes, content_type))
    result["input_type"] = "image"
    return result


@router.post("/pdf")
async def classify_pdf(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="File must be a PDF.")
    pdf_bytes = await _read_limited_body(request)
    result = _execute(lambda: _inference().predict_pdf(pdf_bytes))
    return result
