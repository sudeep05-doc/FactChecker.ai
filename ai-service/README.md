# FactChecker.ai AI Service

Standalone Python/FastAPI microservice foundation for FactChecker.ai.

The AI service preserves this boundary:

```text
CAL -> preprocessing -> foundation models -> USR -> CMREF -> RR
    -> decision/calibration -> CMREA -> final structured result
```

The HTTP verification endpoint remains an explicit mock endpoint. The injected
pipeline, foundation adapters, and evaluation framework are exercised directly
by tests. React, Node.js, MongoDB, authentication, and paid APIs are not used by
this service.

## Requirements

- Python 3.10 or newer is recommended. The test environment also supports Python 3.9.
- pip
- macOS, Linux, or Windows

Install dependencies from the service directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## Run the service

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The health endpoint is available at `http://127.0.0.1:8000/health` and API docs
at `http://127.0.0.1:8000/docs`.

## Run tests

```bash
pytest
pytest tests/test_text_encoder.py
pytest tests/test_evaluation.py
```

Tests use injected fakes and do not download foundation models.

## Text foundation model

Task 23A integrates the lightweight open-source
`sentence-transformers/all-MiniLM-L6-v2` SentenceTransformer by default. The
model is a supporting foundation component, not the research contribution; the
research architecture remains CMREF/RR/decision-calibration/CMREA.

Configuration is loaded through the existing settings pattern:

```dotenv
TEXT_ENCODER_MODEL=sentence-transformers/all-MiniLM-L6-v2
TEXT_ENCODER_DEVICE=auto
TEXT_ENCODER_BATCH_SIZE=8
TEXT_ENCODER_CHUNK_SIZE=4000
```

`SentenceTransformerTextEncoder` loads lazily on the first encode request and
reuses one model instance for subsequent calls. `auto` selects Apple MPS when
available and otherwise CPU. Explicit `mps` also falls back to CPU when MPS is
unavailable. The actual device is retained in structured processing metadata.

The encoder returns validated structured results containing the text modality,
model name, dimension, normalized embedding, status, errors when unavailable,
and processing metadata. `to_usr_text()` converts an available result to the
existing `USRText`/`USREmbedding` boundary without changing USR or CMREF.

Empty or whitespace-only text returns `TEXT_EMPTY` and no vector. Non-finite,
empty, malformed, or unavailable model outputs return structured unavailable
states; no random, zero, padded, truncated, or fabricated vector is produced.

Long text is split deterministically into ordered character chunks using
`TEXT_ENCODER_CHUNK_SIZE`. Each chunk is encoded, the embeddings are averaged in
order, and the aggregate is normalized. Chunk count and strategy are recorded.
This avoids silently discarding article content, while the existing text
preprocessor still enforces its configured maximum input length.

The default batch size is deliberately small for an 8 GB Apple M1 development
machine. Actual model download size and runtime depend on the SentenceTransformers
and PyTorch versions and the local model cache. If model files are unavailable,
the adapter reports `TEXT_ENCODING_UNAVAILABLE`; it does not fabricate output.

Text-only USR operation remains valid. CMREF receives the validated text
embedding; pairwise cross-modal alignment and contradiction remain undefined
when no second modality or contradiction evaluator is available.

## Evaluation framework

The `app/evaluation` package consumes explicit dataset samples and structured
predictions from an injected executor. It does not access CMREF internals,
CMREA internals, React, Node.js, MongoDB, authentication, or paid APIs. Ground
truth comes only from the dataset label and is never inferred from source
reputation, confidence, OCR, Whisper, alignment, reasoning, or explanations.

Baseline configurations include `text_only`, `image_only`, `text_image`,
`text_image_ocr`, and `all_available`. Ablations include
`baseline_text`, `baseline_image`, `multimodal_no_alignment`,
`multimodal_alignment`, `multimodal_alignment_consistency`, and
`multimodal_full_reasoning`. These are experimental configurations, not claims
that any configuration is superior.

The framework supports classification metrics, Brier score, ECE,
reliability-bin data, modality robustness, contradiction records, explanation
records, structured error analysis, JSON serialization, and reproducibility
metadata. Missing predictions and probabilities remain explicitly unavailable.
Training split evaluation requires explicit `allow_training=True`.

No real dataset results, fabricated accuracy values, statistical significance
claims, or empirical validation claims are included. Real research conclusions
require approved datasets, executed experiments, and documented analysis.

## Directory guide

| Directory           | Responsibility                                          |
| ------------------- | ------------------------------------------------------- |
| `app/api`           | FastAPI routers and HTTP endpoints                      |
| `app/config`        | Environment-based settings                              |
| `app/cal`           | Content acquisition                                     |
| `app/preprocessing` | Deterministic modality preprocessing                    |
| `app/models`        | Lazy foundation model adapters                          |
| `app/usr`           | Unified semantic representation                         |
| `app/cmref`         | Cross-modal evidence reasoning                          |
| `app/rr`            | Structured reasoning representation                     |
| `app/pipeline`      | Dependency-injected orchestration and decision boundary |
| `app/cmrea`         | RR-based explanation boundary                           |
| `app/evaluation`    | Dataset-agnostic research evaluation                    |
| `tests`             | Automated service and evaluation tests                  |

## Current limitations

## Unified foundation orchestration

Task 23E adds `app/foundation`, a dependency-injected boundary that consumes
the existing SentenceTransformer, OpenCLIP, EasyOCR, and Whisper adapter
outputs and assembles them through the existing USR builder. It can then hand
that USR to the existing CMREF implementation; it does not reimplement any
model, CMREF formula, RR behavior, CMREA behavior, decision logic, or
classification.

Embedded modalities are kept distinct from structured evidence:

```text
text -> SentenceTransformer -> text embedding
image -> OpenCLIP -> image embedding
image -> EasyOCR -> OCR detections/text evidence
audio/video audio -> Whisper -> timestamped transcript evidence
```

OCR and transcript outputs are preserved in USR without invented embeddings.
The optional `embed_textual_evidence` switch is explicit; because the current
USR contract has no separate OCR/transcript embedding slots, enabling it emits
`TEXTUAL_EVIDENCE_EMBEDDING_UNSUPPORTED` while retaining the original evidence.

The orchestrator supports any non-empty subset of text, image, OCR, audio
transcript, video transcript, and existing video-frame representations. Missing
modalities are listed as omitted and never become zero vectors or negative
evidence. Failed adapters retain their original error codes and do not discard
successful modalities. Modality ordering is deterministic: text, image, OCR,
audio transcript, video transcript.

Each assembled modality records provenance such as adapter processing metadata,
model/device information, checkpoint where available, and normalization state.
This is processing/audit metadata, not semantic truth evidence. The result
contains active, successful, omitted, and failed modality lists, USR, optional
CMREF output, provenance, warnings, and errors, but no prediction or confidence.

## Decision and calibration layer

Task 24 adds a replaceable `app/decision` boundary over RR-derived features.
The feature extractor uses fixed ordering and schema version `rr-decision-v1`,
with explicit presence indicators for optional RR evidence so unavailable
evidence is distinguishable from a present low value. It uses only fields that
already exist in RR: consistency, contradiction, contextual features, alignment
records, modality counts, reasoning score, and decision evidence.

The trainable baseline is scikit-learn `LogisticRegression`. Foundation models
remain frozen, and no coefficients or predictions are hand-written. The
lifecycle is explicit: `UNFITTED` -> `TRAINED` -> `READY`. Training consumes
only labeled `REAL`/`FAKE` feature vectors. Validation calibration is a separate
sigmoid/Platt-style LogisticRegression step; test data is not required or used
by the decision service.

Before calibration, a fitted classifier may return a canonical prediction and
raw `FAKE` probability, but calibrated probability and confidence remain null
with `CALIBRATION_UNAVAILABLE`. After validation calibration, calibrated
probability and confidence are exposed in `[0, 1]`. Confidence is never derived
from cosine similarity, OCR confidence, Whisper metadata, source reputation, or
the RR reasoning score alone.

The pipeline passes the complete decision result and metadata into CMREA.
CMREA explains the supplied decision and does not calculate or override it.
The default HTTP endpoint still uses the explicit mock pipeline; no trained
classifier or research performance result is installed by default. Real
datasets, held-out evaluation, calibration assessment, and experiment logging
are still required before any empirical claim.

## Fakeddit dataset preparation

Task 26 adds `FakedditAdapter` for a researcher-supplied local Fakeddit TSV.
The release must be obtained manually; this repository does not scrape Reddit,
download Fakeddit, download the complete image archive, train a classifier, or
run foundation-model inference during preparation.

The default field mapping expects `id`, `clean_title`, `image_url`, and
`2_way_label`. If the supplied release uses different names, pass an explicit
`FakedditFieldMap`; missing required columns fail clearly. The adapter also
requires an explicit source-label mapping, for example:

```python
FakedditAdapter(label_mapping={"0": "REAL", "1": "FAKE"})
```

This mapping is a researcher-supplied experiment configuration. The adapter
does not guess or reverse labels. Task 27 later processed the uploaded official
train, validation, and test TSVs with the explicit `0 -> FAKE`, `1 -> REAL`
mapping documented below.

The controlled first subset uses `require_text=True` and `require_image=True`.
Text and image availability, missing modalities, invalid labels, duplicate IDs,
and image acquisition failures are counted separately. Image URLs are handled
only through an injected acquisition callback, which must return a local,
non-empty, decodable image path. Failed acquisition is recorded as unavailable,
never as `FAKE`; local image files are validated before inclusion.

Output is the existing Task 25 `EvaluationSample` JSONL format. Each record
preserves the original Fakeddit ID, source label, source file, dataset/version,
image reference, label mapping, modality status, and source provenance. The
adapter supports deterministic `max_samples` selection with a seed, but leaves
train/validation/test splitting to Task 25.

**REAL DATASET HAS NOT YET BEEN RUN THROUGH THE MODEL.** Task 27 created
research manifests from the supplied Fakeddit TSVs. No images have been
downloaded, no classifier has been trained, and no research metrics have been
generated.

## Task 27: Fakeddit research subset preparation

`app.evaluation.fakeddit_preparation` prepares small, balanced JSONL manifests
from the three official Fakeddit TSV partitions. It does not merge or randomly
re-split them: train remains train, validation remains validation, and test
remains test. Only rows with non-empty `clean_title` and `image_url` and a
strictly recognized `2_way_label` are candidates. The default explicit mapping
is `0 -> FAKE` and `1 -> REAL`; the mapping is included in each sample and the
preparation report.

Image-level leakage is checked across the original partitions before subset
selection. The normalizer trims surrounding whitespace, lowercases only the URL
scheme and hostname, and preserves the path, query, fragment, port, and user
information. If a normalized URL occurs in multiple splits, TRAIN owns it ahead
of VALIDATION, which owns it ahead of TEST; lower-priority occurrences are
excluded, never moved. Repeated URLs within one split are deduplicated by keeping
the first eligible source row. If a URL has different valid labels anywhere in
the source partitions, all eligible rows for that URL are excluded rather than
choosing or voting on a label. Duplicate IDs are likewise audited and later
occurrences are excluded.

The default request is 10,000 FAKE and 10,000 REAL samples for train, and 2,000
per class for validation and test (28,000 total). Selection uses seed `42` and
an ascending SHA-256 ordering derived from the seed and original ID. When a
split lacks enough examples of either class, the selected count is reduced
equally for both classes and the per-class shortfall is recorded; samples are
never duplicated. The report and `excluded_samples.jsonl` distinguish modality
filtering, invalid labels, duplicate/ambiguous URLs, cross-split leakage, and
the subset-size limit.

This task does not download or request any image URL. The JSONL `image` field
and provenance metadata retain the remote source URL; they do not invent local
image paths. Image acquisition, model training, and evaluation are separate
future steps and are not performed by this preparation command.

Run from `ai-service/` to reproduce the default subset from the uploaded files:

```bash
python -m app.evaluation.fakeddit_preparation \
    --train ../research-data/fakeddit/all_train.tsv \
    --validation ../research-data/fakeddit/all_validate.tsv \
    --test ../research-data/fakeddit/all_test_public.tsv \
    --output-dir data/research/fakeddit \
    --train-per-class 10000 \
    --validation-per-class 2000 \
    --test-per-class 2000 \
    --seed 42
```

The output contains `train.jsonl`, `validation.jsonl`, `test.jsonl`,
`preparation_report.json`, and row-level `excluded_samples.jsonl`. Existing
output files are not overwritten unless `--overwrite` is provided. The report
records input paths and SHA-256 checksums, dynamic row and exclusion counts,
duplicate/leakage audits, label semantics, configuration, and final class
counts. No empirical model metrics are produced by Task 27.

## Task 28: controlled image acquisition

`app.evaluation.fakeddit_acquisition` reads only the three approved Task 27
manifests at `data/research/fakeddit/{train,validation,test}.jsonl`. It does not
re-read the large TSVs, discover images, crawl Reddit, change split membership,
rebalance, or replace failures. The normal command performs acquisition, so
use `--dry-run` first; dry-run reads and validates manifests, reports class and
split counts plus available disk space, and makes no network requests or file
changes. Exact image storage cannot be estimated without downloading, so the
dry-run marks that estimate unknown and shows the configured 20 GiB cap.

Actual acquisition uses `images/` and writes Task 25-compatible JSONL files to
`acquired/` plus `acquisition_report.json`. Original `image` URLs, IDs, labels,
text, split, and metadata are preserved. The validated local path is added as
`metadata.local_image_path`; `metadata.acquisition` records status, HTTP and
content metadata, dimensions, decoded format, attempts, source/normalized URL,
and SHA-256. Filenames use SHA-256 of the normalized URL and an extension
detected from decoded bytes. Original image bytes are preserved without
unnecessary conversion. Different URLs with identical bytes share one local
file, with the relationship recorded in acquisition metadata.

Downloads stream in bounded chunks. Defaults are four concurrent workers,
10-second connect and 30-second read timeouts, three retries after the initial
attempt, 15 MiB per image, 20,000 pixels per dimension, 25 million pixels, and
a 20 GiB aggregate image-storage limit. Transient network errors and HTTP 408,
429, 500, 502, 503, and 504 retry with capped exponential backoff; `Retry-After`
is honored up to its configured cap. Requests follow redirects, send the
configured User-Agent, use a small delay/jitter, and check cached per-origin
`robots.txt` rules. Disallowed or unavailable policy checks are recorded and
the media URL is not requested.

HTTP status and Content-Type are checked, then Pillow verifies and fully decodes
JPEG, PNG, or WEBP bytes. Empty, corrupt, unsupported, oversized, or excessive-
dimension images are rejected and temporary files removed. Successful bytes
are checksummed and atomically renamed from a `.part` file. Resume is enabled by
default: existing local files are revalidated and reused; corrupt ones are
replaced. Every failure stays in its original acquired-manifest record and the
report. Failed samples are not replaced, so the acquired class counts may be
lower than the requested counts.

Run a no-network preflight from `ai-service/`:

```bash
.venv/bin/python -m app.evaluation.fakeddit_acquisition \
    --train-manifest data/research/fakeddit/train.jsonl \
    --validation-manifest data/research/fakeddit/validation.jsonl \
    --test-manifest data/research/fakeddit/test.jsonl \
    --output-dir data/research/fakeddit \
    --dry-run
```

For acquisition development, the optional `--max-samples N` flag caps the total
number of manifest records. It allocates records round-robin across train,
validation, and test, beginning with train, and takes the first allocated rows
from each original manifest without reordering them. For example, a cap of 100
selects 34 train, 33 validation, and 33 test records. This is a smoke-test mode,
not a new research subset: it does not edit Task 27 manifests, move records
between splits, or replace failed acquisitions. Omitting `--max-samples`
continues to target every record, as before. Use a separate output directory so
bounded smoke-test manifests cannot be mistaken for full acquisition outputs.

Dry-run the 100-record selection without contacting any host:

```bash
.venv/bin/python -m app.evaluation.fakeddit_acquisition \
    --train-manifest data/research/fakeddit/train.jsonl \
    --validation-manifest data/research/fakeddit/validation.jsonl \
    --test-manifest data/research/fakeddit/test.jsonl \
    --output-dir data/research/fakeddit-smoke-100 \
    --max-samples 100 \
    --dry-run
```

After reviewing the bounded dry-run, this command acquires at most those 100
records and writes only to the separate smoke-test output directory:

```bash
.venv/bin/python -m app.evaluation.fakeddit_acquisition \
    --train-manifest data/research/fakeddit/train.jsonl \
    --validation-manifest data/research/fakeddit/validation.jsonl \
    --test-manifest data/research/fakeddit/test.jsonl \
    --output-dir data/research/fakeddit-smoke-100 \
    --concurrency 4 \
    --max-retries 3 \
    --max-image-bytes 15728640 \
    --max-total-bytes 21474836480 \
    --max-samples 100 \
    --resume
```

After reviewing that summary, the explicit command to begin image acquisition
is:

```bash
.venv/bin/python -m app.evaluation.fakeddit_acquisition \
    --train-manifest data/research/fakeddit/train.jsonl \
    --validation-manifest data/research/fakeddit/validation.jsonl \
    --test-manifest data/research/fakeddit/test.jsonl \
    --output-dir data/research/fakeddit \
    --concurrency 4 \
    --max-retries 3 \
    --max-image-bytes 15728640 \
    --max-total-bytes 21474836480 \
    --resume
```

Task 28 does not train models, extract features, or calculate evaluation
metrics.

## Real-data research pipeline

Task 25 adds `ResearchEvaluationPipeline` and local dataset helpers under
`app/evaluation`. A researcher supplies a local JSONL manifest; the service does
not scrape, select, or download a dataset automatically. The supported layout
is:

```text
dataset/
    manifest.jsonl
    text/
    images/
    audio/
    video/
```

Each record has a unique `sample_id`, an explicit `label` of `REAL` or `FAKE`,
and any available `text`, `image`, `ocr_text`, `audio`, `video`, `metadata`, and
`source_reference` fields. Missing modalities remain null. Labels are never
inferred from filenames, domains, or source reputation.

`split_samples()` performs deterministic seeded train/validation/test splitting,
preferring stratification when class counts permit. An optional metadata group
key keeps samples from the same article or event together. Preassigned splits
are not silently reshuffled, and split overlap is rejected.

The research flow is:

```text
TRAIN -> RR provider -> rr-decision-v1 features -> LogisticRegression.fit
VALIDATION -> same features -> sigmoid calibration
TEST -> same frozen pipeline -> held-out metrics only
```

The runner requires an injected RR provider, so it cannot bypass foundation
orchestration, USR, CMREF, or RR. An optional cache stores RR intermediates only
when its model/preprocessing/CMREF configuration hash matches; stale entries are
ignored. Cache files and generated results are not committed by this repository.

Existing baseline configurations include text-only, image-only, text+image,
text+image+OCR, and all-available modalities. Result JSON contains dataset and
split sizes, class distributions, model/configuration metadata, feature schema,
classifier/calibration metadata, held-out metrics, test IDs, and reproducibility
metadata.

**REAL DATASET NOT PROVIDED.** The repository contains no trained production
classifier and no real held-out evaluation results. Synthetic fixtures are used
only to test pipeline mechanics. No accuracy, F1, ROC-AUC, Brier, ECE,
calibration quality, or superiority claim is made.

## Image foundation model

Task 23B integrates the lightweight open-source OpenCLIP configuration
`ViT-B-32` with the `openai` pretrained checkpoint by default. OpenCLIP is a
supporting foundation model; the research contribution remains the existing
cross-modal reasoning and explainability architecture.

Configuration is loaded through the existing settings system:

```dotenv
IMAGE_ENCODER_MODEL=ViT-B-32
IMAGE_ENCODER_CHECKPOINT=openai
IMAGE_ENCODER_DEVICE=auto
IMAGE_ENCODER_BATCH_SIZE=4
```

`OpenCLIPImageEncoder` loads lazily, reuses one model instance, and uses the
preprocess transform returned by OpenCLIP itself. `auto` selects MPS when
available and otherwise CPU. If MPS inference fails, the adapter retries on
CPU and records the actual device used.

Image outputs contain the model name, checkpoint, dimension, normalized
embedding, image modality, device, preprocessing metadata, and structured
failure information. Missing, empty, unsupported, corrupted, or unreadable
images never produce a fabricated vector. Batch results preserve input order,
including failure entries, and use a small configurable batch size for an 8 GB
M1 development machine.

`to_usr_image()` converts a successful result to the existing `USRImage` and
`USREmbedding` boundary. Image-only CMREF operation keeps cross-modal
alignment and contradiction undefined; text-plus-image operation can produce
the existing pairwise alignment evidence without turning it into a prediction
or confidence score.

OpenCLIP weights are not downloaded during requests or tests. If weights are
not locally available, the adapter returns `IMAGE_ENCODING_FAILED` rather than
fabricating an embedding. The actual model footprint and runtime depend on
OpenCLIP, PyTorch, and the local model cache.

## Visual text extraction

Task 23C integrates EasyOCR as a supporting visual-text extraction component.
It accepts existing image preprocessing results as well as local paths, bytes,
and PIL images. Configuration is explicit:

```dotenv
OCR_LANGUAGES=en
OCR_DEVICE=auto
OCR_USE_GPU=false
OCR_MODEL_DIRECTORY=
OCR_PARAGRAPH_MODE=false
```

EasyOCR readers are initialized lazily and reused. On the M1 development
machine, `auto`, `mps`, and the default `OCR_USE_GPU=false` use the CPU
conservatively because EasyOCR GPU support is not assumed to be MPS-compatible.
CUDA is used only when explicitly requested and available. The actual device
and backend are recorded in processing metadata, along with languages,
paragraph mode, model directory, detection count, and ordering strategy.

OCR results preserve individual detection order, bounding boxes, raw text,
normalized text, and recognition confidence. Normalization is conservative and
retains meaningful punctuation, numbers, names, dates, and URLs. No-text output
is a completed extraction with the `OCR_NO_TEXT` warning; it is not negative or
fake-news evidence.

OCR confidence is recognition confidence only. It is not truth confidence,
source credibility, a fake/real probability, CMREF confidence, or final
prediction confidence. The adapter never maps OCR confidence to a prediction.

`to_usr_ocr()` preserves structured OCR evidence through the existing `USROCR`
boundary. OCR is not treated as an image embedding and no OCR embedding is
invented. OCR text can be embedded later by the existing text encoder if an
experiment explicitly requests that step. Image, OCR, and text can coexist in
USR; CMREF continues to use only its existing eligible embeddings and formulas.

The implementation uses one lazy reader and avoids retaining unnecessary image
copies. EasyOCR weights are not downloaded during tests. If the reader or model
files are unavailable, the result is structured as `OCR_FAILED` rather than
fabricating text or a confidence value.

## Audio and video transcription

Task 23D integrates the open-source `openai-whisper` implementation with the
lightweight `tiny` model by default. Whisper is a supporting speech foundation
component; it does not produce fake/real predictions or final confidence.

Configuration is loaded through the existing settings system:

```dotenv
WHISPER_MODEL_VARIANT=tiny
WHISPER_DEVICE=auto
WHISPER_LANGUAGE=
WHISPER_TASK=transcribe
WHISPER_MAX_DURATION_SECONDS=600
WHISPER_CHUNK_SECONDS=
```

The model loads lazily on the first valid transcription and is reused for
subsequent requests. `auto` uses the existing device resolver with CPU fallback;
the actual device and `openai-whisper` backend are recorded in metadata. The
implementation passes `fp16=false` for conservative CPU/M1 behavior and keeps
one model instance in memory.

Audio is consumed through the existing `AudioPreprocessingResult` and prepared
16-bit mono WAV path. Local paths and WAV bytes are also supported without
adding URL acquisition. Existing `VideoPreprocessor` audio extraction is
reused through `extracted_audio_path`:

```text
video -> existing audio extraction -> Whisper -> timestamped transcript evidence
```

Video-frame visual analysis remains separate and is not performed here.

Transcript output preserves raw and normalized text, deterministic segment
ordering, segment indexes, start/end timestamps when Whisper provides them,
detected/configured language, task, model, backend, duration, and chunk
metadata. Missing timestamps remain `null`; timestamps are never invented.
Long audio can be split into chronological configurable chunks with segment
offsets preserved. No speech returns `AUDIO_NO_SPEECH`, not negative evidence.

`to_usr_audio()` and `to_usr_video()` preserve transcript evidence and timing in
the existing USR transcript structures without inventing embeddings. A separate
text-encoder step may embed transcript text later. Whisper metadata or any
future transcription confidence is recognition metadata only, never truth
confidence, fake probability, CMREF confidence, or final prediction confidence.

Whisper weights are not downloaded during tests. If the implementation or model
files are unavailable, the adapter returns `TRANSCRIPTION_UNAVAILABLE` instead
of fabricating transcript evidence.

- Foundation model downloads are not required for the test suite.
