"""Application API router."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.task47_inference import router as task47_inference_router
from app.api.routes.verification import router as verification_router

api_router = APIRouter()
api_router.add_api_route(
	"/",
	lambda: {
		"service": "factchecker-ai",
		"message": "FactChecker.ai AI service is running.",
	},
	methods=["GET"],
	tags=["service"],
)
api_router.include_router(health_router)
api_router.include_router(verification_router, prefix="/api/v1")
api_router.include_router(task47_inference_router)
