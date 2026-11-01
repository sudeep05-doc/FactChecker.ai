import assert from "node:assert/strict";
import test from "node:test";
import {
  createUnavailableVerification,
  getPredictionPresentation,
} from "./prediction.js";

test("unavailable verification never returns a verdict or confidence", () => {
  const originalRandom = Math.random;
  Math.random = () => {
    throw new Error("random output is forbidden");
  };

  try {
    const result = createUnavailableVerification({
      type: "text",
      content: "A statement submitted for checking.",
    });

    assert.equal(result.status, "unavailable");
    assert.equal(result.isMock, true);
    assert.equal(result.evidenceStatus, "not_implemented");
    assert.equal(result.verdict, null);
    assert.equal(result.confidence, null);
    assert.equal(result.label, "Verification unavailable");
  } finally {
    Math.random = originalRandom;
  }
});

test("dataset output is presented as a dataset label, never a factual verdict", () => {
  const presentation = getPredictionPresentation({
    predictionType: "dataset_classification",
    datasetIdentity: "Fakeddit",
    datasetPrediction: "FAKE",
    datasetScore: 0.82,
    confidenceSemantics: "uncalibrated_dataset_score",
  });

  assert.equal(presentation.kind, "dataset_classification");
  assert.equal(presentation.title, "Fakeddit Dataset-Label Prediction");
  assert.match(presentation.summary, /Fakeddit label: FAKE/);
  assert.equal(
    presentation.scoreSemantics,
    "uncalibrated_dataset_score"
  );
  assert.equal(presentation.score, 82);
  assert.notEqual(presentation.summary, "REFUTED");
});

test("Task 47 snake_case payload retains dataset scope and score semantics", () => {
  const presentation = getPredictionPresentation({
    prediction_type: "dataset_classification",
    dataset_identity: "Fakeddit 2-way distant-supervision label",
    dataset_prediction: "REAL",
    dataset_score: 0.61,
    confidence_semantics: "uncalibrated_dataset_score",
  });

  assert.equal(presentation.kind, "dataset_classification");
  assert.equal(presentation.score, 61);
  assert.match(presentation.title, /Dataset-Label Prediction/);
  assert.match(presentation.summary, /Fakeddit.*label: REAL/);
});

test("legacy prediction records are not treated as verified verdicts or scores", () => {
  const presentation = getPredictionPresentation({
    label: "Real News",
    confidence: 94,
  });

  assert.equal(presentation.kind, "legacy_unverified");
  assert.equal(presentation.scoreLabel, null);
});

test("unrecognized labels are not treated as evidence verdicts", () => {
  const presentation = getPredictionPresentation({
    predictionType: "evidence_verification",
    evidenceStatus: "evaluated",
    verdict: "LIKELY_FAKE",
  });

  assert.equal(presentation.kind, "evidence_unavailable");
});
