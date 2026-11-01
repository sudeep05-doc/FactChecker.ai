"""Pillow-based image validation and conservative normalization."""

import tempfile
from pathlib import Path
from typing import Optional, Set

from PIL import Image, UnidentifiedImageError

from app.cal.schemas import AcquisitionStatus, CALResult
from app.preprocessing.image_schema import (
    ImagePreprocessingIssue,
    ImagePreprocessingResult,
    ImagePreprocessingStatus,
)


SUPPORTED_IMAGE_FORMATS: Set[str] = {"JPEG", "PNG", "WEBP"}


class ImagePreprocessor:
    """Validate images and prepare a path-backed RGB representation."""

    def __init__(self, max_dimension: int = 224) -> None:
        if max_dimension < 1:
            raise ValueError("max_dimension must be positive")
        self.max_dimension = max_dimension

    def process(self, content: CALResult) -> ImagePreprocessingResult:
        base = {
            "request_id": content.request_id,
            "input_type": content.input_type,
        }

        if content.acquisition_status != AcquisitionStatus.COMPLETED:
            return self._failure(
                base,
                "ACQUISITION_INCOMPLETE",
                "CAL content was not acquired successfully.",
            )

        if not content.image_paths:
            return self._failure(
                base,
                "IMAGE_PATH_UNAVAILABLE",
                "CAL did not provide an image path.",
            )

        image_path = Path(content.image_paths[0]).expanduser()
        if not image_path.is_file():
            return self._failure(
                base,
                "IMAGE_NOT_FOUND",
                "The acquired image path does not exist.",
            )

        try:
            with Image.open(image_path) as opened_image:
                image_format = opened_image.format
                if image_format not in SUPPORTED_IMAGE_FORMATS:
                    return self._failure(
                        base,
                        "UNSUPPORTED_IMAGE_FORMAT",
                        "Only JPEG, PNG, and WEBP images are supported.",
                    )

                # verify() detects truncated or malformed image data without
                # retaining a second full image in memory.
                opened_image.verify()

            with Image.open(image_path) as image:
                image.load()
                original_width, original_height = image.size
                original_mode = image.mode
                output_width, output_height = _scaled_size(
                    original_width, original_height, self.max_dimension
                )
                requires_normalization = (
                    original_mode != "RGB"
                    or (output_width, output_height)
                    != (original_width, original_height)
                )

                processed_path = str(image_path)
                processed_format = image_format
                warnings = []

                if requires_normalization:
                    normalized = image.convert("RGB")
                    if (output_width, output_height) != normalized.size:
                        normalized = normalized.resize(
                            (output_width, output_height), Image.Resampling.LANCZOS
                        )
                    processed_path = _write_normalized_image(normalized)
                    processed_format = "PNG"
                    warnings.append(
                        ImagePreprocessingIssue(
                            code="IMAGE_NORMALIZED",
                            message="Image was converted to RGB and/or resized for downstream processing.",
                        )
                    )

                metadata = {
                    "original_mode": original_mode,
                    "processed_mode": "RGB" if requires_normalization else original_mode,
                    "original_file_name": image_path.name,
                    "original_file_size_bytes": image_path.stat().st_size,
                    "has_exif": bool(image.getexif()),
                    "metadata_keys": sorted(image.info.keys()),
                }

                return ImagePreprocessingResult(
                    **base,
                    processed_image_path=processed_path,
                    width=output_width,
                    height=output_height,
                    format=processed_format,
                    original_width=original_width,
                    original_height=original_height,
                    metadata=metadata,
                    preprocessing_status=ImagePreprocessingStatus.COMPLETED,
                    warnings=warnings,
                )
        except (UnidentifiedImageError, OSError, SyntaxError) as error:
            return self._failure(
                base,
                "CORRUPTED_IMAGE",
                f"The image could not be decoded safely: {error}.",
            )

    @staticmethod
    def _failure(base: dict, code: str, message: str) -> ImagePreprocessingResult:
        return ImagePreprocessingResult(
            **base,
            preprocessing_status=ImagePreprocessingStatus.FAILED,
            errors=[ImagePreprocessingIssue(code=code, message=message)],
        )


def _scaled_size(width: int, height: int, max_dimension: int) -> tuple[int, int]:
    scale = min(1.0, max_dimension / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def _write_normalized_image(image: Image.Image) -> str:
    temporary_file = tempfile.NamedTemporaryFile(
        prefix="factchecker-image-", suffix=".png", delete=False
    )
    temporary_path = temporary_file.name
    temporary_file.close()
    image.save(temporary_path, format="PNG")
    return temporary_path