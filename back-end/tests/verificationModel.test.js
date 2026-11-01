const assert = require("node:assert/strict");
const test = require("node:test");
const mongoose = require("mongoose");
const Verification = require("../models/Verification");

const baseRecord = () => ({
  user: new mongoose.Types.ObjectId(),
  label: "Verification unavailable",
  predictionType: "evidence_verification",
  confidence: null,
  confidenceSemantics: "not_available",
  isMock: true,
  evidenceStatus: "not_implemented",
  explanationProvenance: "mock_notice",
  status: "unavailable",
  verdict: null,
  reportId: null,
});

test("database contract accepts an unavailable mock without score or verdict", async () => {
  await new Verification(baseRecord()).validate();
});

test("database contract rejects mock verdicts and confidence", async () => {
  const record = new Verification({
    ...baseRecord(),
    verdict: "SUPPORTED",
    confidence: 0.9,
  });

  await assert.rejects(record.validate(), /Mock records cannot contain/);
});

test("database contract accepts scoped dataset labels without factual verdicts", async () => {
  const record = new Verification({
    ...baseRecord(),
    isMock: false,
    predictionType: "dataset_classification",
    datasetPrediction: "FAKE",
    datasetScore: 0.82,
    classScores: { FAKE: 0.82, REAL: 0.18 },
    datasetIdentity: "Fakeddit 2-way distant-supervision label",
    modelIdentity: "task47/text_only",
    confidenceSemantics: "uncalibrated_dataset_score",
    evidenceStatus: "not_applicable",
    explanationProvenance: "dataset_classifier",
    status: "completed",
  });

  await record.validate();
  assert.equal(record.verdict, null);
});

test("dataset-classification labels cannot be persisted as evidence verdicts", async () => {
  const record = new Verification({
    ...baseRecord(),
    isMock: false,
    predictionType: "dataset_classification",
    datasetPrediction: "FAKE",
    datasetIdentity: "Fakeddit",
    modelIdentity: "model@version",
    confidence: 0.82,
    confidenceSemantics: "uncalibrated_dataset_score",
    explanationProvenance: "dataset_classifier",
    evidenceStatus: "evaluated",
    verdict: "REFUTED",
  });

  await assert.rejects(record.validate(), /Dataset predictions require/);
});

test("legacy records retain explicit unknown semantics in history serialization", () => {
  const record = new Verification({
    ...baseRecord(),
    predictionType: undefined,
    confidence: 94,
    confidenceSemantics: undefined,
    isMock: undefined,
    evidenceStatus: undefined,
    explanationProvenance: undefined,
    status: undefined,
    label: "Real News",
  });

  const history = record.toHistoryJSON();
  assert.equal(history.predictionType, "legacy_unverified");
  assert.equal(history.confidenceSemantics, "legacy_unknown");
  assert.equal(history.isMock, null);
  assert.equal(history.evidenceStatus, "not_available");
  assert.equal(history.label, "Real News");
  assert.equal(history.confidence, 94);
});
