const EVIDENCE_VERDICTS = new Set([
  "SUPPORTED",
  "REFUTED",
  "INSUFFICIENT_EVIDENCE",
  "CONFLICTING_EVIDENCE",
  "CHERRY_PICKING",
]);

export function createUnavailableVerification({
  type = "text",
  content = "",
  fileName = "",
} = {}) {
  const timestamp = new Date().toLocaleString();

  return {
    id: Date.now(),
    predictionType: "evidence_verification",
    datasetPrediction: null,
    modelIdentity: null,
    datasetIdentity: null,
    verdict: null,
    confidence: null,
    confidenceSemantics: "not_available",
    isMock: true,
    evidenceStatus: "not_implemented",
    explanationProvenance: "mock_notice",
    status: "unavailable",
    label: "Verification unavailable",
    explanation:
      "Evidence-based factual verification is not implemented. No verdict or confidence score was produced.",
    reasoning: [],
    contentType: type,
    inputContent: content,
    fileName,
    reportId: null,
    processingTime: null,
    time: timestamp,
    method: "mock-unavailable",
    text: (content || fileName || "Content submitted").slice(0, 120),
  };
}

export function getPredictionPresentation(result) {
  const predictionType =
    result?.predictionType ?? result?.prediction_type;
  const evidenceStatus =
    result?.evidenceStatus ?? result?.evidence_status;
  const verdict = result?.verdict;
  const scoreSemantics =
    result?.confidenceSemantics ?? result?.confidence_semantics;
  const datasetPrediction =
    result?.datasetPrediction ?? result?.dataset_prediction;
  const classScores = result?.classScores ?? result?.class_scores;
  const datasetScore =
    result?.datasetScore ??
    result?.dataset_score ??
    classScores?.[datasetPrediction];
  const scoreValue =
    predictionType === "dataset_classification"
      ? datasetScore
      : result?.confidence;
  const scoreAvailable =
    Number.isFinite(scoreValue) &&
    scoreValue >= 0 &&
    scoreValue <= 1 &&
    ["calibrated_class_probability", "uncalibrated_dataset_score"].includes(
      scoreSemantics
    );

  if (
    predictionType === "dataset_classification"
  ) {
    const datasetLabel = datasetPrediction || "unavailable";
    const datasetName =
      result.datasetIdentity ||
      result.dataset_identity ||
      "Unspecified dataset";
    return {
      kind: "dataset_classification",
      title: `${datasetName} Dataset-Label Prediction`,
      summary: `${datasetName} label: ${datasetLabel}`,
      score: scoreAvailable ? scoreValue * 100 : null,
      scoreLabel: scoreAvailable ? "Dataset-classification score" : null,
      scoreSemantics: scoreAvailable ? scoreSemantics : "not_available",
    };
  }

  if (
    predictionType === "evidence_verification" &&
    evidenceStatus === "evaluated" &&
    EVIDENCE_VERDICTS.has(verdict)
  ) {
    return {
      kind: "evidence_verdict",
      title: "Evidence-Based Factual Verification",
      summary: verdict,
      score: scoreAvailable ? scoreValue * 100 : null,
      scoreLabel: scoreAvailable ? "Predicted-class probability" : null,
      scoreSemantics: scoreAvailable ? scoreSemantics : "not_available",
    };
  }

  if (predictionType === "evidence_verification") {
    return {
      kind: "evidence_unavailable",
      title: "Factual verification unavailable",
      summary: "No evidence-based verdict was generated.",
      score: null,
      scoreLabel: null,
      scoreSemantics: "not_available",
    };
  }

  return {
    kind: "legacy_unverified",
    title: "Legacy unverified prediction",
    summary: "Prediction semantics are unavailable.",
    score: null,
    scoreLabel: null,
    scoreSemantics: "unknown",
  };
}
