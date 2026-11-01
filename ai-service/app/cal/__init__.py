"""Content Acquisition Layer (CAL)."""

from app.cal.schemas import AcquisitionStatus, CALResult
from app.cal.service import ContentAcquisitionService

__all__ = ["AcquisitionStatus", "CALResult", "ContentAcquisitionService"]
