import { useContext, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";

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
      const label = item?.label || "";
      const itemConfidence = Number(item?.confidence || 0);
      const itemDate = getDate(item);

      const matchesSearch = text
        .toLowerCase()
        .includes(search.toLowerCase());

      const matchesResult =
        resultFilter === "all" ||
        (resultFilter === "real" &&
          label === "Real News") ||
        (resultFilter === "fake" &&
          label === "Fake News");

      const matchesConfidence =
        itemConfidence >= confidence;

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
    (item) => item.label === "Real News"
  ).length;

  const fakeCount = history.filter(
    (item) => item.label === "Fake News"
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
    if (!text) return "Verified Content";

    return text.length > 85
      ? `${text.substring(0, 85)}...`
      : text;
  };

  const viewReport = (item) => {
    const result =
      item.label === "Real News"
        ? "REAL"
        : "FAKE";

    window.alert(
      `Verification Report\n\n` +
      `Prediction: ${result}\n` +
      `Confidence: ${item.confidence}%\n` +
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
            Review, filter and manage all your
            previously verified content.
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
              Confidence (%)
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
            Real
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
            Fake
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
            Total Verifications
          </span>
        </div>

        <div>
          <strong className="summary-real">
            {realCount}
          </strong>
          <span>
            Real Content
          </span>
        </div>

        <div>
          <strong className="summary-fake">
            {fakeCount}
          </strong>
          <span>
            Fake Content
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

            const isReal =
              item.label === "Real News";

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
                      alt="Verified content"
                    />
                  ) : (
                    <div className="history-generated-preview">

                      <span>
                        {isReal
                          ? "✓ VERIFIED"
                          : "⚠ REVIEW"}
                      </span>

                      <strong>
                        {getThumbnailText(
                          item.text
                        )}
                      </strong>

                      <small>
                        AI Verification Result
                      </small>

                    </div>
                  )}

                  <span
                    className={`history-image-label ${
                      isReal
                        ? "real-label"
                        : "fake-label"
                    }`}
                  >
                    {isReal
                      ? "REAL"
                      : "FAKE"}
                  </span>

                </div>

                {/* Content */}

                <div className="history-card-content">

                  <div className="history-prediction">

                    <span>
                      Prediction:
                    </span>

                    <strong
                      className={
                        isReal
                          ? "prediction-real"
                          : "prediction-fake"
                      }
                    >
                      {isReal
                        ? "REAL"
                        : "FAKE"}
                    </strong>

                  </div>

                  <div className="history-confidence-text">
                    Confidence:{" "}
                    <strong>
                      {item.confidence}%
                    </strong>
                  </div>

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
                  <span>
                    Click to view report
                  </span>

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
            Try changing your search or
            filter settings.
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