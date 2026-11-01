"""Conservative, deterministic text preprocessing."""

import re
import unicodedata
from typing import Dict, Optional

from app.cal.schemas import AcquisitionStatus, CALResult
from app.preprocessing.schemas import (
    PreprocessingIssue,
    PreprocessingStatus,
    TextPreprocessingResult,
)


_COMMON_LANGUAGE_MARKERS: Dict[str, tuple[str, ...]] = {
    "en": (" the ", " and ", " is ", " of "),
    "es": (" el ", " la ", " y ", " de "),
    "fr": (" le ", " la ", " et ", " de "),
    "de": (" der ", " die ", " und ", " ist "),
}


class TextPreprocessor:
    """Normalize text without stopword removal, stemming, or lemmatization."""

    def __init__(self, max_text_length: int = 1_000_000) -> None:
        if max_text_length < 1:
            raise ValueError("max_text_length must be positive")
        self.max_text_length = max_text_length

    def process(self, content: CALResult) -> TextPreprocessingResult:
        text = content.text_content
        original_length = len(text) if text is not None else 0
        base = {
            "request_id": content.request_id,
            "input_type": content.input_type,
            "original_text_length": original_length,
        }

        if content.acquisition_status != AcquisitionStatus.COMPLETED:
            return TextPreprocessingResult(
                **base,
                preprocessing_status=PreprocessingStatus.FAILED,
                errors=[
                    PreprocessingIssue(
                        code="ACQUISITION_INCOMPLETE",
                        message="CAL content was not acquired successfully.",
                    )
                ],
            )

        if text is None or not text.strip():
            return TextPreprocessingResult(
                **base,
                preprocessing_status=PreprocessingStatus.FAILED,
                errors=[
                    PreprocessingIssue(
                        code="EMPTY_CONTENT",
                        message="Text content is empty after whitespace inspection.",
                    )
                ],
            )

        if original_length > self.max_text_length:
            return TextPreprocessingResult(
                **base,
                preprocessing_status=PreprocessingStatus.FAILED,
                errors=[
                    PreprocessingIssue(
                        code="TEXT_TOO_LONG",
                        message=(
                            "Text exceeds the configured maximum length of "
                            f"{self.max_text_length} characters."
                        ),
                    )
                ],
            )

        cleaned_text = clean_text(text)
        if not cleaned_text:
            return TextPreprocessingResult(
                **base,
                preprocessing_status=PreprocessingStatus.FAILED,
                errors=[
                    PreprocessingIssue(
                        code="EMPTY_CONTENT",
                        message="Text content is empty after preprocessing.",
                    )
                ],
            )

        warnings = []
        if cleaned_text != text:
            warnings.append(
                PreprocessingIssue(
                    code="TEXT_NORMALIZED",
                    message="Unicode, control characters, or whitespace were normalized.",
                )
            )

        return TextPreprocessingResult(
            **base,
            cleaned_text=cleaned_text,
            cleaned_text_length=len(cleaned_text),
            detected_language=detect_language(cleaned_text),
            preprocessing_status=PreprocessingStatus.COMPLETED,
            warnings=warnings,
        )


def clean_text(text: str) -> str:
    """Apply conservative normalization while preserving punctuation and words."""

    normalized = unicodedata.normalize("NFKC", text)
    without_controls = "".join(
        character
        for character in normalized
        if character in "\t\n\r" or not unicodedata.category(character).startswith("C")
    )
    return re.sub(r"\s+", " ", without_controls).strip()


def detect_language(text: str) -> Optional[str]:
    """Return a basic deterministic language label from scripts and markers."""

    scripts = set()
    for character in text:
        code_point = ord(character)
        if 0x0900 <= code_point <= 0x097F:
            scripts.add("hi")
        elif 0x0980 <= code_point <= 0x09FF:
            scripts.add("bn")
        elif 0x0400 <= code_point <= 0x04FF:
            scripts.add("ru")
        elif 0x0600 <= code_point <= 0x06FF:
            scripts.add("ar")
        elif 0x3040 <= code_point <= 0x30FF:
            scripts.add("ja")
        elif 0x4E00 <= code_point <= 0x9FFF:
            scripts.add("zh")
        elif 0xAC00 <= code_point <= 0xD7AF:
            scripts.add("ko")
        elif character.isalpha() and "LATIN" in unicodedata.name(character, ""):
            scripts.add("latin")

    if len(scripts) > 1:
        return "mixed"
    if scripts and scripts != {"latin"}:
        return next(iter(scripts))
    if scripts == {"latin"}:
        lowered = f" {text.lower()} "
        matches = [
            language
            for language, markers in _COMMON_LANGUAGE_MARKERS.items()
            if any(marker in lowered for marker in markers)
        ]
        return matches[0] if len(matches) == 1 else "en"
    return None