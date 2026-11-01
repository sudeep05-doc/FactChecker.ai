# AI Verification API Contract

This document defines the Backend-to-AI request and response boundary. The
endpoint currently uses a temporary mock pipeline. The schemas are
deliberately independent of MongoDB and do not imply that inference, model
loading, or confidence estimation is available.

## Endpoint

```text
POST /api/v1/verify
```

The separate Task 47 classifier endpoints are
`POST /api/v1/classify/text`, `/image`, and `/pdf`. Their outputs identify
`is_mock: false`, `prediction_type: "dataset_classification"`, a Fakeddit distant-supervision
dataset scope, the exact model identity, `confidence_semantics:
"uncalibrated_dataset_score"`, the selected `dataset_score`, and
`verdict: null`. `class_scores` and `dataset_score` are in the unit interval
but are uncalibrated. The legacy `prediction`
field is retained for compatibility and is duplicated as
`dataset_prediction`; it must never be treated as an evidence verdict or
factual confidence. PDF classification extracts embedded text only; scanned
PDF OCR is not supported. These endpoints are not connected to the frontend
or Node backend.

The Node.js backend remains the gateway for the React frontend. It may send a
JSON request with normalized content or use multipart/form-data in a future
transport adapter. Large binary data should not be base64-encoded into JSON.
For multipart requests, the backend should first persist or stage the upload
and pass the resulting opaque `content.file_reference` to the same service
contract.

The backend's public response uses equivalent camelCase names
(`predictionType`, `evidenceStatus`, `datasetPrediction`, `modelIdentity`,
`datasetIdentity`, `confidenceSemantics`, and `explanationProvenance`). The
backend currently does not call this microservice; its own verification route
returns the same explicit unavailable state until integration and evidence
evaluation are implemented.

## Request

The Pydantic request model is `VerificationRequest` in
`app/schemas/verification.py`.

| Field                | Type   | Description                                                             |
| -------------------- | ------ | ----------------------------------------------------------------------- |
| `request_id`         | UUID   | Gateway correlation ID; generated if omitted                            |
| `input_type`         | enum   | `text`, `image`, `pdf`, `audio`, `video`, `news_url`, or `youtube_url`  |
| `content`            | object | Text, URL, or opaque file metadata/reference                            |
| `processing_options` | object | Optional extraction, transcription, explanation, and output preferences |

`content` supports:

- `text` for text input
- `url` for news and YouTube URLs
- `file_reference` for staged image, PDF, audio, and video content
- optional `file_name`, `mime_type`, `size_bytes`, `sha256`, and `attributes`

The request validator requires the appropriate content field for each input
type. It does not accept a local filesystem path as a file reference.

## Response

The Pydantic response model is `VerificationResponse`.

```json
{
  "request_id": "00000000-0000-4000-8000-000000000000",
  "status": "unavailable",
  "is_mock": true,
  "prediction_type": "evidence_verification",
  "evidence_status": "not_implemented",
  "verdict": null,
  "dataset_prediction": null,
  "model_identity": null,
  "dataset_identity": null,
  "confidence": null,
  "confidence_semantics": "not_available",
  "explanation_provenance": "mock_notice",
  "modality_weights": [],
  "diagnostic_signals": [],
  "reasoning": {},
  "explanation": "Evidence-based factual verification is not implemented. No verdict or confidence score was produced.",
  "errors": []
}
```

The response explicitly marks itself as mock and unavailable. It contains no
prediction, verdict, or confidence value. Dataset classification is a separate
prediction type and must include its dataset identity; its score must not be
described as factual confidence. Allowed evidence verdicts are
`SUPPORTED`, `REFUTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, and
`CHERRY_PICKING`; the schema rejects verdicts unless evidence evaluation is
marked as evaluated.

Any future `youtube_url` processing must document whether it handles only
acquired description text; it must not imply video or audio analysis unless
those modalities are actually processed.

| Field                   | Type        | Description                                                     |
| ----------------------- | ----------- | --------------------------------------------------------------- |
| `request_id`            | UUID        | Correlates the response with the request                        |
| `status`                | enum        | `completed`, `partial`, `failed`, or `unavailable`               |
| `is_mock`               | boolean     | Whether the response came from the temporary mock pipeline      |
| `prediction_type`       | enum        | `evidence_verification` or `dataset_classification`               |
| `evidence_status`       | enum        | `not_implemented`, `unavailable`, `not_applicable`, `evaluated`, or `failed` |
| `verdict`               | enum/null   | Evidence verdict; only populated after evidence evaluation       |
| `dataset_prediction`   | string/null | Dataset-label output, separately scoped from factual verdicts    |
| `model_identity`        | string/null | Model name/version when an actual model produced the output      |
| `dataset_identity`      | string/null | Dataset/release scope for a dataset-classification output       |
| `confidence`            | number/null | Unit-interval score only when accompanied by explicit `confidence_semantics`; never a factual-truth score |
| `confidence_semantics`  | enum        | `calibrated_class_probability`, `uncalibrated_dataset_score`, or `not_available` |
| `explanation_provenance`| enum        | `mock_notice`, `evidence_evaluator`, or `dataset_classifier`     |
| `modality_weights`       | array       | Configured heuristic weights, not measured classifier attribution |
| `diagnostic_signals`     | array       | Named measurements; not evidence that a claim is true or an explanation of classifier causality |
| `reasoning`             | object      | RR output passed from CMREF toward CMREA                        |
| `explanation`           | string/null | Human-readable CMREA explanation                                |
| `errors`                | array       | Structured processing errors; may coexist with `partial` status |

## Errors

Each error contains:

```json
{
  "code": "CONTENT_UNAVAILABLE",
  "message": "The referenced content could not be acquired.",
  "field": "content.file_reference"
}
```

Transport-level HTTP errors and application-level `errors` are separate. A
request validation failure is returned by FastAPI before the pipeline is
invoked; a partial pipeline result can return HTTP success with `status` set to
`partial` and populated `errors`.

## Multipart consideration

The schemas describe the normalized internal contract. A future API adapter
may accept `multipart/form-data` with an upload field named `file` plus
`input_type`, `request_id`, and serialized processing options. That adapter
must normalize the upload into `ContentMetadata.file_reference` before calling
the pipeline. No multipart endpoint or file processing is implemented here.

## Mock behavior

`POST /api/v1/verify` currently performs Pydantic validation and delegates to
`MockVerificationPipeline`. It returns `status: "unavailable"`, `is_mock:
true`, `evidence_status: "not_implemented"`, `verdict: null`, and
`confidence: null`. The notice is not an evidence-based explanation. No
models are loaded, and no inference is performed.
