const verifyContent = async ({
  type = "text",
  content = "",
  file = null,
}) => {
  const submittedContent = String(content || "");
  const fileName = file?.originalname || "";
  const previewSource = submittedContent || fileName || "Content submitted";

  return {
    predictionType: "evidence_verification",
    datasetPrediction: null,
    modelIdentity: null,
    datasetIdentity: null,
    verdict: null,
    label: "Verification unavailable",
    confidence: null,
    confidenceSemantics: "not_available",
    isMock: true,
    evidenceStatus: "not_implemented",
    explanationProvenance: "mock_notice",
    status: "unavailable",
    fakeScore: null,
    trustedSource: null,
    explanation:
      "Evidence-based factual verification is not implemented. No verdict or confidence score was produced.",
    factors: null,
    reasoning: [],
    contentType: type,
    inputContent: submittedContent,
    fileName,
    reportId: null,
    processingTime: null,
    time: new Date().toLocaleString(),
    method: "mock-unavailable",
    text: previewSource.slice(0, 120),
  };
};

module.exports = {
  verifyContent,
};
