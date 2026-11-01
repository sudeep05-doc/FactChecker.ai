"""Bounded, resumable image acquisition for approved Task 27 Fakeddit manifests."""

from __future__ import annotations

import argparse
import hashlib
import httpx
import json
import logging
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from PIL import Image, UnidentifiedImageError

from app.evaluation.fakeddit import FakedditPreparationError
from app.evaluation.fakeddit_preparation import (
    PREPARATION_VERSION,
    normalize_image_url,
)
from app.evaluation.schemas import DatasetSplit, EvaluationSample, GroundTruthLabel
from app.preprocessing.image import SUPPORTED_IMAGE_FORMATS
from app.utils.structured_logging import configure_logging, get_logger


ACQUISITION_VERSION = "fakeddit-image-acquisition-v1"
DEFAULT_USER_AGENT = "FactChecker.ai Research Image Acquisition/1.0"
SUPPORTED_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
SUCCESS_STATUSES = {"downloaded", "already_present"}
RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}
SPLITS = (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST)
logger = get_logger(__name__)


class FakedditAcquisitionError(ValueError):
    """Raised when approved manifests or acquisition configuration are invalid."""


class _AcquisitionFailure(Exception):
    def __init__(self, status: str, message: str, *, http_status: Optional[int] = None):
        super().__init__(message)
        self.status = status
        self.http_status = http_status


class _StorageBudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class FakedditAcquisitionConfig:
    concurrency: int = 4
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    max_backoff_seconds: float = 30.0
    max_retry_after_seconds: float = 60.0
    max_image_bytes: int = 15 * 1024 * 1024
    max_dimension: int = 20_000
    max_pixels: int = 25_000_000
    max_total_bytes: int = 20 * 1024 * 1024 * 1024
    request_delay_seconds: float = 0.1
    request_jitter_seconds: float = 0.1
    chunk_bytes: int = 64 * 1024
    disk_reserve_bytes: int = 128 * 1024 * 1024
    progress_interval: int = 100
    user_agent: str = DEFAULT_USER_AGENT
    resume: bool = True

    def __post_init__(self) -> None:
        positive = {
            "concurrency": self.concurrency,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "max_image_bytes": self.max_image_bytes,
            "max_dimension": self.max_dimension,
            "max_pixels": self.max_pixels,
            "max_total_bytes": self.max_total_bytes,
            "chunk_bytes": self.chunk_bytes,
            "progress_interval": self.progress_interval,
        }
        if any(value <= 0 for value in positive.values()):
            raise FakedditAcquisitionError("concurrency, timeouts, limits, and progress interval must be positive")
        nonnegative = (
            self.max_retries,
            self.backoff_factor,
            self.max_backoff_seconds,
            self.max_retry_after_seconds,
            self.request_delay_seconds,
            self.request_jitter_seconds,
            self.disk_reserve_bytes,
        )
        if any(value < 0 for value in nonnegative):
            raise FakedditAcquisitionError("retry, delay, and reserve settings must be non-negative")
        if not self.user_agent.strip():
            raise FakedditAcquisitionError("user_agent must not be empty")


@dataclass
class _Target:
    split: DatasetSplit
    record: Dict[str, object]
    source_url: str
    normalized_url: str
    sample_id: str
    label: GroundTruthLabel


@dataclass
class _ImageResult:
    source_url: str
    normalized_url: str
    status: str
    attempts: int = 0
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    file_size_bytes: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: Optional[str] = None
    detected_format: Optional[str] = None
    local_path: Optional[Path] = None
    error: Optional[str] = None
    duplicate_content_of: Optional[str] = None
    replaced_corrupt_existing: bool = False


class _ByteBudget:
    def __init__(self, maximum: int, initial_bytes: int):
        self.maximum = maximum
        self.committed = initial_bytes
        self.in_flight = 0
        self.lock = threading.Lock()

    def reserve(self, amount: int) -> None:
        with self.lock:
            if self.committed + self.in_flight + amount > self.maximum:
                raise _StorageBudgetExceeded("configured max_total_bytes would be exceeded")
            self.in_flight += amount

    def release_in_flight(self, amount: int) -> None:
        with self.lock:
            self.in_flight = max(0, self.in_flight - amount)

    def commit(self, amount: int) -> None:
        with self.lock:
            self.in_flight = max(0, self.in_flight - amount)
            self.committed += amount

    def release_committed(self, amount: int) -> None:
        with self.lock:
            self.committed = max(0, self.committed - amount)


class _RobotsPolicy:
    def __init__(self, client: httpx.Client, config: FakedditAcquisitionConfig):
        self.client = client
        self.config = config
        self.cache = {}
        self.locks = {}
        self.lock = threading.Lock()

    def check(self, url: str):
        parsed = urlparse(url)
        origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
        with self.lock:
            host_lock = self.locks.setdefault(origin, threading.Lock())
        with host_lock:
            if origin not in self.cache:
                self.cache[origin] = self._load_policy(origin, url)
            return self.cache[origin]

    def _load_policy(self, origin: str, image_url: str):
        robots_url = origin + "/robots.txt"
        retry_delay = 0.0
        for attempt in range(1, self.config.max_retries + 2):
            if attempt > 1:
                time.sleep(retry_delay)
            _request_delay(self.config)
            retry_status = None
            retry_after = None
            try:
                with self.client.stream("GET", robots_url) as response:
                    if response.status_code == 404:
                        return True, None
                    if response.status_code not in range(200, 300):
                        retry_status = response.status_code
                        retry_after = response.headers.get("retry-after")
                        if response.status_code in RETRYABLE_HTTP_STATUSES and attempt <= self.config.max_retries:
                            retry_delay = _retry_delay(
                                self.config, attempt, retry_status, retry_after
                            )
                            continue
                        return False, f"robots.txt returned HTTP {response.status_code}"
                    body = bytearray()
                    for chunk in response.iter_bytes(16 * 1024):
                        if len(body) + len(chunk) > 512 * 1024:
                            return False, "robots.txt exceeded 512 KiB safety limit"
                        body.extend(chunk)
                    parser = RobotFileParser(robots_url)
                    parser.parse(body.decode("utf-8", errors="replace").splitlines())
                    product_token = self.config.user_agent.split()[0]
                    allowed = parser.can_fetch(product_token, image_url)
                    return (True, None) if allowed else (False, "robots.txt disallows this URL")
            except httpx.TimeoutException as error:
                if attempt <= self.config.max_retries:
                    retry_delay = _retry_delay(self.config, attempt, None, None)
                    continue
                return False, f"robots.txt request timed out: {error}"
            except httpx.HTTPError as error:
                if attempt <= self.config.max_retries:
                    retry_delay = _retry_delay(self.config, attempt, None, None)
                    continue
                return False, f"robots.txt request failed: {error}"
        return False, "robots.txt policy could not be established"


def stable_image_filename(normalized_url: str, detected_format: str) -> str:
    """Return a stable URL-derived filename with an extension from decoded bytes."""
    extension = SUPPORTED_EXTENSIONS.get(detected_format.upper())
    if extension is None:
        raise FakedditAcquisitionError(f"unsupported decoded image format: {detected_format}")
    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    return f"{digest}{extension}"


def acquire_fakeddit_images(
    train_manifest: str | Path,
    validation_manifest: str | Path,
    test_manifest: str | Path,
    *,
    output_dir: str | Path,
    config: FakedditAcquisitionConfig = FakedditAcquisitionConfig(),
    dry_run: bool = False,
    max_samples: Optional[int] = None,
    http_client: Optional[httpx.Client] = None,
    progress: bool = True,
) -> Dict[str, object]:
    """Acquire only images named in Task 27 manifests and write acquired JSONL files."""
    manifests = {
        DatasetSplit.TRAIN: Path(train_manifest),
        DatasetSplit.VALIDATION: Path(validation_manifest),
        DatasetSplit.TEST: Path(test_manifest),
    }
    destination = Path(output_dir)
    all_targets, preparation_versions = _read_targets(manifests)
    total_manifest_records = len(all_targets)
    targets = _limit_targets(all_targets, max_samples)
    unique_targets = _unique_url_targets(targets)
    available_bytes = _available_bytes(destination)

    if dry_run:
        return _dry_run_report(
            manifests,
            targets,
            unique_targets,
            destination,
            config,
            available_bytes,
            preparation_versions,
            max_samples,
            total_manifest_records,
        )

    images_dir = destination / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    _remove_stale_parts(images_dir)
    initial_bytes = _image_directory_bytes(images_dir)
    if initial_bytes > config.max_total_bytes:
        raise FakedditAcquisitionError(
            f"existing images use {initial_bytes} bytes, above max_total_bytes={config.max_total_bytes}"
        )
    client = http_client or httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(
            config.read_timeout,
            connect=config.connect_timeout,
            read=config.read_timeout,
            write=config.read_timeout,
            pool=config.connect_timeout,
        ),
        headers={"User-Agent": config.user_agent},
    )
    owns_client = http_client is None
    budget = _ByteBudget(config.max_total_bytes, initial_bytes)
    previous_metadata = _previous_acquisition_metadata(destination)
    robots_policy = _RobotsPolicy(client, config)
    try:
        results = _acquire_unique_targets(
            unique_targets,
            images_dir,
            destination,
            client,
            config,
            budget,
            previous_metadata,
            robots_policy,
            progress,
        )
    finally:
        if owns_client:
            client.close()

    _deduplicate_content(results, images_dir, budget)
    acquired_manifests = _build_acquired_manifests(targets, results, destination)
    report = _build_report(
        manifests,
        targets,
        unique_targets,
        results,
        acquired_manifests,
        destination,
        config,
        available_bytes,
        preparation_versions,
        max_samples,
        total_manifest_records,
    )
    acquired_dir = destination / "acquired"
    acquired_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        _atomic_write_jsonl(acquired_dir / f"{split.value}.jsonl", acquired_manifests[split])
    _atomic_write_json(destination / "acquisition_report.json", report)
    return report


def _read_targets(manifests: Mapping[DatasetSplit, Path]):
    targets: List[_Target] = []
    versions = set()
    for split in SPLITS:
        path = manifests[split]
        if not path.is_file():
            raise FakedditAcquisitionError(f"Task 27 manifest does not exist: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        sample = EvaluationSample.model_validate(record)
                    except Exception as error:
                        raise FakedditAcquisitionError(
                            f"invalid Task 27 record at {path}:{line_number}: {error}"
                        ) from error
                    if sample.split != split:
                        raise FakedditAcquisitionError(
                            f"manifest split mismatch at {path}:{line_number}"
                        )
                    source_url = sample.metadata.get("image_reference") or sample.image
                    if not isinstance(source_url, str) or not source_url.strip():
                        raise FakedditAcquisitionError(
                            f"missing source image URL at {path}:{line_number}"
                        )
                    if isinstance(sample.image, str) and sample.image != source_url:
                        raise FakedditAcquisitionError(
                            f"image and image_reference disagree at {path}:{line_number}"
                        )
                    normalized_url = normalize_image_url(source_url)
                    preparation = sample.metadata.get("preparation") or {}
                    if preparation.get("version"):
                        versions.add(str(preparation["version"]))
                    targets.append(_Target(
                        split=split,
                        record=record,
                        source_url=source_url,
                        normalized_url=normalized_url,
                        sample_id=sample.sample_id,
                        label=sample.label,
                    ))
        except OSError as error:
            raise FakedditAcquisitionError(f"unable to read manifest {path}: {error}") from error
    return targets, sorted(versions)


def _unique_url_targets(targets: List[_Target]) -> List[_Target]:
    first_by_url = {}
    for target in targets:
        first_by_url.setdefault(target.normalized_url, target)
    return [first_by_url[url] for url in sorted(first_by_url)]


def _limit_targets(targets: List[_Target], max_samples: Optional[int]) -> List[_Target]:
    if max_samples is None:
        return targets
    if max_samples < 1:
        raise FakedditAcquisitionError("--max-samples must be a positive integer")
    split_targets = {
        split: [target for target in targets if target.split == split]
        for split in SPLITS
    }
    target_count = min(max_samples, len(targets))
    quotas = {split: 0 for split in SPLITS}
    while sum(quotas.values()) < target_count:
        progressed = False
        for split in SPLITS:
            if quotas[split] < len(split_targets[split]):
                quotas[split] += 1
                progressed = True
                if sum(quotas.values()) == target_count:
                    break
        if not progressed:
            break

    selected = []
    split_positions = {split: 0 for split in SPLITS}
    for target in targets:
        split_positions[target.split] += 1
        if split_positions[target.split] <= quotas[target.split]:
            selected.append(target)
    return selected


def _acquire_unique_targets(
    targets: List[_Target],
    images_dir: Path,
    output_dir: Path,
    client: httpx.Client,
    config: FakedditAcquisitionConfig,
    budget: _ByteBudget,
    previous_metadata,
    robots_policy,
    progress: bool,
) -> Dict[str, _ImageResult]:
    results: Dict[str, _ImageResult] = {}
    resume_lock = threading.Lock()
    if not targets:
        return results
    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        futures = {
            executor.submit(
                _acquire_one,
                target,
                images_dir,
                output_dir,
                client,
                config,
                budget,
                previous_metadata.get(target.normalized_url),
                resume_lock,
                robots_policy,
            ): target.normalized_url
            for target in targets
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            normalized_url = futures[future]
            try:
                results[normalized_url] = future.result()
            except Exception as error:
                logger.exception("unexpected image acquisition error", extra={"url_hash": _url_hash(normalized_url)})
                results[normalized_url] = _ImageResult(
                    source_url=next(item.source_url for item in targets if item.normalized_url == normalized_url),
                    normalized_url=normalized_url,
                    status="connection_error",
                    error=str(error),
                )
            if progress and (completed % config.progress_interval == 0 or completed == len(targets)):
                counts = Counter(item.status for item in results.values())
                print(
                    f"[{completed}/{len(targets)}] downloaded={counts['downloaded']} "
                    f"already_present={counts['already_present']} failed={sum(count for status, count in counts.items() if status not in SUCCESS_STATUSES)}",
                    flush=True,
                )
    return results


def _acquire_one(
    target: _Target,
    images_dir: Path,
    output_dir: Path,
    client: httpx.Client,
    config: FakedditAcquisitionConfig,
    budget: _ByteBudget,
    prior: Optional[Dict[str, object]],
    resume_lock: threading.Lock,
    robots_policy: _RobotsPolicy,
) -> _ImageResult:
    result = _ImageResult(
        source_url=target.source_url,
        normalized_url=target.normalized_url,
        status="connection_error",
    )
    if config.resume:
        resumed = _reuse_existing_image(
            target, images_dir, output_dir, config, budget, prior, resume_lock
        )
        if resumed and resumed.local_path:
            return resumed
        if resumed:
            result.replaced_corrupt_existing = resumed.replaced_corrupt_existing

    request_url_error = _validate_source_url(target.normalized_url)
    if request_url_error:
        result.status = "invalid_url"
        result.error = request_url_error
        return result
    robots_allowed, robots_error = robots_policy.check(target.normalized_url)
    if not robots_allowed:
        result.status = "robots_disallowed" if robots_error == "robots.txt disallows this URL" else "robots_unavailable"
        result.error = robots_error
        return result

    temporary_path: Optional[Path] = None
    written = 0
    next_retry_delay = 0.0
    for attempt in range(1, config.max_retries + 2):
        result.attempts = attempt
        if attempt > 1:
            time.sleep(next_retry_delay)
            next_retry_delay = 0.0
        _request_delay(config)
        retry_status = None
        retry_after = None
        try:
            with client.stream("GET", target.source_url) as response:
                result.http_status = response.status_code
                if response.status_code not in range(200, 300):
                    retry_status = response.status_code
                    retry_after = response.headers.get("retry-after")
                    if response.status_code not in RETRYABLE_HTTP_STATUSES or attempt > config.max_retries:
                        result.status = "http_error"
                        result.error = f"HTTP {response.status_code}"
                        return result
                else:
                    content_type = response.headers.get("content-type")
                    result.content_type = content_type.split(";", 1)[0].strip().lower() if content_type else None
                    if result.content_type and not result.content_type.startswith("image/"):
                        result.status = "invalid_content_type"
                        result.error = f"response Content-Type was {result.content_type}"
                        return result
                    declared_length = _content_length(response.headers.get("content-length"))
                    if declared_length is not None and declared_length > config.max_image_bytes:
                        result.status = "oversized"
                        result.error = f"Content-Length {declared_length} exceeds max_image_bytes"
                        return result
                    file_descriptor, temporary_name = tempfile.mkstemp(
                        prefix=f"{_url_hash(target.normalized_url)}-",
                        suffix=".part",
                        dir=images_dir,
                    )
                    temporary_path = Path(temporary_name)
                    digest = hashlib.sha256()
                    written = 0
                    try:
                        with os.fdopen(file_descriptor, "wb") as output:
                            for chunk in response.iter_bytes(config.chunk_bytes):
                                if not chunk:
                                    continue
                                if written + len(chunk) > config.max_image_bytes:
                                    raise _AcquisitionFailure("oversized", "stream exceeded max_image_bytes")
                                budget.reserve(len(chunk))
                                try:
                                    output.write(chunk)
                                except OSError:
                                    budget.release_in_flight(len(chunk))
                                    raise
                                written += len(chunk)
                                digest.update(chunk)
                                _check_free_space(images_dir, config, len(chunk))
                    except _StorageBudgetExceeded as error:
                        raise _AcquisitionFailure("storage_budget_exceeded", str(error)) from error
                    if written == 0:
                        raise _AcquisitionFailure("empty_response", "response body was empty")
                    image_info = _inspect_image(temporary_path, config)
                    file_digest = image_info["sha256"]
                    if digest.hexdigest() != file_digest:
                        raise _AcquisitionFailure("checksum_error", "stream and file checksums differ")
                    image_format = image_info["format"]
                    final_path = images_dir / stable_image_filename(target.normalized_url, image_format)
                    replaced_size = final_path.stat().st_size if final_path.is_file() else 0
                    os.replace(temporary_path, final_path)
                    temporary_path = None
                    budget.commit(written)
                    if replaced_size:
                        budget.release_committed(replaced_size)
                    result.status = "downloaded"
                    result.local_path = final_path
                    result.file_size_bytes = written
                    result.width = image_info["width"]
                    result.height = image_info["height"]
                    result.sha256 = file_digest
                    result.detected_format = image_format
                    return result
            if retry_status in RETRYABLE_HTTP_STATUSES and attempt <= config.max_retries:
                next_retry_delay = _retry_delay(config, attempt, retry_status, retry_after)
                continue
        except _AcquisitionFailure as error:
            result.status = error.status
            result.error = str(error)
            if error.status in {"timeout", "connection_error"} and attempt <= config.max_retries:
                time.sleep(_retry_delay(config, attempt, None, None))
                continue
            return result
        except httpx.TimeoutException as error:
            result.status = "timeout"
            result.error = str(error) or "request timed out"
            if attempt <= config.max_retries:
                next_retry_delay = _retry_delay(config, attempt, None, None)
                continue
            return result
        except httpx.HTTPError as error:
            result.status = "connection_error"
            result.error = str(error)
            if attempt <= config.max_retries:
                next_retry_delay = _retry_delay(config, attempt, None, None)
                continue
            return result
        except OSError as error:
            result.status = "connection_error"
            result.error = str(error)
            return result
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
                budget.release_in_flight(written)
                temporary_path = None
                written = 0
    return result


def _reuse_existing_image(target, images_dir, output_dir, config, budget, prior, resume_lock):
    existing = _ImageResult(
        source_url=target.source_url,
        normalized_url=target.normalized_url,
        status="already_present",
    )
    with resume_lock:
        previous_path = _prior_image_path(prior, output_dir)
        candidate_paths = [previous_path] if previous_path else []
        candidate_paths.extend(images_dir.glob(f"{_url_hash(target.normalized_url)}.*"))
        seen_paths = set()
        for candidate in candidate_paths:
            if not candidate or candidate in seen_paths or not candidate.is_file():
                continue
            seen_paths.add(candidate)
            try:
                image_info = _inspect_image(candidate, config)
            except _AcquisitionFailure:
                file_size = candidate.stat().st_size
                candidate.unlink(missing_ok=True)
                budget.release_committed(file_size)
                existing.replaced_corrupt_existing = True
                continue
            existing.local_path = candidate
            existing.file_size_bytes = candidate.stat().st_size
            existing.width = image_info["width"]
            existing.height = image_info["height"]
            existing.detected_format = image_info["format"]
            existing.sha256 = image_info["sha256"]
            existing.http_status = _prior_value(prior, "http_status")
            existing.content_type = _prior_value(prior, "content_type")
            return existing
    return existing if existing.replaced_corrupt_existing else None


def _inspect_image(path: Path, config: FakedditAcquisitionConfig):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                if image_format not in SUPPORTED_IMAGE_FORMATS:
                    raise _AcquisitionFailure("unsupported_image", f"unsupported image format: {image_format or 'unknown'}")
                if width < 1 or height < 1 or max(width, height) > config.max_dimension or width * height > config.max_pixels:
                    raise _AcquisitionFailure("excessive_dimensions", f"image dimensions {width}x{height} exceed configured limits")
                image.verify()
            with Image.open(path) as image:
                image.load()
                if image.size != (width, height):
                    raise _AcquisitionFailure("invalid_image", "decoded dimensions changed during validation")
        return {
            "format": image_format,
            "width": width,
            "height": height,
            "sha256": _file_sha256(path),
        }
    except _AcquisitionFailure:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise _AcquisitionFailure("excessive_dimensions", str(error)) from error
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise _AcquisitionFailure("invalid_image", str(error) or "image decoder rejected response") from error


def _deduplicate_content(results: Dict[str, _ImageResult], images_dir: Path, budget: _ByteBudget) -> None:
    by_checksum = defaultdict(list)
    for result in results.values():
        if result.status in SUCCESS_STATUSES and result.sha256 and result.local_path:
            by_checksum[result.sha256].append(result)
    for group in by_checksum.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda result: result.normalized_url)
        canonical = group[0]
        canonical_path = images_dir / stable_image_filename(
            canonical.normalized_url, canonical.detected_format or ""
        )
        if canonical.local_path != canonical_path:
            if canonical_path.exists():
                old_size = canonical.local_path.stat().st_size
                canonical.local_path.unlink(missing_ok=True)
                budget.release_committed(old_size)
            else:
                os.replace(canonical.local_path, canonical_path)
        canonical.local_path = canonical_path
        for duplicate in group[1:]:
            if duplicate.local_path and duplicate.local_path != canonical_path and duplicate.local_path.exists():
                duplicate_size = duplicate.local_path.stat().st_size
                duplicate.local_path.unlink()
                budget.release_committed(duplicate_size)
            duplicate.duplicate_content_of = canonical.source_url
            duplicate.local_path = canonical_path


def _build_acquired_manifests(targets, results, output_dir):
    records = {split: [] for split in SPLITS}
    for target in targets:
        result = results[target.normalized_url]
        record = target.record
        metadata = dict(record.get("metadata") or {})
        relative_path = None
        if result.local_path:
            relative_path = result.local_path.relative_to(output_dir).as_posix()
        metadata["local_image_path"] = relative_path
        metadata["acquisition"] = {
            "acquisition_version": ACQUISITION_VERSION,
            "acquisition_status": result.status,
            "http_status": result.http_status,
            "content_type": result.content_type,
            "file_size_bytes": result.file_size_bytes,
            "width": result.width,
            "height": result.height,
            "sha256": result.sha256,
            "detected_format": result.detected_format,
            "acquisition_attempts": result.attempts,
            "source_url": target.source_url,
            "normalized_url": target.normalized_url,
            "local_image_path": relative_path,
            "error": result.error,
            "duplicate_content_of": result.duplicate_content_of,
            "replaced_corrupt_existing": result.replaced_corrupt_existing,
        }
        updated = dict(record)
        updated["metadata"] = metadata
        records[target.split].append(updated)
    return records


def _build_report(
    manifests,
    targets,
    unique_targets,
    results,
    acquired_manifests,
    output_dir,
    config,
    available_bytes,
    preparation_versions,
    max_samples,
    total_manifest_records,
):
    per_split = {}
    per_class = {}
    for split in SPLITS:
        split_targets = [target for target in targets if target.split == split]
        split_statuses = [results[target.normalized_url].status for target in split_targets]
        per_split[split.value] = {
            "requested": len(split_targets),
            "successful": sum(status in SUCCESS_STATUSES for status in split_statuses),
            "failed": sum(status not in SUCCESS_STATUSES for status in split_statuses),
            "status_counts": dict(sorted(Counter(split_statuses).items())),
        }
    for label in GroundTruthLabel:
        label_targets = [target for target in targets if target.label == label]
        statuses = [results[target.normalized_url].status for target in label_targets]
        per_class[label.value] = {
            "requested": len(label_targets),
            "successful": sum(status in SUCCESS_STATUSES for status in statuses),
            "failed": sum(status not in SUCCESS_STATUSES for status in statuses),
            "status_counts": dict(sorted(Counter(statuses).items())),
        }

    sample_statuses = [results[target.normalized_url].status for target in targets]
    unique_results = list(results.values())
    failures = [
        {
            "source_url": result.source_url,
            "normalized_url": result.normalized_url,
            "status": result.status,
            "http_status": result.http_status,
            "error": result.error,
            "attempts": result.attempts,
        }
        for result in sorted(unique_results, key=lambda item: item.normalized_url)
        if result.status not in SUCCESS_STATUSES
    ]
    host_counts = Counter(urlparse(target.normalized_url).hostname or "" for target in targets)
    local_files = {
        result.local_path for result in unique_results
        if result.local_path and result.local_path.is_file()
    }
    unique_file_bytes = sum(path.stat().st_size for path in local_files)
    duplicate_content_urls = sum(bool(result.duplicate_content_of) for result in unique_results)
    status_counts = Counter(sample_statuses)
    return {
        "acquisition_version": ACQUISITION_VERSION,
        "dataset": "fakeddit",
        "task27_preparation_version": preparation_versions[0] if len(preparation_versions) == 1 else preparation_versions,
        "input_manifests": {split.value: str(manifests[split]) for split in SPLITS},
        "output_directory": str(output_dir),
        "selection": {
            "mode": "bounded_smoke_test" if max_samples is not None else "full_manifests",
            "max_samples": max_samples,
            "total_manifest_records": total_manifest_records,
            "selected_records": len(targets),
            "selected_by_split": {split: values["requested"] for split, values in per_split.items()},
            "ordering": "first records per split, allocated round-robin train/validation/test; original manifest order retained",
        },
        "configuration": _config_dict(config),
        "counts": {
            "total_requested": len(targets),
            "unique_normalized_urls_requested": len(unique_targets),
            "successful": sum(status in SUCCESS_STATUSES for status in sample_statuses),
            "failed": sum(status not in SUCCESS_STATUSES for status in sample_statuses),
            "already_present": status_counts["already_present"],
            "downloaded_successfully": status_counts["downloaded"],
            "http_errors": status_counts["http_error"],
            "timeout_errors": status_counts["timeout"],
            "invalid_images": status_counts["invalid_image"],
            "invalid_content_type": status_counts["invalid_content_type"],
            "robots_disallowed": status_counts["robots_disallowed"],
            "robots_unavailable": status_counts["robots_unavailable"],
            "empty_responses": status_counts["empty_response"],
            "oversized": status_counts["oversized"],
            "excessive_dimensions": status_counts["excessive_dimensions"],
            "unsupported_images": status_counts["unsupported_image"],
            "storage_budget_exceeded": status_counts["storage_budget_exceeded"],
            "duplicate_content_urls": duplicate_content_urls,
            "unique_local_files": len(local_files),
            "unique_local_bytes": unique_file_bytes,
            "unique_content_sha256_count": len({result.sha256 for result in unique_results if result.sha256}),
        },
        "per_split": per_split,
        "per_class": per_class,
        "host_counts": dict(sorted(host_counts.items())),
        "available_disk_bytes_at_start": available_bytes,
        "total_successful_bytes": sum(
            result.file_size_bytes for result in unique_results
            if result.status in SUCCESS_STATUSES
        ),
        "failures": failures,
        "image_acquisition": "source URLs only; no discovery, crawling, or sample replacement",
        "training_or_evaluation": "not_performed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _dry_run_report(
    manifests,
    targets,
    unique_targets,
    output_dir,
    config,
    available_bytes,
    preparation_versions,
    max_samples,
    total_manifest_records,
):
    per_split = {}
    per_class = {}
    for split in SPLITS:
        per_split[split.value] = {
            "requested": sum(target.split == split for target in targets),
        }
    for label in GroundTruthLabel:
        per_class[label.value] = {
            "requested": sum(target.label == label for target in targets),
        }
    return {
        "dry_run": True,
        "acquisition_version": ACQUISITION_VERSION,
        "dataset": "fakeddit",
        "task27_preparation_version": preparation_versions[0] if len(preparation_versions) == 1 else preparation_versions,
        "input_manifests": {split.value: str(manifests[split]) for split in SPLITS},
        "output_directory": str(output_dir),
        "selection": {
            "mode": "bounded_smoke_test" if max_samples is not None else "full_manifests",
            "max_samples": max_samples,
            "total_manifest_records": total_manifest_records,
            "selected_records": len(targets),
            "selected_by_split": {split: values["requested"] for split, values in per_split.items()},
            "ordering": "first records per split, allocated round-robin train/validation/test; original manifest order retained",
        },
        "configuration": _config_dict(config),
        "total_requested": len(targets),
        "unique_normalized_urls_requested": len(unique_targets),
        "duplicate_manifest_url_rows": len(targets) - len(unique_targets),
        "per_split": per_split,
        "per_class": per_class,
        "available_disk_bytes": available_bytes,
        "estimated_storage_bytes": None,
        "storage_estimate_note": "exact image sizes require network requests; dry-run made none",
        "max_total_bytes": config.max_total_bytes,
        "network_requests_made": 0,
        "files_created": 0,
    }


def _config_dict(config):
    return {
        "concurrency": config.concurrency,
        "connect_timeout_seconds": config.connect_timeout,
        "read_timeout_seconds": config.read_timeout,
        "max_retries": config.max_retries,
        "backoff_factor": config.backoff_factor,
        "max_backoff_seconds": config.max_backoff_seconds,
        "max_retry_after_seconds": config.max_retry_after_seconds,
        "max_image_bytes": config.max_image_bytes,
        "max_dimension": config.max_dimension,
        "max_pixels": config.max_pixels,
        "max_total_bytes": config.max_total_bytes,
        "request_delay_seconds": config.request_delay_seconds,
        "request_jitter_seconds": config.request_jitter_seconds,
        "disk_reserve_bytes": config.disk_reserve_bytes,
        "user_agent": config.user_agent,
        "resume": config.resume,
    }


def _previous_acquisition_metadata(output_dir: Path):
    previous = {}
    for split in SPLITS:
        path = output_dir / "acquired" / f"{split.value}.jsonl"
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    acquisition = (record.get("metadata") or {}).get("acquisition") or {}
                    normalized = acquisition.get("normalized_url")
                    local_image_path = (
                        (record.get("metadata") or {}).get("local_image_path")
                        or acquisition.get("local_image_path")
                    )
                    if normalized and local_image_path:
                        previous[normalized] = {**acquisition, "local_image_path": local_image_path}
        except (OSError, json.JSONDecodeError):
            logger.warning("unable to read previous acquired manifest", extra={"path": str(path)})
    return previous


def _prior_image_path(prior, output_dir):
    if not prior:
        return None
    value = prior.get("local_image_path")
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else output_dir / path


def _prior_value(prior, key):
    return prior.get(key) if prior else None


def _validate_source_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "URL must use HTTP(S) and include a hostname"
    if parsed.username or parsed.password:
        return "URLs containing embedded credentials are not allowed"
    return None


def _content_length(value):
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _retry_delay(config, attempt, http_status, retry_after):
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                seconds = 0
        if seconds > 0:
            return min(seconds, config.max_retry_after_seconds)
    exponential = config.backoff_factor * (2 ** max(0, attempt - 1))
    return min(exponential, config.max_backoff_seconds)


def _request_delay(config):
    delay = config.request_delay_seconds
    if config.request_jitter_seconds:
        delay += random.uniform(0, config.request_jitter_seconds)
    if delay > 0:
        time.sleep(delay)


def _check_free_space(directory: Path, config: FakedditAcquisitionConfig, next_chunk_size: int):
    free_bytes = shutil.disk_usage(directory).free
    if free_bytes - next_chunk_size < config.disk_reserve_bytes:
        raise _AcquisitionFailure("storage_budget_exceeded", "disk safety reserve would be crossed")


def _available_bytes(path: Path) -> int:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return shutil.disk_usage(candidate).free


def _image_directory_bytes(images_dir: Path) -> int:
    if not images_dir.is_dir():
        return 0
    return sum(
        path.stat().st_size
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def _remove_stale_parts(images_dir: Path):
    for part in images_dir.glob("*.part"):
        part.unlink(missing_ok=True)


def _url_hash(normalized_url):
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_jsonl(path, records):
    temporary = path.with_name(path.name + ".part")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_write_json(path, record):
    temporary = path.with_name(path.name + ".part")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", type=Path, default=Path("data/research/fakeddit/train.jsonl"))
    parser.add_argument("--validation-manifest", type=Path, default=Path("data/research/fakeddit/validation.jsonl"))
    parser.add_argument("--test-manifest", type=Path, default=Path("data/research/fakeddit/test.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/research/fakeddit"))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=None, help="set both connect and read timeout")
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--read-timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3, help="retries after the first attempt")
    parser.add_argument("--max-image-bytes", type=int, default=15 * 1024 * 1024)
    parser.add_argument("--max-dimension", type=int, default=20_000)
    parser.add_argument("--max-pixels", type=int, default=25_000_000)
    parser.add_argument("--max-total-bytes", type=int, default=20 * 1024 * 1024 * 1024)
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="bounded smoke test: acquire at most this many first-in-manifest records, distributed round-robin across splits",
    )
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--request-delay", type=float, default=0.1)
    parser.add_argument("--request-jitter", type=float, default=0.1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.timeout is not None:
        args.connect_timeout = args.timeout
        args.read_timeout = args.timeout
    try:
        config = FakedditAcquisitionConfig(
            concurrency=args.concurrency,
            connect_timeout=args.connect_timeout,
            read_timeout=args.read_timeout,
            max_retries=args.max_retries,
            max_image_bytes=args.max_image_bytes,
            max_dimension=args.max_dimension,
            max_pixels=args.max_pixels,
            max_total_bytes=args.max_total_bytes,
            user_agent=args.user_agent,
            request_delay_seconds=args.request_delay,
            request_jitter_seconds=args.request_jitter,
            resume=args.resume,
        )
        if not args.quiet:
            configure_logging(args.log_level)
        report = acquire_fakeddit_images(
            args.train_manifest,
            args.validation_manifest,
            args.test_manifest,
            output_dir=args.output_dir,
            config=config,
            dry_run=args.dry_run,
            max_samples=args.max_samples,
            progress=not args.quiet and not args.dry_run,
        )
    except (FakedditAcquisitionError, FakedditPreparationError, OSError, httpx.HTTPError) as error:
        print(f"Fakeddit acquisition failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())