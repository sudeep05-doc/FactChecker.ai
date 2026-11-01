from uuid import uuid4

from app.cal import AcquisitionStatus, CALResult
from app.preprocessing import PreprocessingService, PreprocessingStatus


def make_cal_result(text: str, status: AcquisitionStatus = AcquisitionStatus.COMPLETED):
    return CALResult(
        request_id=uuid4(),
        input_type="text",
        source="text",
        text_content=text,
        acquisition_status=status,
    )


def test_normal_text_is_cleaned_without_losing_punctuation() -> None:
    result = PreprocessingService().process(make_cal_result("  This is news!  " ))

    assert result.preprocessing_status == PreprocessingStatus.COMPLETED
    assert result.cleaned_text == "This is news!"
    assert result.detected_language == "en"
    assert result.cleaned_text_length == 13


def test_empty_text_fails_validation() -> None:
    result = PreprocessingService().process(make_cal_result("   \n\t"))

    assert result.preprocessing_status == PreprocessingStatus.FAILED
    assert result.errors[0].code == "EMPTY_CONTENT"


def test_whitespace_heavy_text_is_collapsed() -> None:
    result = PreprocessingService().process(make_cal_result("A\t\n  claim   with spaces."))

    assert result.cleaned_text == "A claim with spaces."
    assert result.original_text_length > result.cleaned_text_length


def test_unicode_text_is_normalized_and_preserved() -> None:
    result = PreprocessingService().process(make_cal_result("Cafe\u0301 — 50% ✅"))

    assert result.cleaned_text == "Café — 50% ✅"
    assert result.detected_language == "en"


def test_multilingual_scripts_are_reported_as_mixed() -> None:
    result = PreprocessingService().process(make_cal_result("Hello नमस्ते"))

    assert result.cleaned_text == "Hello नमस्ते"
    assert result.detected_language == "mixed"


def test_extremely_long_text_fails_configured_limit() -> None:
    preprocessor = PreprocessingService()
    result = preprocessor.process(make_cal_result("a" * 1_000_001))

    assert result.preprocessing_status == PreprocessingStatus.FAILED
    assert result.errors[0].code == "TEXT_TOO_LONG"