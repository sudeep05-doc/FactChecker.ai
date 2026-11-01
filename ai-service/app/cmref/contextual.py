"""Extensible contextual feature interface."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ContextualFeature:
    name: str
    value: float
    version: str
    metadata: Dict[str, Any]


class ContextualFeatureProvider:
    """Provider interface; absent features are omitted, never zero-filled."""

    def features(self, usr: Any) -> list[ContextualFeature]:
        raise NotImplementedError


def collect_contextual_features(
    usr: Any,
    provider: Optional[Callable[[Any], list[ContextualFeature]]] = None,
) -> list[ContextualFeature]:
    if provider is None:
        return []
    features = provider(usr)
    for feature in features:
        if not 0 <= feature.value <= 1:
            raise ValueError("contextual feature values must be in [0, 1]")
    return features


def aggregate_contextual_features(features: list[ContextualFeature]) -> Optional[float]:
    if not features:
        return None
    return sum(feature.value for feature in features) / len(features)