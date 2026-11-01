"""FastAPI application entry point."""

from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config.settings import get_allowed_origins, get_settings
from app.utils.structured_logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(
    title="FactChecker.ai AI Service",
    version=settings.app_version,
    description="Standalone FastAPI microservice for future explainable multimodal fake news detection.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(settings),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "request_validation_failed",
        extra={"event": "request_validation_failed", "path": request.url.path},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={"event": "unhandled_exception", "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    logger.info(
        "request_completed",
        extra={
            "event": "request_completed",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.include_router(api_router)
