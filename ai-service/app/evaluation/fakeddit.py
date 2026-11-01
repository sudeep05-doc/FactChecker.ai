"""Local Fakeddit metadata to Task 25 manifest preparation."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from app.evaluation.schemas import EvaluationSample, GroundTruthLabel


class FakedditPreparationError(ValueError):
    """Raised when the supplied Fakeddit metadata cannot be interpreted safely."""


@dataclass(frozen=True)
class FakedditFieldMap:
    sample_id: str = "id"
    text: str = "clean_title"
    image: str = "image_url"
    label: str = "2_way_label"


@dataclass
class FakedditPreparationResult:
    samples: List[EvaluationSample]
    counts: Dict[str, int]
    provenance: Dict[str, object]
    invalid_rows: List[Dict[str, object]]

    def manifest_jsonl(self) -> str:
        return "".join(
            json.dumps(sample.model_dump(mode="json"), sort_keys=True) + "\n"
            for sample in self.samples
        )

    def write_manifest(self, path: str | Path) -> None:
        Path(path).write_text(self.manifest_jsonl(), encoding="utf-8")


ImageAcquirer = Callable[[str, str], Optional[str]]


class FakedditAdapter:
    """Prepare a researcher-supplied Fakeddit TSV without training or inference."""

    def __init__(
        self,
        *,
        label_mapping: Mapping[str, GroundTruthLabel | str],
        fields: FakedditFieldMap = FakedditFieldMap(),
        dataset_version: Optional[str] = None,
        image_acquirer: Optional[ImageAcquirer] = None,
    ) -> None:
        if not label_mapping:
            raise FakedditPreparationError("an explicit Fakeddit label_mapping is required")
        normalized = {}
        for source_label, target_label in label_mapping.items():
            try:
                normalized[str(source_label)] = GroundTruthLabel(target_label)
            except ValueError as error:
                raise FakedditPreparationError("label_mapping targets must be REAL or FAKE") from error
        self.label_mapping = normalized
        self.fields = fields
        self.dataset_version = dataset_version
        self.image_acquirer = image_acquirer

    def prepare(
        self,
        metadata_path: str | Path,
        *,
        output_image_dir: Optional[str | Path] = None,
        max_samples: Optional[int] = None,
        seed: int = 42,
        require_text: bool = True,
        require_image: bool = True,
        label_filter: Optional[Iterable[GroundTruthLabel | str]] = None,
    ) -> FakedditPreparationResult:
        path = Path(metadata_path)
        if not path.is_file():
            raise FakedditPreparationError(f"Fakeddit metadata file does not exist: {path}")
        rows = self._read_rows(path)
        self._validate_fields(rows.fieldnames or [])
        allowed_labels = {GroundTruthLabel(label) for label in label_filter} if label_filter else None
        counts = {
            "rows_seen": 0,
            "text_available": 0,
            "image_available": 0,
            "text_image_available": 0,
            "missing_text": 0,
            "missing_image": 0,
            "invalid_labels": 0,
            "duplicate_ids": 0,
            "image_unavailable": 0,
            "selected": 0,
        }
        invalid_rows: List[Dict[str, object]] = []
        converted: List[EvaluationSample] = []
        seen_ids = set()
        for row_number, row in enumerate(rows, start=2):
            counts["rows_seen"] += 1
            source_id = _clean(row.get(self.fields.sample_id))
            if not source_id:
                invalid_rows.append({"row": row_number, "code": "MISSING_SAMPLE_ID"})
                continue
            if source_id in seen_ids:
                counts["duplicate_ids"] += 1
                invalid_rows.append({"row": row_number, "sample_id": source_id, "code": "DUPLICATE_SAMPLE_ID"})
                continue
            seen_ids.add(source_id)
            source_label = _clean(row.get(self.fields.label))
            if source_label not in self.label_mapping:
                counts["invalid_labels"] += 1
                invalid_rows.append({"row": row_number, "sample_id": source_id, "code": "INVALID_OR_UNMAPPED_LABEL", "source_label": source_label})
                continue
            label = self.label_mapping[source_label]
            if allowed_labels and label not in allowed_labels:
                continue
            text = _clean(row.get(self.fields.text)) or None
            image_reference = _clean(row.get(self.fields.image)) or None
            if text:
                counts["text_available"] += 1
            else:
                counts["missing_text"] += 1
            if image_reference:
                image_path = self._prepare_image(image_reference, source_id, output_image_dir)
            else:
                image_path = None
            if image_path and not _valid_image_path(image_path):
                image_path = None
            if image_path:
                counts["image_available"] += 1
            else:
                counts["missing_image"] += 1
                if image_reference:
                    counts["image_unavailable"] += 1
            if text and image_path:
                counts["text_image_available"] += 1
            if require_text and not text:
                continue
            if require_image and not image_path:
                continue
            converted.append(EvaluationSample(
                sample_id=source_id,
                label=label,
                text=text,
                image=image_path,
                metadata={
                    "dataset": "Fakeddit",
                    "dataset_version": self.dataset_version,
                    "source_id": source_id,
                    "source_label": source_label,
                    "source_file": str(path),
                    "modality_status": {
                        "text": "available" if text else "unavailable",
                        "image": "available" if image_path else "unavailable",
                    },
                    "image_reference": image_reference,
                },
                source_reference=source_id,
            ))
        if max_samples is not None:
            if max_samples < 1:
                raise FakedditPreparationError("max_samples must be positive")
            rng = random.Random(seed)
            rng.shuffle(converted)
            converted = converted[:max_samples]
        counts["selected"] = len(converted)
        provenance = {
            "dataset": "Fakeddit",
            "dataset_version": self.dataset_version,
            "source_file": str(path),
            "source_file_sha256": _sha256(path),
            "field_mapping": self.fields.__dict__,
            "label_mapping": {key: value.value for key, value in self.label_mapping.items()},
            "filter": {"max_samples": max_samples, "seed": seed, "require_text": require_text, "require_image": require_image, "label_filter": sorted(label.value for label in allowed_labels) if allowed_labels else None},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "image_acquisition": "injected_acquirer_only",
        }
        return FakedditPreparationResult(converted, counts, provenance, invalid_rows)

    @staticmethod
    def _read_rows(path: Path):
        try:
            handle = path.open("r", encoding="utf-8", newline="")
            return csv.DictReader(handle, delimiter="\t")
        except (OSError, UnicodeError, csv.Error) as error:
            raise FakedditPreparationError(f"unable to read Fakeddit TSV: {error}") from error

    def _validate_fields(self, fieldnames: List[str]) -> None:
        required = [self.fields.sample_id, self.fields.text, self.fields.image, self.fields.label]
        missing = [field for field in required if field not in fieldnames]
        if missing:
            raise FakedditPreparationError(f"required Fakeddit fields are missing: {missing}")

    def _prepare_image(self, reference: str, source_id: str, output_image_dir: Optional[str | Path]) -> Optional[str]:
        parsed = urlparse(reference)
        if parsed.scheme in {"http", "https"}:
            if self.image_acquirer is None:
                return None
            return self.image_acquirer(reference, source_id)
        path = Path(reference).expanduser()
        return str(path) if path.is_file() else None


def _clean(value: Optional[str]) -> str:
    return str(value or "").strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_image_path(path: str) -> bool:
    candidate = Path(path).expanduser()
    if not candidate.is_file() or candidate.stat().st_size == 0:
        return False
    try:
        with Image.open(candidate) as image:
            image.verify()
        return True
    except (OSError, UnidentifiedImageError, SyntaxError):
        return False
