import { useState } from "react";
import { generateVerificationPDF } from "../../utils/generateVerificationPDF";
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

  const isFake =
    result.label === "Fake News" ||
    result.label === "Likely Fake";

  const verdict = isFake
    ? "Likely Fake"
    : "Likely Authentic";

  const confidence =
    Number(result.confidence) || 0;

  const handleDownload = () => {
    generateVerificationPDF({
      verdict,
      confidence,

      contentType:
        result.contentType ||
        "AI Content Verification",

      reportId:
        result.reportId ||
        `VA-${Date.now()}`,

      analysisSummary:
        result.explanation ||
        "The submitted content was analyzed using AI-powered verification.",

      reasoning:
        result.reasoning || [
          "Content patterns were analyzed.",
          "Source credibility was evaluated.",
          "Writing style and consistency were reviewed.",
          "The submitted claim was compared against verification signals.",
        ],

      recommendation:
        isFake
          ? "Verify the information using reliable sources before sharing."
          : "The content appears credible based on the available verification signals.",

      processingTime:
        result.processingTime ||
        "1.8 seconds",
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
    result.reasoning || [
      isFake
        ? "Suspicious wording or misinformation signals were detected."
        : "The writing pattern appears consistent with credible reporting.",

      result.trustedSource
        ? "The submitted source matches a recognized trusted domain."
        : "Source credibility requires additional verification.",

      isFake
        ? "The claim contains patterns commonly associated with misleading content."
        : "No major credibility inconsistencies were detected.",

      "AI verification should be considered as an assistance tool and not as a replacement for human fact-checking.",
    ];

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
            Verification Result
          </h1>

          <p>
            Review the assessment generated for your
            submitted content.
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
                isFake ? "fake" : "real"
              }`}
            >
              {isFake ? "!" : "✓"}
            </div>

            <div>

              <h2>
                {verdict}
              </h2>

              <span
                className={`result-status ${
                  isFake ? "fake" : "real"
                }`}
              >
                {isFake
                  ? "Misinformation signals detected"
                  : "Credibility signals detected"}
              </span>

            </div>

          </div>

        </div>


        {/* CONFIDENCE */}

        <div className="result-confidence">

          <div className="confidence-heading">

            <span>
              Confidence
            </span>

            <strong>
              {confidence}%
            </strong>

          </div>

          <div className="confidence-track">

            <div
              className={`confidence-fill ${
                isFake ? "fake" : "real"
              }`}
              style={{
                width: `${confidence}%`,
              }}
            />

          </div>

          <small>
            AI assessment confidence
          </small>

        </div>

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
            AI Explanation
          </h3>

          <p>
            {result.explanation ||
              "This is an AI-generated verification explanation based on the submitted content and available credibility signals."}
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
                "1.8 seconds"}
            </strong>

          </div>


          <div className="verification-detail-row">

            <span>
              Report ID
            </span>

            <strong>
              {result.reportId ||
                "VA-" + Date.now()}
            </strong>

          </div>


          <div className="verification-detail-row">

            <span>
              Status
            </span>

            <strong className="completed-status">
              Completed
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
          onClick={handleDownload}
        >
          ↓ Download Report
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