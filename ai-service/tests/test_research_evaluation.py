import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.cmref import CMREF
from app.cmref.projection import ProjectionRegistry
from app.evaluation import (
    BASELINE_CONFIGURATIONS,
    DatasetSplit,
    EvaluationConfiguration,
    EvaluationSample,
    FeatureCache,
    ResearchEvaluationPipeline,
    get_configuration,
    load_jsonl,
    split_samples,
)
from app.rr import build_reasoning_representation
from app.usr import USRImage, USRText, USREmbedding, UnifiedSemanticRepresentationBuilder


def sample(index, label, split=None, group=None):
    return EvaluationSample(
        sample_id=f"sample-{index}",
        label=label,
        text=f"claim {index}",
        metadata={"event": group} if group else {},
        split=split,
    )


def rr_provider(record, configuration):
    text = USRText(
        text=record.text or "claim",
        embedding=USREmbedding(model_name="test-text", dimension=2, values=[1.0, 0.0]),
    )
    image = None
    if "image" in configuration.modalities and record.image is not None:
        image = USRImage(embedding=USREmbedding(model_name="test-image", dimension=2, values=[0.0, 1.0]))
    usr = UnifiedSemanticRepresentationBuilder().build(str(uuid4()), text=text, image=image)
    return build_reasoning_representation(CMREF(ProjectionRegistry(2)).reason(usr))


def test_jsonl_dataset_parsing_and_invalid_labels(tmp_path: Path):
    path = tmp_path / "manifest.jsonl"
    path.write_text(json.dumps({"sample_id": "one", "label": "REAL", "text": "claim"}) + "\n", encoding="utf-8")

    records = load_jsonl(path, DatasetSplit.TEST)

    assert records[0].label.value == "REAL"
    with pytest.raises(ValueError):
        EvaluationSample(sample_id="bad", label="UNKNOWN")


def test_split_is_reproducible_stratified_and_non_overlapping():
    records = [sample(index, "REAL" if index % 2 == 0 else "FAKE") for index in range(20)]

    first = split_samples(records, seed=17)
    second = split_samples(records, seed=17)

    assert {key: [item.sample_id for item in value] for key, value in first.items()} == {key: [item.sample_id for item in value] for key, value in second.items()}
    assert all(item.split == key for key, values in first.items() for item in values)
    ids = [item.sample_id for values in first.values() for item in values]
    assert len(ids) == len(set(ids))
    assert all(any(item.label.value == label for item in first[DatasetSplit.TRAIN]) for label in ("REAL", "FAKE"))


def test_group_split_keeps_event_groups_together():
    records = [sample(index, "REAL" if index % 2 == 0 else "FAKE", group=f"event-{index // 2}") for index in range(20)]

    splits = split_samples(records, seed=3, group_key="event")
    memberships = {}
    for split, values in splits.items():
        for record in values:
            memberships.setdefault(record.metadata["event"], split)
            assert memberships[record.metadata["event"]] == split


def test_split_rejects_preassigned_and_duplicate_samples():
    with pytest.raises(ValueError, match="preassigned"):
        split_samples([sample(1, "REAL", split=DatasetSplit.TEST)])
    with pytest.raises(ValueError, match="unique"):
        split_samples([sample(1, "REAL"), sample(1, "FAKE")])


def test_feature_cache_rejects_stale_configuration(tmp_path: Path):
    cache = FeatureCache(str(tmp_path / "features.json"))
    cache.put("one", "hash-a", {"rr": {"value": 1}})
    cache.save()
    reloaded = FeatureCache(str(tmp_path / "features.json"))

    assert reloaded.get("one", "hash-a")["rr"]["value"] == 1
    assert reloaded.get("one", "hash-b") is None


def test_research_pipeline_trains_calibrates_and_evaluates_only_held_out_test():
    records = [sample(index, "REAL" if index % 2 == 0 else "FAKE") for index in range(12)]
    splits = {
        DatasetSplit.TRAIN: [sample(index, "REAL" if index % 2 == 0 else "FAKE", DatasetSplit.TRAIN) for index in range(6)],
        DatasetSplit.VALIDATION: [sample(index + 6, "REAL" if index % 2 == 0 else "FAKE", DatasetSplit.VALIDATION) for index in range(3)],
        DatasetSplit.TEST: [sample(index + 9, "REAL" if index % 2 == 0 else "FAKE", DatasetSplit.TEST) for index in range(3)],
    }
    pipeline = ResearchEvaluationPipeline(rr_provider)

    result = pipeline.run(
        records,
        dataset_identifier="synthetic-unit-test",
        dataset_version="v1",
        configuration=get_configuration("text_only"),
        seed=11,
        splits=splits,
        model_metadata={"text": "test-text"},
        cmref_configuration={"working_dimension": 2},
    )
    payload = result.model_dump(mode="json")

    assert payload["split"]["train_size"] == 6
    assert payload["split"]["validation_size"] == 3
    assert payload["split"]["test_size"] == 3
    assert payload["classifier"]["training_sample_count"] == 6
    assert payload["calibration"]["fitted"] is True
    assert payload["feature_schema"]["version"] == "rr-decision-v1"
    assert len(payload["test_sample_ids"]) == 3
    assert payload["metrics"]["classification"]
    assert payload["metrics"]["calibration"]
    assert "SYNTHETIC" in payload["warnings"][0]
    assert result.payload["dataset"]["identifier"] == "synthetic-unit-test"


def test_test_overlap_is_rejected_before_training():
    duplicate = sample(1, "REAL", DatasetSplit.TRAIN)
    splits = {
        DatasetSplit.TRAIN: [duplicate],
        DatasetSplit.VALIDATION: [sample(2, "FAKE", DatasetSplit.VALIDATION)],
        DatasetSplit.TEST: [duplicate],
    }
    with pytest.raises(ValueError, match="overlap"):
        ResearchEvaluationPipeline(rr_provider).run(
            [duplicate], dataset_identifier="mock", dataset_version="v1",
            configuration=get_configuration("text_only"), splits=splits,
        )


def test_baseline_configurations_remain_available_for_real_runs():
    assert {"text_only", "image_only", "text_image", "text_image_ocr", "all_available"} <= BASELINE_CONFIGURATIONS.keys()
    assert get_configuration("text_image").modalities == ["text", "image"]


def test_malformed_research_dataset_and_empty_split_are_rejected():
    with pytest.raises(ValueError, match="empty"):
        ResearchEvaluationPipeline(rr_provider).run(
            [], dataset_identifier="empty", dataset_version="v1",
            configuration=EvaluationConfiguration(name="text", modalities=["text"]),
            splits={DatasetSplit.TRAIN: [], DatasetSplit.VALIDATION: [], DatasetSplit.TEST: []},
        )
    with pytest.raises(ValueError, match="non-empty"):
        ResearchEvaluationPipeline(rr_provider).run(
            [sample(1, "REAL")], dataset_identifier="bad", dataset_version="v1",
            configuration=get_configuration("text_only"),
            splits={DatasetSplit.TRAIN: [sample(1, "REAL", DatasetSplit.TRAIN)], DatasetSplit.VALIDATION: [], DatasetSplit.TEST: []},
        )
