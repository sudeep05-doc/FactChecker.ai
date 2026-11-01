from typing import Any, Dict

import httpx

from app.cal.schemas import AcquisitionStatus
from app.cal.url import NewsURLAcquirer, YouTubeAcquirer
from app.schemas.verification import InputType, VerificationRequest


class FakeResponse:
    def __init__(self, content: bytes, url: str = "https://news.example/article") -> None:
        self.content = content
        self.url = url
        self.encoding = "utf-8"
        self.headers = {"content-type": "text/html", "content-length": str(len(content))}

    def raise_for_status(self) -> None:
        return None


class FakeHTTPClient:
    def __init__(self, response: Any = None, error: Exception = None) -> None:
        self.response = response
        self.error = error

    def get(self, url: str) -> Any:
        if self.error:
            raise self.error
        return self.response


class FakeYouTubeExtractor:
    def extract_info(self, url: str, download: bool) -> Dict[str, Any]:
        assert download is False
        return {
            "title": "Example video",
            "channel": "Example channel",
            "duration": 12,
            "description": "A description for later transcription.",
            "thumbnail": "https://img.youtube.com/thumb.jpg",
            "formats": [
                {"acodec": "opus", "vcodec": "none"},
                {"acodec": "none", "vcodec": "avc1"},
            ],
        }


def test_news_url_extracts_article_and_image_metadata() -> None:
    html = b"""
    <html><head><title>Fallback title</title></head>
    <body><article><h1>Article title</h1><p>Article body text.</p></article>
    <img src="/image.jpg"></body></html>
    """
    request = VerificationRequest(
        input_type=InputType.NEWS_URL,
        content={"url": "https://news.example/article"},
    )
    acquirer = NewsURLAcquirer(
        http_client=FakeHTTPClient(FakeResponse(html)),
        text_extractor=lambda html, **kwargs: "Article body text.",
        metadata_extractor=lambda html: type("Metadata", (), {"title": "Article title"})(),
    )

    result = acquirer.acquire(request)

    assert result.acquisition_status == AcquisitionStatus.COMPLETED
    assert result.text_content == "Article body text."
    assert result.metadata["title"] == "Article title"
    assert result.metadata["image_urls"] == ["https://news.example/image.jpg"]


def test_news_url_enforces_content_limit() -> None:
    request = VerificationRequest(
        input_type=InputType.NEWS_URL,
        content={"url": "https://news.example/article"},
    )
    response = FakeResponse(b"too large")
    response.headers["content-length"] = "100"
    result = NewsURLAcquirer(
        http_client=FakeHTTPClient(response),
        max_content_bytes=10,
    ).acquire(request)

    assert result.acquisition_status == AcquisitionStatus.FAILED
    assert result.errors[0].code == "CONTENT_SIZE_LIMIT"


def test_news_url_handles_timeout() -> None:
    request = VerificationRequest(
        input_type=InputType.NEWS_URL,
        content={"url": "https://news.example/article"},
    )
    result = NewsURLAcquirer(
        http_client=FakeHTTPClient(error=httpx.TimeoutException("timeout")),
    ).acquire(request)

    assert result.errors[0].code == "URL_TIMEOUT"


def test_youtube_acquisition_reads_metadata_without_download() -> None:
    request = VerificationRequest(
        input_type=InputType.YOUTUBE_URL,
        content={"url": "https://www.youtube.com/watch?v=example"},
    )
    result = YouTubeAcquirer(extractor=FakeYouTubeExtractor()).acquire(request)

    assert result.acquisition_status == AcquisitionStatus.COMPLETED
    assert result.metadata["downloaded"] is False
    assert result.metadata["available_audio_formats"] == 1
    assert result.audio_path is None


def test_unsupported_url_is_rejected() -> None:
    request = VerificationRequest(
        input_type=InputType.YOUTUBE_URL,
        content={"url": "https://example.com/not-youtube"},
    )

    result = YouTubeAcquirer(extractor=FakeYouTubeExtractor()).acquire(request)

    assert result.acquisition_status == AcquisitionStatus.FAILED
    assert result.errors[0].code == "UNSUPPORTED_URL"