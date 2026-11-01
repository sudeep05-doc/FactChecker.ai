import { useContext, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import { getPredictionPresentation } from "../../utils/prediction";

const isDatasetClassification = (item) =>
  item?.predictionType === "dataset_classification" ||
  item?.prediction_type === "dataset_classification";

const getDatasetLabel = (item) =>
  String(item?.datasetPrediction || item?.dataset_prediction || "").toUpperCase();

const History = () => {
  const {
    history,
    setHistory,
    exportHistory,
  } = useContext(AppContext);

  const [search, setSearch] = useState("");
  const [resultFilter, setResultFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all");
  const [confidence, setConfidence] = useState(0);

  const getDate = (item) => {
    if (!item?.time) return null;

    const date = new Date(item.time);

    if (!Number.isNaN(date.getTime())) {
      return date;
    }

    return null;
  };

  const filteredHistory = useMemo(() => {
    const now = new Date();

    return history.filter((item) => {
      const text = item?.text || "";
      const itemScore = getPredictionPresentation(item).score;
      const itemDate = getDate(item);

      const matchesSearch = text
        .toLowerCase()
        .includes(search.toLowerCase());

      const matchesResult =
        resultFilter === "all" ||
        (resultFilter === "real" &&
          isDatasetClassification(item) &&
          ["REAL", "REAL NEWS"].includes(getDatasetLabel(item))) ||
        (resultFilter === "fake" &&
          isDatasetClassification(item) &&
          ["FAKE", "FAKE NEWS"].includes(getDatasetLabel(item)));

      const matchesConfidence =
        confidence === 0 ||
        (isDatasetClassification(item) &&
          itemScore !== null &&
          itemScore >= confidence);

      let matchesDate = true;

      if (dateFilter !== "all" && itemDate) {
        const difference =
          now.getTime() - itemDate.getTime();

        const days =
          difference / (1000 * 60 * 60 * 24);

        if (dateFilter === "today") {
          matchesDate =
            itemDate.toDateString() ===
            now.toDateString();
        }

        if (dateFilter === "7days") {
          matchesDate = days <= 7;
        }

        if (dateFilter === "30days") {
          matchesDate = days <= 30;
        }
      }

      return (
        matchesSearch &&
        matchesResult &&
        matchesConfidence &&
        matchesDate
      );
    });
  }, [
    history,
    search,
    resultFilter,
    dateFilter,
    confidence,
  ]);

  const realCount = history.filter(
    (item) =>
      isDatasetClassification(item) &&
      ["REAL", "REAL NEWS"].includes(getDatasetLabel(item))
  ).length;

  const fakeCount = history.filter(
    (item) =>
      isDatasetClassification(item) &&
      ["FAKE", "FAKE NEWS"].includes(getDatasetLabel(item))
  ).length;

  const deleteAnalysis = (id) => {
    const updated = history.filter(
      (item) => item.id !== id
    );

    setHistory(updated);
  };

  const clearHistory = () => {
    if (
      window.confirm(
        "Are you sure you want to clear all verification history?"
      )
    ) {
      setHistory([]);
    }
  };

  const formatDate = (item) => {
    const date = getDate(item);

    if (!date) {
      return item?.time || "Unknown date";
    }

    return date.toLocaleDateString(
      "en-US",
      {
        month: "short",
        day: "numeric",
        year: "numeric",
      }
    );
  };

  const getThumbnailText = (text) => {
    if (!text) return "Submitted Content";

    return text.length > 85
      ? `${text.substring(0, 85)}...`
      : text;
  };

  const viewReport = (item) => {
    const presentation = getPredictionPresentation(item);
    const predictionSummary = presentation.summary;
    const scoreSummary =
      isDatasetClassification(item) && presentation.score !== null
        ? `\nDataset-classification score: ${presentation.score}% (${presentation.scoreSemantics === "uncalibrated_dataset_score" ? "uncalibrated" : "calibrated class probability"})`
        : "";

    window.alert(
      `Prediction History Record\n\n` +
      `${predictionSummary}${scoreSummary}\n` +
      `Date: ${formatDate(item)}\n\n` +
      `${item.text}`
    );
  };

  return (
    <div className="truthlog-history-page">

      {/* =================================================
          PAGE HEADER
      ================================================= */}

      <div className="truthlog-history-header">

        <div>
          <span className="history-eyebrow">
            VERIFICATION CENTER
          </span>

          <h1>
            TruthLog - Verification History
          </h1>

          <p>
            Review saved records. Legacy predictions are unverified, and
            dataset labels are not factual verdicts.
          </p>
        </div>

        <div className="history-header-actions">

          <button
            className="history-export-button"
            onClick={exportHistory}
          >
            ↓ Export
          </button>

          <button
            className="history-clear-button"
            onClick={clearHistory}
          >
            Clear History
          </button>

        </div>

      </div>

      {/* =================================================
          SEARCH
      ================================================= */}

      <div className="history-search-box">

        <span className="history-search-icon">
          ⌕
        </span>

        <input
          type="text"
          placeholder="Search verified content, articles, claims..."
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
        />

        {search && (
          <button
            className="history-search-clear"
            onClick={() => setSearch("")}
          >
            ×
          </button>
        )}

      </div>

      {/* =================================================
          FILTERS
      ================================================= */}

      <div className="history-filter-bar">

        <div className="history-date-filter">

          <span>▣</span>

          <select
            value={dateFilter}
            onChange={(event) =>
              setDateFilter(event.target.value)
            }
          >
            <option value="all">
              All Dates
            </option>

            <option value="today">
              Today
            </option>

            <option value="7days">
              Last 7 Days
            </option>

            <option value="30days">
              Last 30 Days
            </option>
          </select>

        </div>

        <div className="history-confidence">

          <div className="confidence-filter-title">
            <span>
              Dataset score (%)
            </span>

            <strong>
              {confidence}%
            </strong>
          </div>

          <input
            type="range"
            min="0"
            max="100"
            value={confidence}
            onChange={(event) =>
              setConfidence(
                Number(event.target.value)
              )
            }
          />

          <div className="confidence-range">
            <span>0</span>
            <span>50</span>
            <span>100</span>
          </div>

        </div>

        <div className="history-result-filters">

          <button
            className={
              resultFilter === "all"
                ? "active"
                : ""
            }
            onClick={() =>
              setResultFilter("all")
            }
          >
            All
          </button>

          <button
            className={`real-filter ${
              resultFilter === "real"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setResultFilter("real")
            }
          >
            <span>✓</span>
            Dataset REAL
          </button>

          <button
            className={`fake-filter ${
              resultFilter === "fake"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setResultFilter("fake")
            }
          >
            <span>■</span>
            Dataset FAKE
          </button>

        </div>

      </div>

      {/* =================================================
          SUMMARY
      ================================================= */}

      <div className="history-mini-summary">

        <div>
          <strong>
            {history.length}
          </strong>
          <span>
            Total Records
          </span>
        </div>

        <div>
          <strong className="summary-real">
            {realCount}
          </strong>
          <span>
            Dataset REAL labels
          </span>
        </div>

        <div>
          <strong className="summary-fake">
            {fakeCount}
          </strong>
          <span>
            Dataset FAKE labels
          </span>
        </div>

        <div>
          <strong>
            {filteredHistory.length}
          </strong>
          <span>
            Showing Results
          </span>
        </div>

      </div>

      {/* =================================================
          RESULTS
      ================================================= */}

      {filteredHistory.length > 0 ? (

        <div className="truthlog-history-grid">

          {filteredHistory.map((item) => {

            const isDataset =
              isDatasetClassification(item);
            const datasetLabel = getDatasetLabel(item);
            const isReal =
              isDataset &&
              ["REAL", "REAL NEWS"].includes(datasetLabel);
            const isFake =
              isDataset &&
              ["FAKE", "FAKE NEWS"].includes(datasetLabel);
            const isMock = item.isMock ?? item.is_mock;
            const presentation = getPredictionPresentation(item);
            const predictionSummary = presentation.summary;

            const image =
              item.image ||
              item.thumbnail ||
              item.imageUrl;

            return (
              <article
                className="truthlog-history-card"
                key={item.id}
              >

                {/* Thumbnail */}

                <div
                  className={`history-card-thumbnail ${
                    isReal
                      ? "thumbnail-real"
                      : "thumbnail-fake"
                  }`}
                >

                  {image ? (
                    <img
                      src={image}
                      alt="Submitted content"
                    />
                  ) : (
                    <div className="history-generated-preview">

                      <span>
                        {isDataset
                          ? "DATASET LABEL"
                          : item.predictionType === "evidence_verification"
                            ? presentation.kind === "evidence_verdict"
                              ? "EVIDENCE VERDICT"
                              : "NOT VERIFIED"
                            : "LEGACY UNVERIFIED"}
                      </span>

                      <strong>
                        {getThumbnailText(
                          item.text
                        )}
                      </strong>

                      <small>
                        {isMock
                          ? "Mock placeholder; no model inference"
                          : isDataset
                          ? "Not a factual verification"
                          : presentation.kind === "evidence_verdict"
                            ? "Evidence status: " + (item.evidenceStatus || "evaluated")
                            : "Prediction semantics unavailable"}
                      </small>

                    </div>
                  )}

                  <span
                    className={`history-image-label ${
                      isReal
                        ? "real-label"
                        : isFake
                          ? "fake-label"
                          : ""
                    }`}
                  >
                    {isDataset
                      ? datasetLabel || "UNKNOWN"
                      : item.predictionType === "evidence_verification"
                        ? item.verdict || "UNAVAILABLE"
                        : "UNVERIFIED"}
                  </span>

                </div>

                {/* Content */}

                <div className="history-card-content">

                  <div className="history-prediction">

                    <span>Result type:</span>

                    <strong
                      className={isReal ? "prediction-real" : isFake ? "prediction-fake" : ""}
                    >
                      {predictionSummary}
                    </strong>

                  </div>

                  {isDataset && presentation.score !== null && (
                    <div className="history-confidence-text">
                      Dataset-classification score:{" "}
                      <strong>
                        {presentation.score}%
                        {presentation.scoreSemantics === "uncalibrated_dataset_score"
                          ? " (uncalibrated; not factual confidence)"
                          : " (class probability; not factual confidence)"}
                      </strong>
                    </div>
                  )}

                  <div className="history-date-text">
                    Date:{" "}
                    <strong>
                      {formatDate(item)}
                    </strong>
                  </div>

                </div>

                {/* Footer */}

                <button
                  className="history-report-button"
                  onClick={() =>
                    viewReport(item)
                  }
                >
                  <span>View record details</span>

                  <strong>
                    →
                  </strong>
                </button>

                <button
                  className="history-delete-card"
                  title="Delete verification"
                  onClick={() =>
                    deleteAnalysis(item.id)
                  }
                >
                  ×
                </button>

              </article>
            );
          })}

        </div>

      ) : (

        <div className="truthlog-empty-history">

          <div className="empty-history-icon">
            ◫
          </div>

          <h2>
            No verification records found
          </h2>

          <p>
            Try changing your search or filters. This does not indicate that a
            claim was verified.
          </p>

          <button
            onClick={() => {
              setSearch("");
              setResultFilter("all");
              setDateFilter("all");
              setConfidence(0);
            }}
          >
            Reset Filters
          </button>

        </div>

      )}

    </div>
  );
};

export default History;