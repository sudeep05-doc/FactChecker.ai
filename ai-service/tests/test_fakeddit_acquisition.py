import hashlib
import io
import json
import time
from collections import Counter
from pathlib import Path

import httpx
import pytest
from PIL import Image

import app.evaluation.fakeddit_acquisition as acquisition_module
from app.evaluation.datasets import load_jsonl
from app.evaluation.fakeddit_acquisition import (
    FakedditAcquisitionError,
    FakedditAcquisitionConfig,
    acquire_fakeddit_images,
    stable_image_filename,
)
from app.evaluation.schemas import DatasetSplit


def encoded_image(color=(255, 0, 0), size=(8, 6), format="JPEG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format=format)
    return buffer.getvalue()


def sample(sample_id, label="FAKE", split="train", url=None):
    source_url = url or f"https://images.example/{sample_id}.jpg"
    return {
        "sample_id": sample_id,
        "label": label,
        "text": f"claim for {sample_id}",
        "image": source_url,
        "split": split,
        "source_reference": sample_id,
        "metadata": {
            "dataset": "fakeddit",
            "image_reference": source_url,
            "source_id": sample_id,
            "source_label": "0" if label == "FAKE" else "1",
            "preparation": {"version": "fakeddit-research-subset-v1", "seed": 42},
        },
    }


def write_manifests(root: Path, *, train=(), validation=(), test=()):
    root.mkdir(parents=True, exist_ok=True)
    for split, rows in (("train", train), ("validation", validation), ("test", test)):
        with (root / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
            for record in rows:
                handle.write(json.dumps(record) + "\n")
    return root


def config(**overrides):
    values = {
        "connect_timeout": 1,
        "read_timeout": 1,
        "max_retries": 0,
        "backoff_factor": 0,
        "max_backoff_seconds": 0,
        "max_retry_after_seconds": 0,
        "max_image_bytes": 1024 * 1024,
        "max_dimension": 1000,
        "max_pixels": 1_000_000,
        "max_total_bytes": 10 * 1024 * 1024,
        "request_delay_seconds": 0,
        "request_jitter_seconds": 0,
        "disk_reserve_bytes": 0,
        "progress_interval": 1,
    }
    values.update(overrides)
    return FakedditAcquisitionConfig(**values)


def run_acquisition(
    tmp_path,
    handler,
    *,
    train=None,
    validation=None,
    test=None,
    settings=None,
    dry_run=False,
    max_samples=None,
):
    manifests_dir = write_manifests(
        tmp_path / "source",
        train=train or (),
        validation=validation or (),
        test=test or (),
    )
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    try:
        report = acquire_fakeddit_images(
            manifests_dir / "train.jsonl",
            manifests_dir / "validation.jsonl",
            manifests_dir / "test.jsonl",
            output_dir=tmp_path / "research",
            config=settings or config(),
            dry_run=dry_run,
            max_samples=max_samples,
            http_client=client,
            progress=False,
        )
    finally:
        client.close()
    return report, manifests_dir, tmp_path / "research"


def image_response(content=None, *, content_type="image/jpeg", status=200, headers=None):
    response_headers = {"content-type": content_type}
    response_headers.update(headers or {})
    return httpx.Response(status, headers=response_headers, content=content if content is not None else encoded_image())


def test_successful_download_validates_checksums_and_preserves_source_fields(tmp_path):
    content = encoded_image()
    report, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(content),
        train=[sample("one")],
    )

    record = json.loads((output / "acquired/train.jsonl").read_text().splitlines()[0])
    acquisition = record["metadata"]["acquisition"]
    local_path = output / record["metadata"]["local_image_path"]
    assert acquisition["acquisition_status"] == "downloaded"
    assert acquisition["sha256"] == hashlib.sha256(content).hexdigest()
    assert acquisition["detected_format"] == "JPEG"
    assert acquisition["width"] == 8 and acquisition["height"] == 6
    assert acquisition["file_size_bytes"] == len(content)
    assert record["image"].startswith("https://images.example/")
    assert record["text"] == "claim for one"
    assert record["sample_id"] == "one"
    assert local_path.is_file()
    assert report["counts"]["downloaded_successfully"] == 1


def test_redirect_is_followed_and_final_http_status_recorded(tmp_path):
    content = encoded_image()

    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://images.example/final"})
        return image_response(content)

    report, _, output = run_acquisition(
        tmp_path, handler, train=[sample("redirect", url="https://images.example/start")]
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["http_status"] == 200
    assert report["counts"]["successful"] == 1


def test_http_404_is_permanent_and_not_retried(tmp_path):
    calls = Counter()

    def handler(request):
        calls[request.url.path] += 1
        return httpx.Response(404)

    report, _, output = run_acquisition(
        tmp_path,
        handler,
        train=[sample("missing")],
        settings=config(max_retries=3),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert calls["/missing.jpg"] == 1
    assert record["metadata"]["acquisition"]["acquisition_status"] == "http_error"
    assert record["metadata"]["acquisition"]["acquisition_attempts"] == 1
    assert report["counts"]["http_errors"] == 1


@pytest.mark.parametrize("status", [429, 503])
def test_retryable_http_status_is_retried(tmp_path, status):
    calls = Counter()
    content = encoded_image()

    def handler(request):
        calls[request.url.path] += 1
        if calls[request.url.path] == 1:
            return httpx.Response(status, headers={"retry-after": "0"})
        return image_response(content)

    _, _, output = run_acquisition(
        tmp_path,
        handler,
        train=[sample("retry")],
        settings=config(max_retries=1),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert calls["/retry.jpg"] == 2
    assert record["metadata"]["acquisition"]["acquisition_status"] == "downloaded"
    assert record["metadata"]["acquisition"]["acquisition_attempts"] == 2


def test_retry_after_is_honored_once_and_capped(tmp_path, monkeypatch):
    calls = Counter()
    delays = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls[request.url.path] += 1
        if calls[request.url.path] == 1:
            return httpx.Response(429, headers={"retry-after": "10"})
        return image_response()

    monkeypatch.setattr(acquisition_module.time, "sleep", delays.append)
    run_acquisition(
        tmp_path,
        handler,
        train=[sample("retry-after")],
        settings=config(max_retries=1, max_retry_after_seconds=2),
    )
    assert calls["/retry-after.jpg"] == 2
    assert delays == [2]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (httpx.ReadTimeout("read timeout"), "timeout"),
        (httpx.ConnectError("connection reset"), "connection_error"),
    ],
)
def test_timeout_and_connection_failures_are_bounded(tmp_path, error, expected_status):
    calls = Counter()

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls[request.url.path] += 1
        raise error

    report, _, output = run_acquisition(
        tmp_path,
        handler,
        train=[sample("network-error")],
        settings=config(max_retries=1),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert calls["/network-error.jpg"] == 2
    assert record["metadata"]["acquisition"]["acquisition_status"] == expected_status
    assert report["counts"]["failed"] == 1


@pytest.mark.parametrize(
    ("content", "content_type", "expected_status"),
    [
        (b"<html>blocked</html>", "text/html", "invalid_content_type"),
        (b"<html>blocked</html>", "image/jpeg", "invalid_image"),
        (b"", "image/jpeg", "empty_response"),
        (b"truncated image bytes", "image/jpeg", "invalid_image"),
    ],
)
def test_invalid_responses_are_visible_and_never_stored(tmp_path, content, content_type, expected_status):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(content, content_type=content_type),
        train=[sample("bad-image")],
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == expected_status
    assert record["metadata"]["local_image_path"] is None
    assert list((output / "images").iterdir()) == []


def test_unsupported_format_is_rejected(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(encoded_image(format="GIF"), content_type="image/gif"),
        train=[sample("gif")],
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "unsupported_image"


def test_content_length_and_streaming_size_limits(tmp_path):
    declared_report, _, declared_output = run_acquisition(
        tmp_path / "declared",
        lambda request: image_response(encoded_image(), headers={"content-length": "1000"}),
        train=[sample("declared")],
        settings=config(max_image_bytes=100),
    )
    streamed_report, _, streamed_output = run_acquisition(
        tmp_path / "streamed",
        lambda request: image_response(encoded_image(), headers={"content-length": "10"}),
        train=[sample("streamed")],
        settings=config(max_image_bytes=100),
    )
    declared = json.loads((declared_output / "acquired/train.jsonl").read_text())
    streamed = json.loads((streamed_output / "acquired/train.jsonl").read_text())
    assert declared["metadata"]["acquisition"]["acquisition_status"] == "oversized"
    assert streamed["metadata"]["acquisition"]["acquisition_status"] == "oversized"
    assert declared_report["counts"]["oversized"] == streamed_report["counts"]["oversized"] == 1


def test_excessive_pixel_count_is_rejected_before_decode(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(encoded_image(size=(20, 20))),
        train=[sample("large-dimensions")],
        settings=config(max_pixels=100),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "excessive_dimensions"


def test_max_dimension_limit_is_enforced(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(encoded_image(size=(20, 2))),
        train=[sample("wide")],
        settings=config(max_dimension=10),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "excessive_dimensions"


def test_filename_is_stable_and_uses_detected_format_extension():
    url = "https://example.com/image?width=320"
    first = stable_image_filename(url, "JPEG")
    second = stable_image_filename(url, "jpeg")
    assert first == second
    assert first == hashlib.sha256(url.encode()).hexdigest() + ".jpg"
    assert stable_image_filename(url, "PNG").endswith(".png")


def test_identical_image_bytes_from_different_urls_share_one_file(tmp_path):
    content = encoded_image()
    report, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(content),
        train=[sample("a", url="https://images.example/a"), sample("b", url="https://images.example/b")],
    )
    records = [json.loads(line) for line in (output / "acquired/train.jsonl").read_text().splitlines()]
    paths = [record["metadata"]["local_image_path"] for record in records]
    assert paths[0] == paths[1]
    assert len(list((output / "images").iterdir())) == 1
    assert report["counts"]["duplicate_content_urls"] == 1
    assert report["counts"]["unique_local_files"] == 1


def test_resume_reuses_prior_canonical_path_for_duplicate_content(tmp_path):
    content = encoded_image()
    rows = [
        sample("first", url="https://images.example/a"),
        sample("second", url="https://images.example/b"),
    ]
    run_acquisition(tmp_path, lambda request: image_response(content), train=rows)

    def must_not_request(request):
        raise AssertionError("resumed duplicate content should not be requested again")

    report, _, output = run_acquisition(tmp_path, must_not_request, train=rows)
    records = [json.loads(line) for line in (output / "acquired/train.jsonl").read_text().splitlines()]
    assert report["counts"]["already_present"] == 2
    assert {record["metadata"]["acquisition"]["acquisition_status"] for record in records} == {
        "already_present"
    }
    assert len(list((output / "images").iterdir())) == 1


def test_resume_reuses_existing_valid_file_without_request(tmp_path):
    content = encoded_image()
    run_acquisition(tmp_path, lambda request: image_response(content), train=[sample("resume")])

    def must_not_request(request):
        raise AssertionError("valid resumed image should not be requested again")

    report, manifests, output = run_acquisition(
        tmp_path,
        must_not_request,
        train=[sample("resume")],
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "already_present"
    assert record["metadata"]["acquisition"]["acquisition_attempts"] == 0
    assert report["counts"]["already_present"] == 1
    assert load_jsonl(output / "acquired/train.jsonl", DatasetSplit.TRAIN)[0].sample_id == "resume"
    assert manifests.exists()


def test_corrupt_existing_image_is_replaced_on_resume(tmp_path):
    old = encoded_image(color=(255, 0, 0))
    _, _, output = run_acquisition(tmp_path, lambda request: image_response(old), train=[sample("replace")])
    record = json.loads((output / "acquired/train.jsonl").read_text())
    existing = output / record["metadata"]["local_image_path"]
    existing.write_bytes(b"corrupted")
    new = encoded_image(color=(0, 255, 0))
    _, _, output = run_acquisition(tmp_path, lambda request: image_response(new), train=[sample("replace")])
    updated = json.loads((output / "acquired/train.jsonl").read_text())
    assert updated["metadata"]["acquisition"]["acquisition_status"] == "downloaded"
    assert updated["metadata"]["acquisition"]["replaced_corrupt_existing"] is True
    assert updated["metadata"]["acquisition"]["sha256"] == hashlib.sha256(new).hexdigest()
    assert not list((output / "images").glob("*.part"))


def test_failed_stream_removes_part_and_never_creates_final_image(tmp_path):
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"partial"
            raise httpx.ReadError("interrupted")

        def close(self):
            pass

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=BrokenStream())

    _, _, output = run_acquisition(tmp_path, handler, train=[sample("interrupted")])
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "connection_error"
    assert not list((output / "images").glob("*.part"))
    assert not list((output / "images").glob("*.jpg"))


def test_manifest_order_is_stable_despite_network_completion_order(tmp_path):
    content = encoded_image()

    def handler(request):
        if request.url.path.endswith("first.jpg"):
            time.sleep(0.03)
        return image_response(content)

    records = [sample("first"), sample("second"), sample("third")]
    _, _, output = run_acquisition(
        tmp_path,
        handler,
        train=records,
        settings=config(concurrency=3),
    )
    acquired = load_jsonl(output / "acquired/train.jsonl", DatasetSplit.TRAIN)
    assert [record.sample_id for record in acquired] == ["first", "second", "third"]


def test_deduplicated_manifest_url_is_requested_once(tmp_path):
    calls = Counter()

    def handler(request):
        calls[request.url.path] += 1
        return image_response()

    _, _, output = run_acquisition(
        tmp_path,
        handler,
        train=[
            sample("upper", url="https://EXAMPLE.com/shared"),
            sample("lower", url="https://example.com/shared"),
        ],
    )
    records = [json.loads(line) for line in (output / "acquired/train.jsonl").read_text().splitlines()]
    assert calls["/shared"] == 1
    assert records[0]["metadata"]["local_image_path"] == records[1]["metadata"]["local_image_path"]


def test_storage_budget_failure_is_reported_and_part_file_removed(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(encoded_image()),
        train=[sample("budget")],
        settings=config(max_total_bytes=10),
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "storage_budget_exceeded"
    assert not list((output / "images").glob("*.part"))


def test_report_has_per_split_and_per_class_counts_without_replacement(tmp_path):
    rows = [
        sample("fake-ok", "FAKE"),
        sample("fake-failed", "FAKE", url="https://images.example/fail"),
        sample("real-ok", "REAL"),
    ]

    def handler(request):
        if request.url.path == "/fail":
            return httpx.Response(404)
        return image_response()

    report, _, output = run_acquisition(
        tmp_path,
        handler,
        train=rows,
        validation=[sample("validation", "REAL", "validation")],
        settings=config(concurrency=2),
    )
    assert report["counts"]["total_requested"] == 4
    assert report["per_split"]["train"]["requested"] == 3
    assert report["per_split"]["train"]["successful"] == 2
    assert report["per_split"]["train"]["failed"] == 1
    assert report["per_class"]["FAKE"]["requested"] == 2
    assert report["per_class"]["FAKE"]["successful"] == 1
    assert report["per_class"]["FAKE"]["failed"] == 1
    assert report["selection"]["mode"] == "full_manifests"
    assert report["selection"]["max_samples"] is None
    assert len((output / "acquired/train.jsonl").read_text().splitlines()) == 3
    assert len((output / "acquired/validation.jsonl").read_text().splitlines()) == 1


def test_dry_run_reads_counts_without_network_or_filesystem_writes(tmp_path):
    manifests = write_manifests(
        tmp_path / "source",
        train=[sample("fake", "FAKE"), sample("true", "REAL")],
        validation=[sample("validation", "FAKE", "validation")],
        test=[sample("test", "REAL", "test")],
    )
    output = tmp_path / "not-created"
    client = httpx.Client(transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(AssertionError("network"))))
    try:
        report = acquire_fakeddit_images(
            manifests / "train.jsonl",
            manifests / "validation.jsonl",
            manifests / "test.jsonl",
            output_dir=output,
            config=config(),
            dry_run=True,
            http_client=client,
            progress=False,
        )
    finally:
        client.close()

    assert report["total_requested"] == 4
    assert report["per_split"] == {
        "train": {"requested": 2},
        "validation": {"requested": 1},
        "test": {"requested": 1},
    }
    assert report["per_class"]["FAKE"]["requested"] == 2
    assert report["per_class"]["REAL"]["requested"] == 2
    assert report["estimated_storage_bytes"] is None
    assert report["network_requests_made"] == report["files_created"] == 0
    assert not output.exists()


def test_bounded_acquisition_distributes_evenly_and_preserves_manifest_order(tmp_path):
    train_rows = [sample(f"train-{index}", "FAKE" if index % 2 == 0 else "REAL") for index in range(6)]
    validation_rows = [sample(f"validation-{index}", "REAL", "validation") for index in range(6)]
    test_rows = [sample(f"test-{index}", "FAKE", "test") for index in range(6)]
    original_manifests = write_manifests(
        tmp_path / "source",
        train=train_rows,
        validation=validation_rows,
        test=test_rows,
    )
    before = {
        split: (original_manifests / f"{split}.jsonl").read_bytes()
        for split in ("train", "validation", "test")
    }

    report, _, output = run_acquisition(
        tmp_path,
        lambda request: httpx.Response(404) if request.url.path == "/robots.txt" else image_response(),
        train=train_rows,
        validation=validation_rows,
        test=test_rows,
        max_samples=8,
    )

    selected_ids = {
        split: [record["sample_id"] for record in map(
            json.loads, (output / f"acquired/{split}.jsonl").read_text().splitlines()
        )]
        for split in ("train", "validation", "test")
    }
    assert selected_ids == {
        "train": ["train-0", "train-1", "train-2"],
        "validation": ["validation-0", "validation-1", "validation-2"],
        "test": ["test-0", "test-1"],
    }
    assert report["counts"]["total_requested"] == 8
    assert report["selection"]["mode"] == "bounded_smoke_test"
    assert report["selection"]["total_manifest_records"] == 18
    assert report["selection"]["selected_by_split"] == {"train": 3, "validation": 3, "test": 2}
    assert {
        split: (original_manifests / f"{split}.jsonl").read_bytes()
        for split in ("train", "validation", "test")
    } == before


def test_bounded_dry_run_is_deterministic_and_never_writes(tmp_path):
    train = [sample(f"train-{index}") for index in range(10)]
    validation = [sample(f"validation-{index}", split="validation") for index in range(10)]
    test = [sample(f"test-{index}", split="test") for index in range(10)]
    first, _, first_output = run_acquisition(
        tmp_path / "first",
        lambda request: (_ for _ in ()).throw(AssertionError("dry-run made a request")),
        train=train,
        validation=validation,
        test=test,
        max_samples=5,
        dry_run=True,
    )
    second, _, second_output = run_acquisition(
        tmp_path / "second",
        lambda request: (_ for _ in ()).throw(AssertionError("dry-run made a request")),
        train=train,
        validation=validation,
        test=test,
        max_samples=5,
        dry_run=True,
    )

    assert first["selection"] == second["selection"]
    assert first["selection"]["selected_by_split"] == {"train": 2, "validation": 2, "test": 1}
    assert first["total_requested"] == 5
    assert not first_output.exists()
    assert not second_output.exists()


def test_bounded_limit_above_population_preserves_full_manifest_behavior(tmp_path):
    train = [sample("train-0"), sample("train-1", "REAL")]
    validation = [sample("validation-0", split="validation")]
    test = [sample("test-0", split="test")]
    report, _, _ = run_acquisition(
        tmp_path,
        lambda request: httpx.Response(404) if request.url.path == "/robots.txt" else image_response(),
        train=train,
        validation=validation,
        test=test,
        max_samples=100,
    )
    assert report["counts"]["total_requested"] == 4
    assert report["selection"]["selected_by_split"] == {"train": 2, "validation": 1, "test": 1}


@pytest.mark.parametrize("max_samples", [0, -1])
def test_bounded_limit_must_be_positive(tmp_path, max_samples):
    train = [sample("train-0")]
    write_manifests(tmp_path / "source", train=train)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    try:
        with pytest.raises(FakedditAcquisitionError, match="positive integer"):
            acquire_fakeddit_images(
                tmp_path / "source/train.jsonl",
                tmp_path / "source/validation.jsonl",
                tmp_path / "source/test.jsonl",
                output_dir=tmp_path / "not-created",
                config=config(),
                max_samples=max_samples,
                http_client=client,
                progress=False,
            )
    finally:
        client.close()
    assert not (tmp_path / "not-created").exists()


def test_invalid_url_is_not_requested_and_failure_remains_in_manifest(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: (_ for _ in ()).throw(AssertionError("invalid URL was requested")),
        train=[sample("bad-url", url="file:///tmp/private.jpg")],
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert record["metadata"]["acquisition"]["acquisition_status"] == "invalid_url"


def test_robots_disallowed_image_is_not_requested_and_is_reported(tmp_path):
    requested_paths = []

    def handler(request):
        requested_paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"User-agent: *\nDisallow: /private\n",
            )
        return image_response()

    report, _, output = run_acquisition(
        tmp_path,
        handler,
        train=[sample("blocked", url="https://images.example/private/image.jpg")],
    )
    record = json.loads((output / "acquired/train.jsonl").read_text())
    assert requested_paths == ["/robots.txt"]
    assert record["metadata"]["acquisition"]["acquisition_status"] == "robots_disallowed"
    assert report["counts"]["robots_disallowed"] == 1


def test_task25_manifest_schema_accepts_acquisition_metadata(tmp_path):
    _, _, output = run_acquisition(
        tmp_path,
        lambda request: image_response(),
        train=[sample("compatible")],
    )
    loaded = load_jsonl(output / "acquired/train.jsonl", DatasetSplit.TRAIN)
    assert loaded[0].metadata["local_image_path"].startswith("images/")
    assert loaded[0].image.startswith("https://")