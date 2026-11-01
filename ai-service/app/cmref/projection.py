"""Versioned, explicit embedding projection adapters."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence


@dataclass(frozen=True)
class ProjectionAdapter:
    model_name: str
    source_dimension: int
    target_dimension: int
    version: str
    transform: Callable[[Sequence[float]], Sequence[float]]

    def project(self, values: Sequence[float]) -> list[float]:
        if len(values) != self.source_dimension:
            raise ValueError("projection input dimension does not match adapter")
        projected = list(self.transform(values))
        if len(projected) != self.target_dimension:
            raise ValueError("projection output dimension does not match adapter")
        return projected


class ProjectionRegistry:
    """Resolve only explicitly configured adapters, with safe identity support."""

    def __init__(self, working_dimension: int, adapters: Optional[Dict[str, ProjectionAdapter]] = None):
        if working_dimension < 1:
            raise ValueError("working_dimension must be positive")
        self.working_dimension = working_dimension
        self.adapters = adapters or {}

    def resolve(self, model_name: str, source_dimension: int) -> Optional[ProjectionAdapter]:
        adapter = self.adapters.get(model_name)
        if adapter is not None:
            return adapter
        if source_dimension == self.working_dimension:
            return ProjectionAdapter(
                model_name=model_name,
                source_dimension=source_dimension,
                target_dimension=self.working_dimension,
                version="identity-v1",
                transform=lambda values: list(values),
            )
        return None