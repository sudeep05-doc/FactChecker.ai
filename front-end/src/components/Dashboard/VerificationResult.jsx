import { useState } from "react";
import { generateVerificationPDF } from "../../utils/generateVerificationPDF";
import { getPredictionPresentation } from "../../utils/prediction";
import "./VerificationResult.css";

const VerificationResult = ({
  result,
  setActiveView,
}) => {
  const [feedback, setFeedback] = useState(null);

  if (!result) {
    return (
      <div className="verification-result-empty">
        <div className="result-empty-icon">✓</div>

        <h2>No verification result yet</h2>

        <p>
          Submit an article, text, URL, image, PDF, or video
          to generate a verification report.
        </p>

        <button
          onClick={() => setActiveView("analyze")}
        >
          Verify Content
        </button>
      </div>
    );
  }

  const presentation = getPredictionPresentation(result);
  const isDatasetClassification =
    presentation.kind === "dataset_classification";
  const isEvidenceEvaluated =
    presentation.kind === "evidence_verdict";
  const isUnavailable = !isDatasetClassification && !isEvidenceEvaluated;
  const datasetPrediction =
    result.datasetPrediction ?? result.dataset_prediction;
  const datasetIdentity =
    result.datasetIdentity ?? result.dataset_identity;
  const mockStatus = result.isMock ?? result.is_mock;
  const isFake =
    result.verdict === "REFUTED" ||
    ["FAKE", "Fake News"].includes(datasetPrediction);
  const isPositive =
    result.verdict === "SUPPORTED" ||
    ["REAL", "Real News"].includes(datasetPrediction);
  const resultTone = isUnavailable || isDatasetClassification
    ? ""
    : isFake
      ? "fake"
      : isPositive
        ? "real"
        : "";
  const verdict = presentation.title;
  const confidence = presentation.score;

  const handleDownload = () => {
    if (!isEvidenceEvaluated) {
      return;
    }

    generateVerificationPDF({
      verdict: result.verdict,
      confidence: null,

      contentType:
        result.contentType ||
        "Submitted content",

      reportId:
        result.reportId ||
        "Not generated",

      analysisSummary:
        result.explanation ||
        "No explanation is available.",

      reasoning:
        Array.isArray(result.reasoning) ? result.reasoning : [],

      recommendation: "Review the cited evidence before relying on this result.",

      processingTime:
        result.processingTime ||
        "Not run",
    });
  };

  const handleFeedback = (value) => {
    setFeedback(value);
  };

  const getInputType = () => {
    switch (result.contentType) {
      case "youtube":
        return "YouTube URL";

      case "website":
        return "Website URL";

      case "image":
        return "Image";

      case "pdf":
        return "PDF Document";

      case "video":
        return "Video";

      case "text":
        return "Text";

      default:
        return result.contentType ||
          "Text Analysis";
    }
  };

  const reasoning =
    Array.isArray(result.reasoning) ? result.reasoning : [];

  return (
    <div className="verification-result-page">

      {/* =========================================
          PAGE HEADER
      ========================================== */}

      <div className="verification-result-heading">

        <div>

          <span className="verification-result-eyebrow">
            VERIFACT AI
          </span>

          <h1>
            {presentation.title}
          </h1>

          <p>
            {isDatasetClassification
              ? "This output predicts a dataset label and is not an evidence-based factual verdict."
              : isEvidenceEvaluated
                ? "Review the verdict and its evaluated evidence."
                : "Evidence-based factual verification is unavailable; no verdict was generated."}
          </p>

        </div>

      </div>


      {/* =========================================
          RESULT SUMMARY
      ========================================== */}

      <section className="result-verdict-card">

        <div className="result-verdict-left">

          <span className="result-small-label">
            Assessment
          </span>

          <div className="result-verdict-row">

            <div
              className={`result-verdict-icon ${
                resultTone
              }`}
            >
              {isUnavailable || isDatasetClassification || (!isFake && !isPositive)
                ? "?"
                : isFake
                  ? "!"
                  : "✓"}
            </div>

            <div>

              <h2>
                {verdict}
              </h2>

              <span
                className={`result-status ${
                  resultTone
                }`}
              >
                {isDatasetClassification
                  ? `Dataset: ${datasetIdentity || "unspecified"}; not a factual verdict`
                  : isEvidenceEvaluated
                    ? "Verdict based on evaluated evidence"
                    : "Evidence evaluation is not implemented"}
              </span>

            </div>

          </div>

        </div>


        {/* CONFIDENCE */}

        {confidence !== null && Number.isFinite(confidence) ? (
        <div className="result-confidence">

          <div className="confidence-heading">

            <span>
              {presentation.scoreLabel}
            </span>

            <strong>
              {confidence}%
            </strong>

          </div>

          <div className="confidence-track">

            <div
              className={`confidence-fill ${resultTone}`}
              style={{
                width: `${confidence}%`,
              }}
            />

          </div>

          <small>
            {presentation.scoreSemantics === "uncalibrated_dataset_score"
              ? "Uncalibrated dataset score; not factual confidence"
              : "Class probability; not factual confidence"}
          </small>

        </div>
        ) : (
          <div className="result-confidence">
            <div className="confidence-heading">
              <span>Confidence</span>
              <strong>Not available</strong>
            </div>
            <small>No factual confidence score is produced.</small>
          </div>
        )}

      </section>


      {/* =========================================
          AI EXPLANATION
      ========================================== */}

      <section className="result-info-card">

        <div className="result-card-icon purple">
          ✦
        </div>

        <div className="result-card-content">

          <h3>
            {isDatasetClassification
              ? "Dataset-Label Scope"
              : "Verification Status"}
          </h3>

          <p>
            {isDatasetClassification
              ? "The output is limited to the named dataset label; it does not establish whether a claim is true or false."
              : result.explanation ||
                "Evidence-based factual verification is not implemented."}
          </p>

        </div>

      </section>


      {/* =========================================
          REASONING SUMMARY
      ========================================== */}

      <section className="result-info-card reasoning-card">

        <div className="result-card-icon blue">
          ≡
        </div>

        <div className="result-card-content">

          <h3>
            Reasoning Summary
          </h3>

          <div className="reasoning-list">

            {reasoning.map(
              (item, index) => (

                <div
                  className="reasoning-item"
                  key={index}
                >

                  <span>
                    {index + 1}
                  </span>

                  <p>
                    {item}
                  </p>

                </div>

              )
            )}
            {reasoning.length === 0 && (
              <p>
                {isDatasetClassification
                  ? "No evidence was evaluated; this dataset label is not a factual verdict."
                  : "No evidence-based reasoning is available."}
              </p>
            )}

          </div>

        </div>

      </section>


      {/* =========================================
          VERIFICATION DETAILS
      ========================================== */}

      <section className="result-details-card">

        <div className="details-heading">

          <div className="result-card-icon green">
            ✓
          </div>

          <div>

            <h3>
              Verification Details
            </h3>

            <p>
              Technical information about this assessment.
            </p>

          </div>

        </div>


        <div className="verification-details-list">

          <div className="verification-detail-row">

            <span>
              Input Type
            </span>

            <strong>
              {getInputType()}
            </strong>

          </div>


          <div className="verification-detail-row">

            <span>
              Processing Time
            </span>

            <strong>
              {result.processingTime ||
                "Not run"}
            </strong>

          </div>


          <div className="verification-detail-row">

            <span>
              Report ID
            </span>

            <strong>
              {result.reportId || "Not generated"}
            </strong>

          </div>


          <div className="verification-detail-row">

            <span>
              Status
            </span>

            <strong className="completed-status">
              {result.status || "unavailable"}
            </strong>
          </div>

          <div className="verification-detail-row">
            <span>Mock response</span>
            <strong>
              {mockStatus == null ? "Unknown" : mockStatus ? "Yes" : "No"}
            </strong>
          </div>

        </div>

      </section>


      {/* =========================================
          ACTIONS
      ========================================== */}

      <div className="verification-result-actions">

        <button
          className="verify-again-btn"
          onClick={() =>
            setActiveView("analyze")
          }
        >
          ← Verify Again
        </button>


        <button
          className="download-report-btn"
          disabled={!isEvidenceEvaluated}
          onClick={handleDownload}
        >
          {isEvidenceEvaluated
            ? "↓ Download Report"
            : "Report unavailable"}
        </button>

      </div>


      {/* =========================================
          FEEDBACK
      ========================================== */}

      <section className="result-feedback">

        <div>

          <h3>
            Was this result helpful?
          </h3>

          <p>
            Your feedback helps improve the verification
            experience.
          </p>

        </div>


        <div className="feedback-buttons">

          <button
            className={
              feedback === "helpful"
                ? "selected"
                : ""
            }
            onClick={() =>
              handleFeedback("helpful")
            }
          >
            👍 Helpful
          </button>

          <button
            className={
              feedback === "not-helpful"
                ? "selected"
                : ""
            }
            onClick={() =>
              handleFeedback("not-helpful")
            }
          >
            👎 Not helpful
          </button>

        </div>

      </section>

    </div>
  );
};

export default VerificationResult;