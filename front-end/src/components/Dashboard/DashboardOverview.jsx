import { useContext, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import "./DashboardOverview.css";

const DAY_MS = 24 * 60 * 60 * 1000;

const formatNumber = (value) =>
  Number(value || 0).toLocaleString();

const getRecordDate = (record) => {
  const timestamp =
    typeof record?.id === "number" && record.id > 0
      ? record.id
      : null;
  const dateValue =
    record?.createdAt ||
    record?.timestamp ||
    record?.date ||
    record?.time;
  const parsedDate = dateValue ? new Date(dateValue) : null;

  if (timestamp && !Number.isNaN(new Date(timestamp).getTime())) {
    return new Date(timestamp);
  }

  return parsedDate && !Number.isNaN(parsedDate.getTime())
    ? parsedDate
    : null;
};

const getRecordCategory = (record) => {
  const type = record?.predictionType ?? record?.prediction_type;

  if (type === "dataset_classification") return "dataset";
  if (
    type === "evidence_verification" &&
    (record?.evidenceStatus ?? record?.evidence_status) === "evaluated" &&
    record?.verdict
  ) {
    return "evidence";
  }
  return "unavailable";
};

const getRecordTitle = (record) =>
  record?.text ||
  record?.inputContent ||
  record?.input_content ||
  record?.fileName ||
  record?.file_name ||
  "Submitted content";

const getRecordType = (record) => {
  const rawType =
    record?.contentType ??
    record?.content_type ??
    record?.type ??
    "other";
  const type = String(rawType).toLowerCase();

  if (type.includes("url") || type.includes("website")) return "Website";
  if (type.includes("image")) return "Image";
  if (type.includes("video")) return "Video";
  if (type.includes("pdf") || type.includes("document")) return "Document";
  if (type.includes("text")) return "Text";
  return "Other";
};

const getStatusLabel = (record) => {
  const category = getRecordCategory(record);

  if (category === "dataset") {
    const label =
      record?.datasetPrediction ??
      record?.dataset_prediction ??
      "Label recorded";
    return `Dataset: ${label}`;
  }
  if (category === "evidence") {
    return String(record.verdict).replaceAll("_", " ");
  }
  return "Verification unavailable";
};

const formatDate = (date) =>
  date
    ? date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
    : "Date unavailable";

const makeLinePath = (values, maxValue) =>
  values
    .map((value, index) => {
      const x = 50 + (index * 500) / Math.max(values.length - 1, 1);
      const y = 172 - (value / maxValue) * 142;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

const makeAreaPath = (values, maxValue) => {
  if (!values.length) return "";
  const line = makeLinePath(values, maxValue);
  return `${line} L 550 172 L 50 172 Z`;
};

function DashboardOverview({ setActiveView }) {
  const { history = [] } = useContext(AppContext);
  const [activityRange, setActivityRange] = useState("7days");

  const dashboardData = useMemo(() => {
    const records = Array.isArray(history) ? history : [];
    const recordsWithDate = records.map((record) => ({
      record,
      date: getRecordDate(record),
    }));
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const bucketCount = activityRange === "1year"
      ? 12
      : activityRange === "1month"
        ? 5
        : 7;
    const activityStart = activityRange === "1year"
      ? new Date(today.getFullYear(), today.getMonth() - 11, 1)
      : new Date(today.getTime() - (activityRange === "1month" ? 29 : 6) * DAY_MS);
    const activity = Array.from({ length: bucketCount }, (_, index) => {
      const date = activityRange === "1year"
        ? new Date(activityStart.getFullYear(), activityStart.getMonth() + index, 1)
        : new Date(activityStart.getTime() + index * (activityRange === "1month" ? 7 : 1) * DAY_MS);
      return {
        date,
        label: activityRange === "7days"
          ? date.toLocaleDateString(undefined, { weekday: "short" })
          : date.toLocaleDateString(undefined, activityRange === "1year"
            ? { month: "short" }
            : { month: "short", day: "numeric" }),
        total: 0,
        dataset: 0,
      };
    });

    recordsWithDate.forEach(({ record, date }) => {
      if (!date) return;
      const dayIndex = Math.floor(
        (new Date(date.getFullYear(), date.getMonth(), date.getDate()) -
          activityStart) / DAY_MS
      );
      const bucketIndex = activityRange === "1year"
        ? (date.getFullYear() - activityStart.getFullYear()) * 12 +
          date.getMonth() - activityStart.getMonth()
        : activityRange === "1month"
          ? Math.floor(dayIndex / 7)
          : dayIndex;
      if (bucketIndex < 0 || bucketIndex >= activity.length || date > now) return;
      activity[bucketIndex].total += 1;
      if (getRecordCategory(record) === "dataset") {
        activity[bucketIndex].dataset += 1;
      }
    });

    const datasetCount = records.filter(
      (record) => getRecordCategory(record) === "dataset"
    ).length;
    const evidenceCount = records.filter(
      (record) => getRecordCategory(record) === "evidence"
    ).length;
    const unavailableCount = records.length - datasetCount - evidenceCount;
    const contentTypes = ["Text", "Website", "Image", "Document", "Video", "Other"]
      .map((label) => ({
        label,
        count: records.filter((record) => getRecordType(record) === label).length,
      }))
      .filter((entry) => entry.count > 0)
      .sort((left, right) => right.count - left.count)
      .slice(0, 5);
    const recent = [...recordsWithDate]
      .sort((left, right) => (right.date?.getTime() || 0) - (left.date?.getTime() || 0))
      .slice(0, 5);

    return {
      records,
      activity,
      datasetCount,
      evidenceCount,
      unavailableCount,
      contentTypes,
      recent,
    };
  }, [history, activityRange]);

  const { records, activity, datasetCount, evidenceCount, unavailableCount, contentTypes, recent } =
    dashboardData;
  const maxActivity = Math.max(1, ...activity.map((bucket) => bucket.total));
  const activityScale = Math.ceil(maxActivity / 4) * 4 || 1;
  const datasetShare = records.length
    ? (datasetCount / records.length) * 100
    : 0;
  const evidenceShare = records.length
    ? (evidenceCount / records.length) * 100
    : 0;
  const unavailableShare = records.length
    ? (unavailableCount / records.length) * 100
    : 0;
  const contentTypeMax = Math.max(1, ...contentTypes.map((entry) => entry.count));

  return (
    <div className="misinfo-overview">
      <header className="misinfo-overview-top">
        <div>
          <span className="overview-kicker">FACTCHECKER OVERVIEW</span>
          <h1>Analysis Dashboard</h1>
          <p>
            A summary of your saved records. Dataset labels are not evidence-based
            factual verdicts.
          </p>
        </div>
        <button
          className="overview-analyze-btn"
          onClick={() => setActiveView?.("analyze")}
          type="button"
        >
          New analysis <span aria-hidden="true">↗</span>
        </button>
      </header>

      <section className="overview-stat-grid" aria-label="Analysis totals">
        <article className="overview-stat-card stat-purple">
          <span className="overview-stat-icon">▤</span>
          <div>
            <span>Saved records</span>
            <strong>{formatNumber(records.length)}</strong>
            <small>All content types</small>
          </div>
        </article>
        <article className="overview-stat-card stat-orange">
          <span className="overview-stat-icon">◈</span>
          <div>
            <span>Dataset-label outputs</span>
            <strong>{formatNumber(datasetCount)}</strong>
            <small>Not factual verdicts</small>
          </div>
        </article>
        <article className="overview-stat-card stat-green">
          <span className="overview-stat-icon">✓</span>
          <div>
            <span>Evidence verdicts</span>
            <strong>{formatNumber(evidenceCount)}</strong>
            <small>Evidence evaluation status</small>
          </div>
        </article>
        <article className="overview-stat-card stat-red">
          <span className="overview-stat-icon">!</span>
          <div>
            <span>Unavailable / legacy</span>
            <strong>{formatNumber(unavailableCount)}</strong>
            <small>No evidence verdict produced</small>
          </div>
        </article>
      </section>

      <section className="overview-main-grid">
        <article className="overview-panel trend-panel">
          <div className="overview-panel-header">
            <div>
              <h2>Analysis activity</h2>
              <small>
                Saved records {activityRange === "1year" ? "by month" : activityRange === "1month" ? "by week" : "by day"}
                {" · "}
                {activityRange === "1year" ? "last year" : activityRange === "1month" ? "last month" : "last 7 days"}
              </small>
            </div>
            <div className="activity-chart-controls">
              <select
                aria-label="Analysis activity date range"
                className="activity-range-select"
                value={activityRange}
                onChange={(event) => setActivityRange(event.target.value)}
              >
                <option value="7days">Last 7 days</option>
                <option value="1month">Last 1 month</option>
                <option value="1year">Last 1 year</option>
              </select>
              <div className="chart-legend">
                <span><i className="legend-records" /> Records</span>
                <span><i className="legend-dataset" /> Dataset labels</span>
              </div>
            </div>
          </div>
          <div className="credibility-chart activity-chart">
            <svg
              viewBox="0 0 560 205"
              preserveAspectRatio="none"
              role="img"
              aria-label={`Saved analysis records and dataset-label outputs for the ${activityRange === "1year" ? "last year" : activityRange === "1month" ? "last month" : "last seven days"}`}
            >
              {[0, 1, 2, 3, 4].map((step) => {
                const value = Math.ceil(activityScale * (4 - step) / 4);
                const y = 30 + step * 35.5;
                return (
                  <g key={step}>
                    <line x1="50" x2="550" y1={y} y2={y} className="chart-grid-line" />
                    <text x="4" y={y + 4} className="chart-axis">{value}</text>
                  </g>
                );
              })}
              {activity.map((bucket, index) => {
                const x = 50 + (index * 500) / Math.max(activity.length - 1, 1);
                return (
                  <g key={bucket.date.toISOString()}>
                    <line x1={x} x2={x} y1="30" y2="172" className="chart-vertical-line" />
                    <text x={x} y="198" textAnchor="middle" className="chart-axis">{bucket.label}</text>
                  </g>
                );
              })}
              <path d={makeAreaPath(activity.map((bucket) => bucket.total), activityScale)} className="chart-area-records" />
              <path d={makeLinePath(activity.map((bucket) => bucket.total), activityScale)} className="chart-line-records" />
              <path d={makeLinePath(activity.map((bucket) => bucket.dataset), activityScale)} className="chart-line-dataset" />
              {activity.map((bucket, index) => {
                const x = 50 + (index * 500) / Math.max(activity.length - 1, 1);
                const yRecords = 172 - (bucket.total / activityScale) * 142;
                const yDataset = 172 - (bucket.dataset / activityScale) * 142;
                return (
                  <g key={`points-${bucket.date.toISOString()}`}>
                    <circle cx={x} cy={yRecords} r="3.5" className="chart-dot-records">
                      <title>{`${bucket.label}: ${bucket.total} saved records`}</title>
                    </circle>
                    <circle cx={x} cy={yDataset} r="3.5" className="chart-dot-dataset">
                      <title>{`${bucket.label}: ${bucket.dataset} dataset-label outputs`}</title>
                    </circle>
                  </g>
                );
              })}
            </svg>
          </div>
        </article>

        <article className="overview-panel distribution-panel">
          <div className="overview-panel-header">
            <div>
              <h2>Record distribution</h2>
              <small>By output type</small>
            </div>
          </div>
          <div
            className="source-donut"
            style={{
              "--dataset-share": `${datasetShare}%`,
              "--evidence-end": `${datasetShare + evidenceShare}%`,
              "--unavailable-end": `${datasetShare + evidenceShare + unavailableShare}%`,
            }}
            role="img"
            aria-label={`${records.length} saved records: ${datasetCount} dataset-label outputs, ${evidenceCount} evidence verdicts, ${unavailableCount} unavailable or legacy records`}
          >
            <div>
              <strong>{formatNumber(records.length)}</strong>
              <small>records</small>
            </div>
          </div>
          <div className="distribution-legend">
            <div><i className="legend-dataset" /><span>Dataset labels</span><b>{formatNumber(datasetCount)}</b></div>
            <div><i className="legend-evidence" /><span>Evidence verdicts</span><b>{formatNumber(evidenceCount)}</b></div>
            <div><i className="legend-unavailable" /><span>Unavailable / legacy</span><b>{formatNumber(unavailableCount)}</b></div>
          </div>
        </article>
      </section>

      <section className="overview-bottom-grid">
        <article className="overview-panel recent-panel">
          <div className="overview-panel-header">
            <div>
              <h2>Recent analyses</h2>
              <small>Latest saved records</small>
            </div>
            <button
              className="see-all-btn"
              onClick={() => setActiveView?.("history")}
              type="button"
            >
              View all <span aria-hidden="true">→</span>
            </button>
          </div>
          {recent.length ? (
            <div className="recent-table-wrap">
              <table className="recent-table">
                <thead>
                  <tr><th>Content</th><th>Type</th><th>Result</th><th>Date</th></tr>
                </thead>
                <tbody>
                  {recent.map(({ record, date }, index) => {
                    const category = getRecordCategory(record);
                    return (
                      <tr key={record.id ?? `${getRecordTitle(record)}-${index}`}>
                        <td title={getRecordTitle(record)}>{getRecordTitle(record)}</td>
                        <td>{getRecordType(record)}</td>
                        <td>
                          <span className={`record-status status-${category}`}>
                            {getStatusLabel(record)}
                          </span>
                        </td>
                        <td>{formatDate(date)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overview-empty-state">
              <span aria-hidden="true">▤</span>
              <p>No analyses saved yet.</p>
              <button type="button" onClick={() => setActiveView?.("analyze")}>Start an analysis</button>
            </div>
          )}
        </article>

        <article className="overview-panel content-panel">
          <div className="overview-panel-header">
            <div>
              <h2>Content types</h2>
              <small>Saved record breakdown</small>
            </div>
          </div>
          {contentTypes.length ? (
            <div className="content-type-list">
              {contentTypes.map((entry, index) => (
                <div className="content-type-row" key={entry.label}>
                  <span>{entry.label}</span>
                  <div className="content-type-track">
                    <i className={`content-type-fill fill-${index}`} style={{ width: `${(entry.count / contentTypeMax) * 100}%` }} />
                  </div>
                  <b>{formatNumber(entry.count)}</b>
                </div>
              ))}
            </div>
          ) : (
            <div className="overview-empty-state compact">
              <span aria-hidden="true">◌</span>
              <p>Content breakdown will appear after your first saved analysis.</p>
            </div>
          )}
          <p className="overview-data-note">
            This dashboard reports saved activity; it does not assess source reliability.
          </p>
        </article>
      </section>
    </div>
  );
}

export default DashboardOverview;
