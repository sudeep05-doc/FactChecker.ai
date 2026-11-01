"""Foundation model registry contract. No models are loaded yet."""


class ModelRegistry:
    """Future lazy-loading registry for modality-specific models."""

    def get(self, name: str):
        raise NotImplementedError("Foundation models are not configured yet.")
