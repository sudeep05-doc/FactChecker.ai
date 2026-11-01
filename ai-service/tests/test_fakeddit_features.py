import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.fakeddit_features import (
    FeatureExtractionCache,
    FeatureExtractionConfig,
    _coerce_split,
    _is_complete_feature_artifact,
    _process_batch,
    _write_jsonl,
    build_feature_artifact,
    iter_acquired_records,
    reconcile_feature_checkpoint,
    run_feature_extraction,
)


class FakeTextEncoder:
    def __init__(self, *, model_name="text-model", device="cpu"):
        self.model_name = model_name
        self.device = device

    def to_usr_text(self, text, language=None):
        from app.usr.models import USREmbedding, USRText

        return USRText(
            text=text,
            language=language,
            embedding=USREmbedding(model_name=self.model_name, dimension=4, values=[1.0, 0.0, 0.0, 0.0], normalized=True),
            metadata={"modality": "text", "processing": {"device": self.device}},
        )


class FakeImageEncoder:
    def __init__(self, *, model_name="image-model", checkpoint="openai", device="cpu"):
        self.model_name = model_name
        self.checkpoint = checkpoint
        self.device = device

    def to_usr_image(self, image):
        from app.usr.models import USREmbedding, USRImage

        return USRImage(
            image_paths=[str(image)],
            embedding=USREmbedding(model_name=self.model_name, dimension=4, values=[0.0, 1.0, 0.0, 0.0], normalized=True),
            metadata={"modality": "image", "checkpoint": self.checkpoint, "processing": {"device": self.device}},
        )


def write_manifest(path: Path, *, split: str, count: int) -> None:
    records = []
    for index in range(count):
        records.append({
            "sample_id": f"{split}-{index:03d}",
            "split": split,
            "label": "REAL" if index % 2 == 0 else "FAKE",
            "text": f"sample text {index}",
            "metadata": {
                "local_image_path": f"images/{split}-{index:03d}.png",
                "acquisition": {"acquisition_status": "downloaded"},
            },
        })
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def write_acquired_records(root: Path, split: str, records: list[dict]) -> None:
    manifest = root / "acquired" / f"{split}.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    image_dir = root / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        local_image = (record.get("metadata") or {}).get("local_image_path")
        if local_image:
            (root / local_image).write_bytes(b"local image")
    manifest.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def acquired_sample(split: str, sample_id: str, *, status: str = "downloaded") -> dict:
    local_image = f"images/{sample_id}.jpg" if status == "downloaded" else None
    return {
        "sample_id": sample_id,
        "split": split,
        "label": "REAL",
        "text": f"title for {sample_id}",
        "metadata": {
            "local_image_path": local_image,
            "acquisition": {"acquisition_status": status},
        },
    }


def complete_artifact(sample: dict, config: FeatureExtractionConfig) -> dict:
    split = sample["split"]
    title = sample["text"]
    local_image = sample["metadata"]["local_image_path"]
    return {
        "sample_id": sample["sample_id"],
        "sample_identity": {"sample_id": sample["sample_id"], "source_reference": sample["sample_id"], "split": split},
        "split": split,
        "label": sample["label"],
        "clean_title": title,
        "text_provenance": {"clean_title": title, "language": "en", "model_name": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384, "normalized": True, "source": "SentenceTransformerTextEncoder.to_usr_text", "processing": {"batch_size": config.text_batch_size, "requested_device": config.device, "deterministic_inference": True, "normalized_embeddings": True, "chunking_strategy": "ordered_character_chunks_mean_normalized"}},
        "image_provenance": {"local_image_path": local_image, "source_url": None, "model_name": "ViT-B-32", "checkpoint": "openai", "dimension": 512, "normalized": True, "processing": {"batch_size": config.image_batch_size, "requested_device": config.device, "deterministic_inference": True, "normalized_embedding": True}},
        "feature_vector": [float(index) for index in range(20)],
        "feature_names": [f"feature-{index}" for index in range(20)],
        "feature_schema_version": "rr-decision-v1",
        "feature_cache_version": "fakeddit-feature-cache-v1",
        "configuration_hash": config.configuration_hash(),
        "configuration_fingerprint": config.configuration_fingerprint(),
        "configuration_fingerprint_version": "fakeddit-feature-config-v2",
        "model_metadata": {"text": {"model_name": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384}, "image": {"model_name": "ViT-B-32", "checkpoint": "openai", "dimension": 512}},
        "created_at": "2026-10-01T00:00:00+00:00",
    }


def install_fake_encoders(monkeypatch, module, build_calls: list[str]) -> None:
    class FakeBatchTextEncoder:
        def __init__(self, **kwargs):
            pass

        def encode_batch_with_chunking(self, texts, language="en"):
            return [SimpleNamespace(status=SimpleNamespace(value="available"), error_code=None) for _ in texts]

        def to_usr_text_from_result(self, text, result):
            return object()

    class FakeBatchImageEncoder:
        def __init__(self, **kwargs):
            pass

        def encode_batch(self, images):
            return [SimpleNamespace(encoding_status=SimpleNamespace(value="completed"), errors=[]) for _ in images]

        def to_usr_image_from_result(self, result):
            return object()

    monkeypatch.setattr(module, "SentenceTransformerTextEncoder", FakeBatchTextEncoder)
    monkeypatch.setattr(module, "OpenCLIPImageEncoder", FakeBatchImageEncoder)

    def build(sample, config, **kwargs):
        build_calls.append(sample["sample_id"])
        return complete_artifact(sample, config)

    monkeypatch.setattr(module, "build_feature_artifact", build)


def test_iter_acquired_records_reads_split_manifest_and_preserves_order(tmp_path: Path) -> None:
    split_dir = tmp_path / "acquired"
    split_dir.mkdir()
    write_manifest(split_dir / "train.jsonl", split="train", count=3)
    (tmp_path / "images").mkdir()
    for index in range(3):
        (tmp_path / "images" / f"train-{index:03d}.png").write_bytes(b"fake png")

    records = list(iter_acquired_records(tmp_path, split="train"))

    assert [record["sample_id"] for record in records] == ["train-000", "train-001", "train-002"]
    assert all(record["split"] == "train" for record in records)
    assert records[0]["metadata"]["local_image_path"] == "images/train-000.png"


def test_feature_cache_reuses_and_invalidates_configuration(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache = FeatureExtractionCache(cache_path)

    cache.put("sample-1", "hash-a", {"label": "REAL", "feature_vector": [1.0, 2.0]})
    assert cache.get("sample-1", "hash-a") is not None
    assert cache.get("sample-1", "hash-b") is None

    cache.put("sample-1", "hash-b", {"label": "REAL", "feature_vector": [3.0, 4.0]})
    assert cache.get("sample-1", "hash-b")["feature_vector"] == [3.0, 4.0]


def test_build_feature_artifact_uses_usr_cmref_rr_and_preserves_metadata(tmp_path: Path) -> None:
    sample = {
        "sample_id": "s1",
        "split": "test",
        "label": "REAL",
        "text": "A sample title",
        "image": "https://example.com/img.jpg",
        "metadata": {"local_image_path": "images/sample.png"},
    }
    image_path = tmp_path / "images"
    image_path.mkdir(parents=True, exist_ok=True)
    image_path.joinpath("sample.png").write_bytes(b"not a valid image")

    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", text_batch_size=2, image_batch_size=2, device="cpu")
    artifact = build_feature_artifact(
        sample,
        config,
        text_encoder=FakeTextEncoder(),
        image_encoder=FakeImageEncoder(),
    )

    assert artifact["sample_id"] == "s1"
    assert artifact["split"] == "test"
    assert artifact["label"] == "REAL"
    assert artifact["text_provenance"]["clean_title"] == "A sample title"
    assert artifact["image_provenance"]["local_image_path"].endswith("sample.png")
    assert len(artifact["feature_vector"]) > 0
    assert all(float(value) == value and value == value for value in artifact["feature_vector"])  # finite values
    assert artifact["feature_schema_version"]
    assert artifact["configuration_hash"]
    assert artifact["model_metadata"]["text"]["model_name"] == "text-model"
    assert artifact["model_metadata"]["image"]["model_name"] == "image-model"
    assert artifact["sample_identity"]["sample_id"] == "s1"
    assert len(artifact["feature_vector"]) == 20
    assert len(artifact["feature_names"]) == 20
    assert artifact["feature_vector"] == pytest.approx(artifact["feature_vector"])


class CountingBatchTextEncoder:
    def __init__(self, config: FeatureExtractionConfig, *, failure_text: str = ""):
        self.config = config
        self.failure_text = failure_text
        self.inference_count = 0

    def encode_batch_with_chunking(self, texts, language="en"):
        from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus

        values = list(texts)
        self.inference_count += len(values)
        results = []
        for text in values:
            if text == self.failure_text:
                results.append(TextEncodingResult(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    status=TextEncodingStatus.UNAVAILABLE,
                    error_code="TEXT_ENCODING_UNAVAILABLE",
                    error_message="test inference failure",
                ))
                continue
            processing = {
                "device": "cpu",
                "requested_device": self.config.device,
                "batch_size": self.config.text_batch_size,
                "encoded_text_count": len(values),
                "normalized_embeddings": True,
                "deterministic_inference": True,
                "chunk_count": 1,
                "chunking_strategy": "ordered_character_chunks_mean_normalized",
                "input_character_count": len(text),
            }
            results.append(TextEncodingResult(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                embedding_dimension=384,
                embedding=[1.0] + [0.0] * 383,
                language=language,
                normalized=True,
                processing_metadata=processing,
            ))
        return results

    def to_usr_text_from_result(self, text, result):
        from app.models.text_encoder_schema import TextEncodingStatus
        from app.usr.models import USREmbedding, USRText

        if result.status != TextEncodingStatus.AVAILABLE:
            return None
        return USRText(
            text=text,
            language=result.language,
            embedding=USREmbedding(
                model_name=result.model_name,
                dimension=result.embedding_dimension,
                values=result.embedding,
                normalized=result.normalized,
            ),
            metadata={"processing": result.processing_metadata, "modality": result.modality},
        )

    def to_usr_text(self, *args, **kwargs):
        raise AssertionError("batch-encoded text must not be encoded a second time")


class CountingBatchImageEncoder:
    def __init__(self, config: FeatureExtractionConfig):
        self.config = config
        self.inference_count = 0

    def encode_batch(self, images):
        from uuid import uuid4
        from app.models.image_encoder_schema import ImageEncodingResult

        values = list(images)
        self.inference_count += len(values)
        return [
            ImageEncodingResult.available(
                request_id=uuid4(),
                model_name="ViT-B-32",
                checkpoint="openai",
                embedding_dimension=512,
                embedding=[1.0] + [0.0] * 511,
                image_path=image,
                normalized=True,
                processing_metadata={
                    "device": "cpu",
                    "requested_device": self.config.device,
                    "batch_size": self.config.image_batch_size,
                    "deterministic_inference": True,
                    "normalized_embedding": True,
                    "image_width": 16,
                    "image_height": 16,
                },
            )
            for image in values
        ]

    def to_usr_image_from_result(self, result):
        from app.models.image_encoder_schema import ImageEncodingStatus
        from app.usr.models import USREmbedding, USRImage

        if result.encoding_status != ImageEncodingStatus.COMPLETED:
            return None
        return USRImage(
            image_paths=[result.image_path] if result.image_path else [],
            embedding=USREmbedding(
                model_name=result.model_name,
                dimension=result.embedding_dimension,
                values=result.embedding,
                normalized=result.normalized,
            ),
            metadata={
                "modality": result.modality,
                "checkpoint": result.checkpoint,
                "processing": result.processing_metadata,
            },
        )

    def to_usr_image(self, *args, **kwargs):
        raise AssertionError("batch-encoded image must not be encoded a second time")


def test_coerce_split_accepts_enum_and_string() -> None:
    assert _coerce_split("train").value == "train"
    assert _coerce_split("validation").value == "validation"
    assert _coerce_split("test").value == "test"


def test_write_jsonl_is_atomic_and_safe_under_concurrent_writes(tmp_path: Path) -> None:
    target = tmp_path / "train.jsonl"
    results = []

    def write_record(index: int) -> None:
        _write_jsonl(target, [{"sample_id": str(index), "value": index}])
        results.append(json.loads(target.read_text(encoding="utf-8")))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_record, range(20)))

    assert len(results) == 20
    assert all(record["sample_id"] in {str(index) for index in range(20)} for record in results)
    assert json.loads(target.read_text(encoding="utf-8"))["sample_id"] in {str(index) for index in range(20)}
    assert list(tmp_path.glob(".train.jsonl.*.tmp")) == []


def test_reconcile_rebuilds_cache_from_jsonl_only_feature(tmp_path: Path) -> None:
    from app.evaluation import fakeddit_features as module

    sample = acquired_sample("train", "jsonl-only")
    write_acquired_records(tmp_path, "train", [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    artifact = complete_artifact(sample, config)
    output = Path(config.output_dir) / "train.jsonl"
    _write_jsonl(output, [artifact])

    result = reconcile_feature_checkpoint(config)
    cache = module.FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")

    assert result["jsonl_only_records_recovered"] == 1
    assert result["cache_only_records_recovered"] == 0
    assert set(cache.values) == {"jsonl-only"}
    assert {row["sample_id"] for row in map(json.loads, output.read_text(encoding="utf-8").splitlines())} == set(cache.values)


def test_reconcile_restores_jsonl_from_cache_only_feature(tmp_path: Path) -> None:
    from app.evaluation import fakeddit_features as module

    sample = acquired_sample("train", "cache-only")
    write_acquired_records(tmp_path, "train", [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    cache = FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")
    cache.put("cache-only", config.configuration_hash(), complete_artifact(sample, config))
    cache.save()

    result = reconcile_feature_checkpoint(config)
    rows = [json.loads(line) for line in (Path(config.output_dir) / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    reloaded_cache = module.FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")

    assert result["cache_only_records_recovered"] == 1
    assert [row["sample_id"] for row in rows] == ["cache-only"]
    assert set(reloaded_cache.values) == {"cache-only"}


def test_failed_acquisition_is_skipped_from_feature_dataset(tmp_path: Path) -> None:
    failed_sample = acquired_sample("train", "failed", status="http_error")
    write_acquired_records(tmp_path, "train", [failed_sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    output = Path(config.output_dir) / "train.jsonl"
    _write_jsonl(output, [{"sample_id": "failed", "split": "train", "status": "failed", "error": "IMAGE_NOT_FOUND"}])

    result = reconcile_feature_checkpoint(config)
    statistics = {"acquisition_skipped": 0}
    assert list(iter_acquired_records(tmp_path, split="train", statistics=statistics)) == []
    assert statistics["acquisition_skipped"] == 1
    assert result["acquisition_failures_skipped"] == 1
    assert output.read_text(encoding="utf-8") == ""


def test_resume_after_interruption_repairs_jsonl_only_then_processes_pending(tmp_path: Path, monkeypatch) -> None:
    sample_one = acquired_sample("train", "already-jsonl")
    sample_two = acquired_sample("train", "pending")
    write_acquired_records(tmp_path, "train", [sample_one, sample_two])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", text_batch_size=1, image_batch_size=1, device="cpu")
    _write_jsonl(Path(config.output_dir) / "train.jsonl", [complete_artifact(sample_one, config)])
    build_calls = []
    install_fake_encoders(monkeypatch, __import__("app.evaluation.fakeddit_features", fromlist=["*"]), build_calls)

    result = run_feature_extraction(config)
    rows = [json.loads(line) for line in (Path(config.output_dir) / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    cache = FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")

    assert build_calls == ["pending"]
    assert result["skipped"] == 1
    assert result["processed"] == 1
    assert {row["sample_id"] for row in rows} == set(cache.values) == {"already-jsonl", "pending"}


def test_repeated_extraction_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    from app.evaluation import fakeddit_features as module

    samples = [acquired_sample("train", "repeat-1"), acquired_sample("train", "repeat-2")]
    write_acquired_records(tmp_path, "train", samples)
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", text_batch_size=1, image_batch_size=1, device="cpu")
    build_calls = []
    install_fake_encoders(monkeypatch, module, build_calls)

    run_feature_extraction(config)
    output_path = Path(config.output_dir) / "train.jsonl"
    cache_path = Path(config.output_dir) / "feature_cache.json"
    first_output = output_path.read_bytes()
    first_cache = cache_path.read_bytes()
    run_feature_extraction(config)

    assert build_calls == ["repeat-1", "repeat-2"]
    assert output_path.read_bytes() == first_output
    assert cache_path.read_bytes() == first_cache
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    output_ids = {json.loads(line)["sample_id"] for line in output_path.read_text(encoding="utf-8").splitlines()}
    assert output_ids == set(cache)


def test_reconciliation_enforces_equal_completed_id_sets(tmp_path: Path) -> None:
    sample = acquired_sample("train", "equal-sets")
    write_acquired_records(tmp_path, "train", [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    _write_jsonl(Path(config.output_dir) / "train.jsonl", [complete_artifact(sample, config)])

    result = reconcile_feature_checkpoint(config)
    output_ids = {json.loads(line)["sample_id"] for line in (Path(config.output_dir) / "train.jsonl").read_text(encoding="utf-8").splitlines()}
    cache_ids = set(json.loads((Path(config.output_dir) / "feature_cache.json").read_text(encoding="utf-8")))

    assert result["reconciled_feature_rows"] == result["reconciled_cache_entries"] == 1
    assert output_ids == cache_ids == {"equal-sets"}


def test_worker_reuses_each_batch_embedding_and_preserves_artifact_provenance(tmp_path: Path) -> None:
    samples = [acquired_sample("train", "batch-1"), acquired_sample("train", "batch-2")]
    write_acquired_records(tmp_path, "train", samples)
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", text_batch_size=8, image_batch_size=4, device="cpu")
    text_encoder = CountingBatchTextEncoder(config)
    image_encoder = CountingBatchImageEncoder(config)
    cache = FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")

    processed, failed = _process_batch(
        samples,
        config=config,
        output_dir=Path(config.output_dir),
        split=_coerce_split("train"),
        cache=cache,
        text_encoder=text_encoder,
        image_encoder=image_encoder,
        progress=[],
    )
    rows = [json.loads(line) for line in (Path(config.output_dir) / "train.jsonl").read_text(encoding="utf-8").splitlines()]

    assert (processed, failed) == (2, 0)
    assert text_encoder.inference_count == image_encoder.inference_count == 2
    assert [row["sample_id"] for row in rows] == ["batch-1", "batch-2"]
    assert all(len(row["feature_vector"]) == 20 for row in rows)
    assert all(all(float(value) == value for value in row["feature_vector"]) for row in rows)
    assert all(row["text_provenance"]["model_name"] == "sentence-transformers/all-MiniLM-L6-v2" for row in rows)
    assert all(row["image_provenance"]["model_name"] == "ViT-B-32" for row in rows)
    assert all(row["image_provenance"]["checkpoint"] == "openai" for row in rows)
    assert {row["sample_id"] for row in rows} == set(cache.values)


def test_batch_text_encoding_preserves_long_text_chunking_without_reencoding() -> None:
    from app.config.settings import Settings
    from app.models.text_encoder import SentenceTransformerTextEncoder

    class CountingModel:
        def __init__(self):
            self.calls = []

        def eval(self):
            pass

        def encode(self, texts, **kwargs):
            values = list(texts)
            self.calls.append(values)
            return [[1.0] + [0.0] * 383 for _ in values]

    model = CountingModel()
    encoder = SentenceTransformerTextEncoder(
        settings=Settings(text_encoder_device="cpu", text_encoder_batch_size=8, text_encoder_chunk_size=4000),
        model_factory=lambda model_name, device: model,
    )

    results = encoder.encode_batch_with_chunking(["short title", "x" * 4001], language="en")

    assert sorted(len(call) for call in model.calls) == [1, 2]
    assert ["short title"] in model.calls
    assert ["x" * 4000, "x"] in model.calls
    assert [result.processing_metadata["chunk_count"] for result in results] == [1, 2]
    assert [result.embedding_dimension for result in results] == [384, 384]


def test_long_text_propagates_failure_from_any_chunk() -> None:
    from app.models.text_encoder import SentenceTransformerTextEncoder
    from app.models.text_encoder_schema import TextEncodingResult, TextEncodingStatus

    encoder = SentenceTransformerTextEncoder()
    available = TextEncodingResult(
        model_name="text-model",
        embedding_dimension=2,
        embedding=[1.0, 0.0],
        normalized=True,
    )
    unavailable = TextEncodingResult(
        model_name="text-model",
        status=TextEncodingStatus.UNAVAILABLE,
        error_code="TEXT_ENCODING_UNAVAILABLE",
        error_message="chunk failed",
    )

    result = encoder._aggregate_chunk_results("long input", ["long", " input"], [available, unavailable], "en")

    assert result.status == TextEncodingStatus.UNAVAILABLE
    assert result.error_code == "TEXT_ENCODING_UNAVAILABLE"


def test_fingerprint_versions_compatibility_without_changing_legacy_hash(tmp_path: Path) -> None:
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    legacy_hash = config.configuration_hash()

    fingerprint_a = config.configuration_fingerprint(library_versions={"torch": "2.0"})
    fingerprint_b = config.configuration_fingerprint(library_versions={"torch": "2.1"})

    assert fingerprint_a != fingerprint_b
    assert config.configuration_hash() == legacy_hash


def test_legacy_checkpoint_requires_exact_model_and_preprocessing_provenance(tmp_path: Path) -> None:
    sample = acquired_sample("train", "legacy")
    write_acquired_records(tmp_path, "train", [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", text_batch_size=8, image_batch_size=4, device="auto")
    artifact = complete_artifact(sample, config)
    artifact.pop("configuration_fingerprint")
    artifact.pop("configuration_fingerprint_version")
    validation = {
        "sample": sample,
        "config": config,
        "configuration_fingerprint": config.configuration_fingerprint(),
        "data_dir": Path(config.data_dir),
    }

    assert _is_complete_feature_artifact(artifact, **validation)
    artifact["image_provenance"]["checkpoint"] = "different-checkpoint"
    assert not _is_complete_feature_artifact(artifact, **validation)


def test_inference_failure_is_counted_without_writing_a_feature_or_cache(tmp_path: Path) -> None:
    sample = acquired_sample("train", "inference-failure")
    sample["text"] = "fail this title"
    write_acquired_records(tmp_path, "train", [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    text_encoder = CountingBatchTextEncoder(config, failure_text=sample["text"])
    image_encoder = CountingBatchImageEncoder(config)
    cache = FeatureExtractionCache(Path(config.output_dir) / "feature_cache.json")
    progress = []

    processed, failed = _process_batch(
        [sample],
        config=config,
        output_dir=Path(config.output_dir),
        split=_coerce_split("train"),
        cache=cache,
        text_encoder=text_encoder,
        image_encoder=image_encoder,
        progress=progress,
    )

    assert (processed, failed) == (0, 1)
    assert progress[0]["status"] == "failed"
    assert cache.values == {}
    assert not (Path(config.output_dir) / "train.jsonl").exists()


def test_checkpoint_reconciliation_preserves_split_boundaries(tmp_path: Path) -> None:
    samples = [acquired_sample(split, f"{split}-id") for split in ("train", "validation", "test")]
    for sample in samples:
        write_acquired_records(tmp_path, sample["split"], [sample])
    config = FeatureExtractionConfig(data_dir=tmp_path, output_dir=tmp_path / "out", device="cpu")
    for sample in samples:
        _write_jsonl(Path(config.output_dir) / f"{sample['split']}.jsonl", [complete_artifact(sample, config)])

    result = reconcile_feature_checkpoint(config)

    assert result["completed_ids_by_split"] == {
        "train": {"train-id"},
        "validation": {"validation-id"},
        "test": {"test-id"},
    }
