import { useContext, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import "./DashboardOverview.css";

const formatNumber = (value) =>
  Number(value || 0).toLocaleString("en-IN");

const topicRows = [
  {
    id: "P001",
    category: "Political Coercion",
    growth: "+12%",
    score: "85%",
    date: "2025-04-11",
  },
  {
    id: "P002",
    category: "Health Claims",
    growth: "-5%",
    score: "78%",
    date: "2025-04-12",
  },
  {
    id: "P003",
    category: "Groceries",
    growth: "+8%",
    score: "90%",
    date: "2025-04-13",
  },
  {
    id: "P004",
    category: "Political Coercion",
    growth: "+1%",
    score: "83%",
    date: "2025-04-14",
  },
];

const chartPoints = [
  { label: "15/2", real: 3300, fake: 650 },
  { label: "18/2", real: 3500, fake: 900 },
  { label: "21/2", real: 4600, fake: 1450 },
  { label: "24/2", real: 4500, fake: 1600 },
  { label: "27/2", real: 2800, fake: 2100 },
  { label: "12/3", real: 2800, fake: 3500 },
  { label: "16/3", real: 2000, fake: 3500 },
];

const getPoint = (point, index, key) => {
  const x = 30 + (index * 520) / 6;
  const y = 167 - (point[key] / 6000) * 155;

  return { x, y };
};

const createPath = (key) => {
  return chartPoints
    .map((point, index) => {
      const { x, y } = getPoint(point, index, key);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
};

const createAreaPath = (key) => {
  const first = getPoint(chartPoints[0], 0, key);

  const points = chartPoints
    .map((point, index) => {
      const { x, y } = getPoint(point, index, key);
      return `L ${x} ${y}`;
    })
    .join(" ");

  const last = getPoint(
    chartPoints[chartPoints.length - 1],
    chartPoints.length - 1,
    key
  );

  return `
    M ${first.x} 167
    ${points}
    L ${last.x} 167
    Z
  `;
};

export default function DashboardOverview({
  setActiveView,
}) {
  const { history } = useContext(AppContext);

  const [period, setPeriod] =
    useState("This Week");

  const [selectedPoint, setSelectedPoint] =
    useState(3);

  const totalAnalyzed =
    history?.length || 0;

  const fakeCount =
    history?.filter(
      (item) => item.label === "Fake News"
    ).length || 0;

  const metrics = useMemo(
    () => ({
      scanned: Math.max(
        45670,
        totalAnalyzed + 45670
      ),

      fake: Math.max(
        2341,
        fakeCount + 2341
      ),

      credibility: 78.4,

      topics: 15,
    }),
    [totalAnalyzed, fakeCount]
  );

  const selectedData =
    chartPoints[selectedPoint];

  return (
    <div className="misinfo-overview">

      {/* =====================================================
          DASHBOARD TOP
      ===================================================== */}

      <div className="misinfo-overview-top">

        <div>

          <span className="overview-kicker">
            INTELLIGENCE OVERVIEW
          </span>

          <h1>
            News Credibility Dashboard
          </h1>

          <p>
            Monitor credibility trends,
            misinformation signals and
            emerging topics.
          </p>

        </div>

        {/* IMPORTANT:
            Analyze Now still opens the
            existing Analyze page.
        */}

        <button
          className="overview-analyze-btn"
          onClick={() =>
            setActiveView?.("analyze")
          }
        >
          Analyze Now

          <span>↗</span>
        </button>

      </div>


      {/* =====================================================
          TOP STATISTICS
      ===================================================== */}

      <section className="overview-stat-grid">

        {/* TOTAL SCANNED */}

        <article className="overview-stat-card">

          <div className="overview-stat-icon trend">
            ↗
          </div>

          <div>

            <span>
              Total Scanned Articles
            </span>

            <strong>
              {formatNumber(
                metrics.scanned
              )}
            </strong>

            <small>
              2 More Then in Yesterday

              <b>
                ↗ 12.5%
              </b>
            </small>

          </div>

        </article>


        {/* FAKE NEWS */}

        <article className="overview-stat-card">

          <div className="overview-stat-icon down">
            ↘
          </div>

          <div>

            <span>
              Likely Fake News
            </span>

            <strong>
              {formatNumber(
                metrics.fake
              )}
            </strong>

            <small>
              1 More Then in Yesterday

              <b>
                ↘ 2,341
              </b>
            </small>

          </div>

        </article>


        {/* CREDIBILITY */}

        <article
          className="
            overview-stat-card
            credibility-card
          "
        >

          <div>

            <span>
              Source Credibility Index
            </span>

            <strong>
              {metrics.credibility}
            </strong>

            <small>
              Color Ceeoibility
            </small>

          </div>


          <div
            className="mini-gauge"
            style={{
              "--gauge": "78.4%",
            }}
          >

            <i />

            <b>
              ↗
            </b>

          </div>

        </article>


        {/* TOPICS */}

        <article className="overview-stat-card">

          <div className="overview-stat-icon topic">
            15
          </div>

          <div>

            <span>
              Top Misleading Topics
            </span>

            <strong>
              {metrics.topics} topics
            </strong>

            <small>
              1 More Then in Yesterday

              <b>
                ↗ 15.5%
              </b>
            </small>

          </div>

        </article>

      </section>


      {/* =====================================================
          MAIN ROW
      ===================================================== */}

      <section className="overview-main-grid">


        {/* =================================================
            CREDIBILITY TREND
        ================================================= */}

        <article
          className="
            overview-panel
            trend-panel
          "
        >

          <div className="overview-panel-header">

            <div>

              <h2>
                News Credibility Trends
              </h2>

            </div>


            <div className="overview-panel-actions">

              <button>
                ▣ &nbsp; Mar 13, 2025
              </button>

              <button className="icon-button">
                ▥
              </button>

            </div>

          </div>


          {/* LEGEND */}

          <div className="chart-legend">

            <span>

              <i className="legend-real" />

              Credible Articles

            </span>

            <span>

              <i className="legend-fake" />

              Suspected Fake News

            </span>

          </div>


          {/* CHART */}

          <div className="credibility-chart">

            <svg
              viewBox="0 0 560 185"
              preserveAspectRatio="none"
              aria-label="
                News credibility trend chart
              "
            >

              {/* HORIZONTAL GRID */}

              {[0, 1800, 3000, 4500, 6000].map(
                (value) => {

                  const y =
                    167 -
                    (value / 6000) *
                      155;

                  return (
                    <g key={value}>

                      <line
                        x1="30"
                        x2="550"
                        y1={y}
                        y2={y}
                        className="
                          chart-grid-line
                        "
                      />

                      <text
                        x="0"
                        y={y + 4}
                        className="
                          chart-axis
                        "
                      >
                        {value}
                      </text>

                    </g>
                  );
                }
              )}


              {/* VERTICAL GRID */}

              {chartPoints.map(
                (point, index) => {

                  const x =
                    30 +
                    (index * 520) /
                      6;

                  return (
                    <line
                      key={`vertical-${point.label}`}
                      x1={x}
                      x2={x}
                      y1="12"
                      y2="167"
                      className="
                        chart-vertical-line
                      "
                    />
                  );
                }
              )}


              {/* AREA */}

              <path
                d={createAreaPath("real")}
                className="
                  chart-area-real
                "
              />

              <path
                d={createAreaPath("fake")}
                className="
                  chart-area-fake
                "
              />


              {/* LINES */}

              <path
                d={createPath("real")}
                className="
                  chart-line-real
                "
              />

              <path
                d={createPath("fake")}
                className="
                  chart-line-fake
                "
              />


              {/* POINTS */}

              {chartPoints.map(
                (point, index) => {

                  const real =
                    getPoint(
                      point,
                      index,
                      "real"
                    );

                  const fake =
                    getPoint(
                      point,
                      index,
                      "fake"
                    );

                  return (
                    <g
                      key={point.label}
                      onClick={() =>
                        setSelectedPoint(
                          index
                        )
                      }
                      style={{
                        cursor:
                          "pointer",
                      }}
                    >

                      <circle
                        cx={real.x}
                        cy={real.y}
                        r={
                          selectedPoint ===
                          index
                            ? 5
                            : 3.2
                        }
                        className="
                          chart-dot-real
                        "
                      />

                      <circle
                        cx={fake.x}
                        cy={fake.y}
                        r={
                          selectedPoint ===
                          index
                            ? 5
                            : 3.2
                        }
                        className="
                          chart-dot-fake
                        "
                      />

                      <text
                        x={real.x}
                        y="181"
                        textAnchor="middle"
                        className="
                          chart-axis
                        "
                      >
                        {point.label}
                      </text>

                    </g>
                  );
                }
              )}

            </svg>


            {/* TOOLTIP */}

            <div className="chart-tooltip">

              <small>
                {selectedData.label}/2025
              </small>

              <strong>
                Credible Articles
              </strong>

              <b>
                {selectedData.real.toLocaleString()}
              </b>

            </div>

          </div>

        </article>


        {/* =================================================
            SUSPECTED SOURCES
        ================================================= */}

        <article
          className="
            overview-panel
            source-panel
          "
        >

          <div className="overview-panel-header">

            <h2>
              Suspected Fake Sources
            </h2>

            <button
              className="see-all-btn"
              onClick={() =>
                setActiveView?.(
                  "history"
                )
              }
            >
              See All
            </button>

          </div>


          {/* DONUT */}

          <div className="source-donut-wrap">

            <div className="source-donut">

              <div>

                <small>
                  Total Revenue
                </small>

                <strong>
                  $35,450
                </strong>

              </div>

            </div>

          </div>


          {/* SOURCE LIST */}

          <div className="source-list">

            <div>

              <span>

                <i className="source-web" />

                Websites

              </span>

              <b>
                $1 ad revenue
              </b>

            </div>


            <div>

              <span>

                <i className="source-social" />

                Social Media

              </span>

              <b>
                $1 ad revenue
              </b>

            </div>


            <div>

              <span>

                <i className="source-forum" />

                Forums

              </span>

              <b>
                $10 content
              </b>

            </div>

          </div>

        </article>

      </section>


      {/* =====================================================
          BOTTOM ROW
      ===================================================== */}

      <section className="overview-bottom-grid">


        {/* =================================================
            AI INSIGHTS
        ================================================= */}

        <article
          className="
            overview-panel
            insights-panel
          "
        >

          <div className="overview-panel-header">

            <h2>
              AI-Generated Insights
            </h2>

            <button className="more-btn">
              •••
            </button>

          </div>


          <p className="insight-copy">

            Optimized detection with new
            stylistic features analysis.
            AI is now better at identifying
            satire vs. disinformation.

          </p>


          <div className="insight-progress">

            <div>

              <span>
                Progress
              </span>

              <i>
                <b />
              </i>

            </div>


            <div className="small-bars">

              <i />
              <i />
              <i />

            </div>

          </div>


          <button className="upgrade-alert-btn">

            Upgrade for Real-time Alerting

          </button>

        </article>


        {/* =================================================
            EMERGING THEMES
        ================================================= */}

        <article
          className="
            overview-panel
            themes-panel
          "
        >

          <div className="overview-panel-header">

            <h2>
              Emerging Misinformation Themes
            </h2>

            <select
              value={period}
              onChange={(event) =>
                setPeriod(
                  event.target.value
                )
              }
            >

              <option>
                This Week
              </option>

              <option>
                This Month
              </option>

              <option>
                This Year
              </option>

            </select>

          </div>


          <div className="theme-table-wrap">

            <table className="theme-table">

              <thead>

                <tr>

                  <th>
                    <span className="table-check">
                      ✓
                    </span>
                  </th>

                  <th>
                    Theme_ID
                  </th>

                  <th>
                    Theme Category
                  </th>

                  <th>
                    Source Growth
                  </th>

                  <th>
                    Credibility Score
                  </th>

                  <th>
                    Verification Date
                  </th>

                </tr>

              </thead>


              <tbody>

                {topicRows.map(
                  (row) => (

                    <tr key={row.id}>

                      <td>

                        <span className="table-check">
                          ✓
                        </span>

                      </td>

                      <td>
                        {row.id}
                      </td>

                      <td>
                        {row.category}
                      </td>

                      <td
                        className={
                          row.growth.startsWith(
                            "+"
                          )
                            ? "growth-up"
                            : "growth-down"
                        }
                      >
                        {row.growth}
                      </td>

                      <td>
                        {row.score}
                      </td>

                      <td>
                        {row.date}
                      </td>

                    </tr>

                  )
                )}

              </tbody>

            </table>

          </div>

        </article>

      </section>

    </div>
  );
}