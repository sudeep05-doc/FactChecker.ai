"""Dataset loading contracts. Loaders never infer labels or split samples."""

from __future__ import annotations

import json
from pathlib import Path
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple

from sklearn.model_selection import train_test_split

from app.evaluation.schemas import DatasetSplit, EvaluationSample


def load_samples(samples: Iterable[EvaluationSample], split: DatasetSplit) -> List[EvaluationSample]:
    selected = list(samples)
    if any(sample.split is not None and sample.split != split for sample in selected):
        raise ValueError(f"all evaluation samples must explicitly use split={split.value}")
    if not selected:
        raise ValueError("evaluation dataset split is empty")
    return [sample.model_copy(update={"split": split}) if sample.split is None else sample for sample in selected]


def split_samples(
    samples: Iterable[EvaluationSample],
    *,
    seed: int = 42,
    train_fraction: float = 0.7,
    validation_fraction: float = 0.15,
    group_key: Optional[str] = None,
) -> Dict[DatasetSplit, List[EvaluationSample]]:
    """Assign unlabeled local samples to reproducible train/validation/test splits."""
    records = list(samples)
    if not records:
        raise ValueError("dataset must not be empty")
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 or train_fraction + validation_fraction >= 1:
        raise ValueError("split fractions must be positive and leave a test split")
    if len({record.sample_id for record in records}) != len(records):
        raise ValueError("sample_id values must be unique")
    if any(record.split is not None for record in records):
        raise ValueError("split_samples requires samples without preassigned splits")
    if group_key is not None:
        return _group_split(records, seed, train_fraction, validation_fraction, group_key)
    train, remainder = _stratified_split(records, train_fraction, seed)
    validation_ratio = validation_fraction / (1.0 - train_fraction)
    validation, test = _stratified_split(remainder, validation_ratio, seed + 1)
    return _assign_splits(train, validation, test)


def _stratified_split(records, first_fraction: float, seed: int):
    labels = [record.label.value for record in records]
    try:
        return train_test_split(records, train_size=first_fraction, random_state=seed, stratify=labels)
    except ValueError:
        if len(records) < 3:
            raise ValueError("dataset is too small for the requested stratified split")
        return train_test_split(records, train_size=first_fraction, random_state=seed, stratify=None)


def _assign_splits(train, validation, test):
    return {
        DatasetSplit.TRAIN: [record.model_copy(update={"split": DatasetSplit.TRAIN}) for record in train],
        DatasetSplit.VALIDATION: [record.model_copy(update={"split": DatasetSplit.VALIDATION}) for record in validation],
        DatasetSplit.TEST: [record.model_copy(update={"split": DatasetSplit.TEST}) for record in test],
    }


def _group_split(records, seed, train_fraction, validation_fraction, group_key):
    groups: Dict[str, List[EvaluationSample]] = {}
    for record in records:
        group = record.metadata.get(group_key)
        if not group:
            raise ValueError(f"missing group key in sample metadata: {group_key}")
        groups.setdefault(str(group), []).append(record)
    ordered = sorted(groups.items(), key=lambda item: item[0])
    rng_order = train_test_split(ordered, train_size=train_fraction, random_state=seed, shuffle=True)
    train_groups, remainder_groups = rng_order
    validation_ratio = validation_fraction / (1.0 - train_fraction)
    validation_groups, test_groups = train_test_split(remainder_groups, train_size=validation_ratio, random_state=seed + 1, shuffle=True)
    return _assign_splits(
        [record for _, group in train_groups for record in group],
        [record for _, group in validation_groups for record in group],
        [record for _, group in test_groups for record in group],
    )


def load_jsonl(path: str | Path, split: DatasetSplit) -> List[EvaluationSample]:
    records = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    records.append(EvaluationSample.model_validate(json.loads(line)))
                except Exception as error:
                    raise ValueError(f"invalid dataset record at line {line_number}") from error
    return load_samples(records, split)
