"""Bounded news and YouTube URL acquisition for the CAL layer."""

from html.parser import HTMLParser
from typing import Any, Callable, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from app.cal.schemas import AcquisitionError, AcquisitionStatus, CALResult
from app.schemas.verification import InputType, VerificationRequest


class ContentSizeLimitError(Exception):
    """Raised when a fetched response exceeds the configured byte limit."""


class NewsURLAcquirer:
    """Fetch and extract article content without judging source credibility."""

    def __init__(
        self,
        http_client: Optional[Any] = None,
        timeout_seconds: float = 10.0,
        max_content_bytes: int = 5 * 1024 * 1024,
        text_extractor: Callable[..., Optional[str]] = trafilatura.extract,
        metadata_extractor: Callable[..., Any] = trafilatura.extract_metadata,
    ) -> None:
        if timeout_seconds <= 0 or max_content_bytes < 1:
            raise ValueError("timeout_seconds and max_content_bytes must be positive")
        self.http_client = http_client
        self.timeout_seconds = timeout_seconds
        self.max_content_bytes = max_content_bytes
        self.text_extractor = text_extractor
        self.metadata_extractor = metadata_extractor

    def acquire(self, request: VerificationRequest) -> CALResult:
        url = str(request.content.url or "")
        validation_error = _validate_http_url(url)
        if validation_error:
            return _failure(request, "INVALID_URL", validation_error)
        if _is_youtube_url(url):
            return _failure(request, "UNSUPPORTED_URL", "Use youtube_url for YouTube content.")

        client = self.http_client or httpx.Client(
            follow_redirects=True,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "FactChecker.ai CAL/1.0"},
        )
        owns_client = self.http_client is None
        try:
            response = _request_limited(client, url, self.max_content_bytes)
            response.raise_for_status()
            html = response.content.decode(response.encoding or "utf-8", errors="replace")
            text = self.text_extractor(html, include_comments=False, include_tables=True) or ""
            article_metadata = self.metadata_extractor(html)
            image_urls = _ImageURLParser().extract(html, str(response.url))
            title = getattr(article_metadata, "title", None) or _html_title(html)

            warnings: List[AcquisitionError] = []
            if not text:
                warnings.append(
                    AcquisitionError(
                        code="ARTICLE_TEXT_NOT_FOUND",
                        message="No main article text could be extracted.",
                    )
                )
            return CALResult(
                request_id=request.request_id,
                input_type=InputType.NEWS_URL.value,
                source=str(response.url),
                text_content=text or None,
                metadata={
                    "title": title,
                    "author": getattr(article_metadata, "author", None),
                    "date": getattr(article_metadata, "date", None),
                    "description": getattr(article_metadata, "description", None),
                    "image_urls": image_urls,
                    "content_type": response.headers.get("content-type"),
                    "content_length_bytes": len(response.content),
                },
                acquisition_status=AcquisitionStatus.COMPLETED,
                errors=warnings,
            )
        except httpx.TimeoutException:
            return _failure(request, "URL_TIMEOUT", "The article request timed out.")
        except ContentSizeLimitError as error:
            return _failure(request, "CONTENT_SIZE_LIMIT", str(error))
        except httpx.HTTPError as error:
            return _failure(request, "NETWORK_ERROR", f"The article could not be fetched: {error}.")
        except UnicodeError as error:
            return _failure(request, "CONTENT_DECODE_ERROR", f"The article response could not be decoded: {error}.")
        finally:
            if owns_client:
                client.close()


class YouTubeAcquirer:
    """Inspect YouTube metadata without downloading the media by default."""

    def __init__(
        self,
        extractor: Optional[Any] = None,
        quality: str = "best[height<=720]/best",
        max_download_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        if max_download_bytes < 1:
            raise ValueError("max_download_bytes must be positive")
        self.extractor = extractor
        self.quality = quality
        self.max_download_bytes = max_download_bytes

    def acquire(self, request: VerificationRequest) -> CALResult:
        url = str(request.content.url or "")
        validation_error = _validate_http_url(url)
        if validation_error:
            return _failure(request, "INVALID_URL", validation_error)
        if not _is_youtube_url(url):
            return _failure(request, "UNSUPPORTED_URL", "The URL is not a supported YouTube URL.")

        try:
            extractor = self.extractor or _create_youtube_extractor(
                self.quality, self.max_download_bytes
            )
            info = extractor.extract_info(url, download=False)
            if not info:
                return _failure(request, "YOUTUBE_METADATA_UNAVAILABLE", "No YouTube metadata was returned.")

            formats = info.get("formats") or []
            audio_formats = [item for item in formats if item.get("acodec") not in (None, "none")]
            video_formats = [item for item in formats if item.get("vcodec") not in (None, "none")]
            return CALResult(
                request_id=request.request_id,
                input_type=InputType.YOUTUBE_URL.value,
                source=url,
                text_content=info.get("description") or None,
                metadata={
                    "title": info.get("title"),
                    "channel": info.get("channel") or info.get("uploader"),
                    "duration_seconds": info.get("duration"),
                    "thumbnail_url": info.get("thumbnail"),
                    "available_audio_formats": len(audio_formats),
                    "available_video_formats": len(video_formats),
                    "requested_quality": self.quality,
                    "downloaded": False,
                    "media_preparation": "metadata_only; ready for later media selection",
                },
                acquisition_status=AcquisitionStatus.COMPLETED,
            )
        except Exception as error:
            return _failure(request, "YOUTUBE_ACQUISITION_ERROR", f"YouTube metadata failed: {error}")


def _request_limited(client: Any, url: str, max_content_bytes: int) -> Any:
    if not hasattr(client, "stream"):
        response = client.get(url)
        _check_declared_size(response, max_content_bytes)
        if len(response.content) > max_content_bytes:
            raise ContentSizeLimitError("Article content exceeds the configured size limit.")
        return response

    with client.stream("GET", url) as response:
        _check_declared_size(response, max_content_bytes)
        chunks = []
        total_size = 0
        for chunk in response.iter_bytes():
            total_size += len(chunk)
            if total_size > max_content_bytes:
                raise ContentSizeLimitError("Article content exceeds the configured size limit.")
            chunks.append(chunk)
        response._content = b"".join(chunks)
        return response


def _check_declared_size(response: Any, max_content_bytes: int) -> None:
    declared_size = response.headers.get("content-length")
    if declared_size and int(declared_size) > max_content_bytes:
        raise ContentSizeLimitError("Article content exceeds the configured size limit.")


def _create_youtube_extractor(quality: str, max_download_bytes: int) -> Any:
    from yt_dlp import YoutubeDL

    return YoutubeDL(
        {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": quality,
            "max_filesize": max_download_bytes,
        }
    )


def _validate_http_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Only absolute HTTP or HTTPS URLs are supported."
    return None


def _is_youtube_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}


def _html_title(html: str) -> Optional[str]:
    parser = _TitleParser()
    parser.feed(html)
    return parser.title


def _failure(request: VerificationRequest, code: str, message: str) -> CALResult:
    return CALResult(
        request_id=request.request_id,
        input_type=request.input_type.value,
        source=str(request.content.url or ""),
        acquisition_status=AcquisitionStatus.FAILED,
        errors=[AcquisitionError(code=code, message=message, field="content.url")],
    )


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        self.in_title = tag.lower() == "title"

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title and self.title is None:
            self.title = data.strip() or None


class _ImageURLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: List[str] = []

    def extract(self, html: str, base_url: str) -> List[str]:
        self.feed(html)
        return [urljoin(base_url, url) for url in self.urls]

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag.lower() != "img":
            return
        attributes = dict(attrs)
        candidate = attributes.get("src") or attributes.get("data-src")
        if candidate and candidate not in self.urls:
            self.urls.append(candidate)