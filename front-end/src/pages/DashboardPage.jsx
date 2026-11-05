import { useContext, useState } from "react";
import Sidebar from "../components/Dashboard/Sidebar";
import Header from "../components/Dashboard/Header";
import DashboardHome from "../components/Dashboard/DashboardHome";
import DashboardOverview from "../components/Dashboard/DashboardOverview";
import History from "../components/Dashboard/History";
import Profile from "../components/Dashboard/Profile";
import Settings from "../components/Dashboard/Settings";
import TrendingNews from "../components/Dashboard/TrendingNews";
import Feedback from "../components/Dashboard/Feedback";

import { AppContext } from "../context/AppContext";
import {
  createUnavailableVerification,
  getPredictionPresentation,
} from "../utils/prediction";


/* =========================================================
   NOTIFICATION DATA
========================================================= */

/* =========================================================
   NOTIFICATION PANEL
========================================================= */

const NotificationPanel = ({
  setActiveView,
  notifications,
  setNotifications,
}) => {
  const [activeTab, setActiveTab] = useState("all");

  const unreadCount = notifications.filter(
    (item) => item.unread
  ).length;


  const markAllRead = () => {
    setNotifications((prev) =>
      prev.map((item) => ({
        ...item,
        unread: false,
      }))
    );
  };


  const markRead = (id) => {
    setNotifications((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, unread: false }
          : item
      )
    );
  };


  const handleNotificationAction = (item) => {
    markRead(item.id);

    if (item.type === "warning") {
      setActiveView("analyze");
    }
  };


  const filteredNotifications =
    activeTab === "all"
      ? notifications
      : activeTab === "system"
      ? notifications.filter(
          (item) => item.type === "system"
        )
      : activeTab === "mentions"
      ? notifications.filter(
          (item) => item.type === "mention"
        )
      : [];


  return (
    <div className="notification-page">

      <style>{`
        .notification-page {
          max-width: 1050px;
          margin: 0 auto;
          padding-bottom: 45px;
          animation: notificationPageIn .35s ease;
        }

        @keyframes notificationPageIn {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .notification-heading {
          margin-bottom: 24px;
        }

        .notification-eyebrow {
          display: block;
          margin-bottom: 6px;
          color: #6843df;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 2px;
        }

        .notification-heading h2 {
          margin: 0;
          color: #172033;
          font-size: 30px;
          font-weight: 750;
        }

        .notification-heading p {
          margin: 7px 0 0;
          color: #78859a;
          font-size: 13px;
        }

        .notification-container {
          background: linear-gradient(
            145deg,
            #f7fbff,
            #eef7fc
          );
          border: 1px solid #dce8ef;
          border-radius: 15px;
          padding: 10px;
        }

        .notification-tabs {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px;
          margin-bottom: 10px;
          border-radius: 10px;
        }

        .notification-tab {
          border: 0;
          background: transparent;
          color: #59677b;
          padding: 9px 18px;
          border-radius: 7px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 600;
          transition: .2s ease;
        }

        .notification-tab:hover {
          background: rgba(255,255,255,.7);
          color: #5433cb;
        }

        .notification-tab.active {
          background: #ffffff;
          color: #5131ca;
          box-shadow: 0 2px 8px rgba(50,70,100,.08);
        }

        .notification-topbar {
          display: flex;
          justify-content: flex-end;
          margin-bottom: 8px;
        }

        .mark-read-btn {
          border: 0;
          background: transparent;
          color: #5e42bd;
          cursor: pointer;
          font-size: 10px;
          font-weight: 700;
          padding: 5px 8px;
        }

        .mark-read-btn:hover {
          text-decoration: underline;
        }

        .notification-list {
          display: grid;
          gap: 9px;
        }

        .notification-item {
          display: flex;
          align-items: center;
          gap: 13px;
          padding: 13px;
          background: #ffffff;
          border: 1px solid #dce4ec;
          border-radius: 12px;
          box-shadow: 0 3px 12px rgba(30,50,80,.04);
          transition: .25s ease;
        }

        .notification-item:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 22px rgba(30,50,80,.09);
        }

        .notification-item.unread {
          border-left: 3px solid #6542df;
        }

        .notification-item.read {
          opacity: .76;
        }

        .notification-icon-box {
          width: 43px;
          height: 43px;
          flex: 0 0 43px;
          display: grid;
          place-items: center;
          border-radius: 12px;
          font-size: 20px;
        }

        .notification-icon-box.warning {
          background: #fff0df;
          color: #d97706;
        }

        .notification-icon-box.system {
          background: #e1f8f1;
          color: #13936b;
        }

        .notification-icon-box.mention {
          background: #ece8ff;
          color: #6743db;
        }

        .notification-content {
          min-width: 0;
          flex: 1;
        }

        .notification-content h3 {
          margin: 0 0 4px;
          color: #202a3d;
          font-size: 12px;
          font-weight: 750;
        }

        .notification-content p {
          margin: 0;
          color: #758196;
          font-size: 10px;
          line-height: 1.5;
        }

        .notification-time {
          display: block;
          margin-top: 5px;
          color: #a0a9b7;
          font-size: 9px;
        }

        .notification-action {
          flex-shrink: 0;
          border: 0;
          border-radius: 7px;
          padding: 9px 12px;
          background: #2478d7;
          color: white;
          cursor: pointer;
          font-size: 9px;
          font-weight: 700;
          box-shadow: 0 4px 10px rgba(36,120,215,.18);
          transition: .2s ease;
        }

        .notification-action:hover {
          transform: translateY(-1px);
          background: #1769c5;
        }

        .notification-empty {
          text-align: center;
          padding: 45px 20px;
          color: #7b879a;
          font-size: 12px;
        }

        .notification-empty-icon {
          width: 52px;
          height: 52px;
          display: grid;
          place-items: center;
          margin: 0 auto 12px;
          border-radius: 50%;
          background: #e9f8f1;
          color: #179b69;
          font-size: 23px;
        }

        @media (max-width: 700px) {
          .notification-tabs {
            overflow-x: auto;
          }

          .notification-tab {
            white-space: nowrap;
            padding: 8px 12px;
          }

          .notification-item {
            align-items: flex-start;
            flex-wrap: wrap;
          }

          .notification-action {
            margin-left: 56px;
          }
        }

        body.dark .notification-heading h2 {
          color: #f1f4fa;
        }

        body.dark .notification-heading p {
          color: #9aa8bb;
        }

        body.dark .notification-container {
          background: #101a2c;
          border-color: #2a3953;
        }

        body.dark .notification-item {
          background: #162238;
          border-color: #2c3c56;
        }

        body.dark .notification-content h3 {
          color: #edf2f8;
        }

        body.dark .notification-content p {
          color: #9ba9bc;
        }

        body.dark .notification-tab {
          color: #a8b5c7;
        }

        body.dark .notification-tab.active {
          background: #1c2a42;
          color: #bdaeff;
        }
      `}</style>


      <div className="notification-heading">
        <span className="notification-eyebrow">
          NOTIFICATIONS
        </span>

        <h2>Notifications</h2>

        <p>
          Manage and review important alerts.
        </p>
      </div>


      <div className="notification-container">

        <div className="notification-tabs">

          <button
            className={`notification-tab ${
              activeTab === "all"
                ? "active"
                : ""
            }`}
            onClick={() => setActiveTab("all")}
          >
            All ({notifications.length})
          </button>

          <button
            className={`notification-tab ${
              activeTab === "system"
                ? "active"
                : ""
            }`}
            onClick={() => setActiveTab("system")}
          >
            System
          </button>

          <button
            className={`notification-tab ${
              activeTab === "mentions"
                ? "active"
                : ""
            }`}
            onClick={() => setActiveTab("mentions")}
          >
            Mentions
          </button>

        </div>


        {unreadCount > 0 && (
          <div className="notification-topbar">
            <button
              className="mark-read-btn"
              onClick={markAllRead}
            >
              Mark all as read
            </button>
          </div>
        )}


        <div className="notification-list">

          {filteredNotifications.length === 0 ? (

            <div className="notification-empty">

              <div className="notification-empty-icon">
                ✓
              </div>

              <strong>
                You're all caught up!
              </strong>

              <div>
                No notifications in this category.
              </div>

            </div>

          ) : (

            filteredNotifications.map(
              (item) => (

                <div
                  key={item.id}
                  className={`notification-item ${
                    item.unread
                      ? "unread"
                      : "read"
                  }`}
                >

                  <div
                    className={`notification-icon-box ${item.type}`}
                  >
                    {item.type === "warning" && "⚠"}
                    {item.type === "system" && "⚙"}
                    {item.type === "mention" && "♧"}
                  </div>


                  <div className="notification-content">

                    <h3>
                      {item.title}
                    </h3>

                    <p>
                      {item.description}
                    </p>

                    <span className="notification-time">
                      {item.time}
                    </span>

                  </div>


                  <button
                    className="notification-action"
                    onClick={() =>
                      handleNotificationAction(item)
                    }
                  >
                    {item.action} ↗
                  </button>

                </div>

              )
            )

          )}

        </div>

      </div>

    </div>
  );
};


/* =========================================================
   VERIFICATION RESULT PANEL
========================================================= */

const VerificationResultPanel = ({
  result,
  setActiveView,
}) => {
  const presentation = getPredictionPresentation(result);
  const isDatasetClassification =
    presentation.kind === "dataset_classification";
  const isEvidenceEvaluated =
    presentation.kind === "evidence_verdict";
  const isUnavailable = !isDatasetClassification && !isEvidenceEvaluated;
  const datasetPrediction =
    result?.datasetPrediction ?? result?.dataset_prediction;
  const datasetIdentity =
    result?.datasetIdentity ?? result?.dataset_identity;
  const mockStatus = result?.isMock ?? result?.is_mock;
  const isFake =
    result?.verdict === "REFUTED" ||
    ["FAKE", "Fake News"].includes(datasetPrediction);
  const isPositive =
    result?.verdict === "SUPPORTED" ||
    ["REAL", "Real News"].includes(datasetPrediction);
  const resultTone = isUnavailable || isDatasetClassification
    ? ""
    : isFake
      ? "fake"
      : isPositive
        ? "real"
        : "";
  const confidence = presentation.score;
  const verdict = presentation.title;
  const explanation =
    result?.explanation ||
    "Evidence-based factual verification is not implemented. No verdict or confidence score was produced.";
  const reasoning = Array.isArray(result?.reasoning)
    ? result.reasoning
    : [];


  return (
    <div className="verification-demo-page">

      <style>{`
        .verification-demo-page {
          max-width: 980px;
          margin: 0 auto;
          padding-bottom: 50px;
          animation: resultPageIn .45s ease;
        }

        @keyframes resultPageIn {
          from {
            opacity: 0;
            transform: translateY(18px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .result-eyebrow {
          display: block;
          color: #6542df;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 2px;
          margin-bottom: 7px;
        }

        .result-page-title {
          margin: 0;
          color: #172033;
          font-size: 30px;
          font-weight: 750;
        }

        .result-page-subtitle {
          margin: 7px 0 25px;
          color: #78859a;
          font-size: 13px;
        }

        .result-verdict-card {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 35px;
          padding: 24px;
          background: white;
          border: 1px solid #dce3eb;
          border-radius: 15px;
          box-shadow: 0 8px 28px rgba(30,45,70,.055);
          animation: resultCardIn .5s ease;
        }

        @keyframes resultCardIn {
          from {
            opacity: 0;
            transform: scale(.98);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        .result-verdict-area {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .result-verdict-icon {
          width: 50px;
          height: 50px;
          display: grid;
          place-items: center;
          border-radius: 14px;
          font-size: 24px;
          font-weight: 900;
          animation: resultIconPop .55s .15s both ease;
        }

        @keyframes resultIconPop {
          0% {
            opacity: 0;
            transform: scale(.4) rotate(-15deg);
          }
          70% {
            transform: scale(1.12) rotate(3deg);
          }
          100% {
            opacity: 1;
            transform: scale(1) rotate(0);
          }
        }

        .result-verdict-icon.fake {
          background: #fff0f1;
          color: #db4048;
        }

        .result-verdict-icon.real {
          background: #e5f9ef;
          color: #159966;
        }

        .result-label {
          display: block;
          color: #8993a4;
          font-size: 9px;
          margin-bottom: 4px;
        }

        .result-verdict-text {
          margin: 0;
          color: #172033;
          font-size: 24px;
          font-weight: 750;
        }

        .result-status {
          display: inline-block;
          margin-top: 5px;
          padding: 5px 9px;
          border-radius: 20px;
          font-size: 9px;
          font-weight: 700;
        }

        .result-status.fake {
          background: #fff0f1;
          color: #d43d45;
        }

        .result-status.real {
          background: #e6f9ef;
          color: #179866;
        }

        .result-confidence-area {
          width: 280px;
        }

        .confidence-top {
          display: flex;
          justify-content: space-between;
          margin-bottom: 9px;
          color: #647186;
          font-size: 10px;
          font-weight: 700;
        }

        .confidence-top strong {
          color: #172033;
          font-size: 17px;
        }

        .confidence-track {
          width: 100%;
          height: 8px;
          overflow: hidden;
          background: #e8edf2;
          border-radius: 20px;
        }

        .confidence-progress {
          height: 100%;
          border-radius: 20px;
          animation: confidenceGrow 1.2s .35s both ease-out;
          transform-origin: left;
        }

        @keyframes confidenceGrow {
          from {
            width: 0 !important;
          }
        }

        .confidence-progress.fake {
          background: linear-gradient(
            90deg,
            #ee5b61,
            #c9363e
          );
        }

        .confidence-progress.real {
          background: linear-gradient(
            90deg,
            #30b57c,
            #138c5a
          );
        }

        .confidence-note {
          display: block;
          margin-top: 7px;
          color: #9aa3b0;
          font-size: 9px;
        }

        .result-info-card {
          display: flex;
          gap: 14px;
          margin-top: 13px;
          padding: 20px 22px;
          background: #fff;
          border: 1px solid #dce3eb;
          border-radius: 14px;
          box-shadow: 0 5px 18px rgba(30,45,70,.035);
          animation: resultInfoIn .45s ease both;
        }

        .result-info-card:nth-child(2) {
          animation-delay: .1s;
        }

        .result-info-card:nth-child(3) {
          animation-delay: .2s;
        }

        .result-info-card:nth-child(4) {
          animation-delay: .3s;
        }

        @keyframes resultInfoIn {
          from {
            opacity: 0;
            transform: translateY(14px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .result-info-icon {
          width: 36px;
          height: 36px;
          flex: 0 0 36px;
          display: grid;
          place-items: center;
          border-radius: 10px;
          font-size: 16px;
          font-weight: 800;
        }

        .result-info-icon.purple {
          background: #eeeaff;
          color: #6743df;
        }

        .result-info-icon.blue {
          background: #e7f1ff;
          color: #2478d7;
        }

        .result-info-icon.green {
          background: #e5f8ef;
          color: #179966;
        }

        .result-info-card h3 {
          margin: 0 0 8px;
          color: #202a3d;
          font-size: 14px;
        }

        .result-info-card p {
          margin: 0;
          color: #718096;
          font-size: 11px;
          line-height: 1.65;
        }

        .reasoning-list {
          display: grid;
          gap: 8px;
        }

        .reasoning-row {
          display: flex;
          gap: 9px;
          align-items: flex-start;
        }

        .reasoning-number {
          width: 20px;
          height: 20px;
          flex: 0 0 20px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          background: #f0edff;
          color: #6340d5;
          font-size: 9px;
          font-weight: 800;
        }

        .result-details {
          margin-top: 13px;
          padding: 21px 22px;
          background: #fff;
          border: 1px solid #dce3eb;
          border-radius: 14px;
          animation: resultInfoIn .45s .35s both ease;
        }

        .result-details h3 {
          margin: 0 0 15px;
          color: #202a3d;
          font-size: 14px;
        }

        .detail-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          min-height: 39px;
          border-top: 1px solid #edf0f4;
          color: #788499;
          font-size: 10px;
        }

        .detail-row strong {
          color: #263148;
        }

        .completed {
          color: #179966 !important;
        }

        .result-actions {
          display: flex;
          gap: 8px;
          margin-top: 15px;
        }

        .result-action {
          border-radius: 8px;
          padding: 10px 15px;
          cursor: pointer;
          font-size: 10px;
          font-weight: 700;
          transition: .2s ease;
        }

        .result-action.primary {
          border: 0;
          background: #172033;
          color: #fff;
        }

        .result-action.secondary {
          border: 1px solid #d7dee7;
          background: #fff;
          color: #354158;
        }

        .result-action:hover {
          transform: translateY(-2px);
        }

        .result-feedback {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 15px;
          margin-top: 18px;
          padding-top: 17px;
          border-top: 1px solid #dce3eb;
        }

        .result-feedback h4 {
          margin: 0;
          color: #253047;
          font-size: 12px;
        }

        .result-feedback p {
          margin: 4px 0 0;
          color: #8c96a5;
          font-size: 9px;
        }

        .feedback-btns {
          display: flex;
          gap: 7px;
        }

        .feedback-btn {
          border: 1px solid #d9e0e8;
          border-radius: 7px;
          background: white;
          color: #647084;
          padding: 8px 11px;
          cursor: pointer;
          font-size: 9px;
        }

        .feedback-btn:hover {
          border-color: #8065dd;
          color: #5d3bcf;
          background: #f4f1ff;
        }

        body.dark .result-page-title,
        body.dark .result-verdict-text,
        body.dark .result-info-card h3,
        body.dark .result-details h3,
        body.dark .result-feedback h4 {
          color: #f0f4fa;
        }

        body.dark .result-page-subtitle,
        body.dark .result-info-card p,
        body.dark .confidence-note,
        body.dark .result-feedback p {
          color: #9ba9bc;
        }

        body.dark .result-verdict-card,
        body.dark .result-info-card,
        body.dark .result-details {
          background: #111d30;
          border-color: #2b3b56;
          box-shadow: none;
        }

        body.dark .detail-row {
          border-color: #293951;
        }

        body.dark .detail-row strong {
          color: #e3e9f2;
        }

        body.dark .result-action.secondary,
        body.dark .feedback-btn {
          background: #18253b;
          border-color: #30415d;
          color: #c1ccda;
        }

        @media (max-width: 700px) {
          .result-verdict-card {
            flex-direction: column;
            align-items: flex-start;
          }

          .result-confidence-area {
            width: 100%;
          }

          .result-feedback {
            align-items: flex-start;
            flex-direction: column;
          }
        }
      `}</style>


      <span className="result-eyebrow">
        VERIFACT AI
      </span>

      <h1 className="result-page-title">
        {presentation.title}
      </h1>

      <p className="result-page-subtitle">
        {isDatasetClassification
          ? "This is a dataset-label prediction, not an evidence-based factual verdict."
          : isEvidenceEvaluated
            ? "Review the verdict and its evaluated evidence."
            : "No factual verdict is available because evidence-based verification is not implemented."}
      </p>


      {/* VERDICT */}

      <div className="result-verdict-card">

        <div className="result-verdict-area">

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

            <span className="result-label">
              Assessment
            </span>

            <h2 className="result-verdict-text">
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


        {confidence !== null && Number.isFinite(confidence) ? (
          <div className="result-confidence-area">

          <div className="confidence-top">
            <span>{presentation.scoreLabel}</span>
            <strong>{confidence}%</strong>
          </div>

          <div className="confidence-track">

            <div
              className={`confidence-progress ${resultTone}`}
              style={{
                width: `${confidence}%`,
              }}
            />

          </div>

          <span className="confidence-note">
            {presentation.scoreSemantics === "uncalibrated_dataset_score"
              ? "Uncalibrated dataset score; not factual confidence"
              : "Calibrated class probability; not factual confidence"}
          </span>

          </div>
        ) : (
          <div className="result-confidence-area">
            <div className="confidence-top">
              <span>Confidence</span>
              <strong>Not available</strong>
            </div>
            <span className="confidence-note">
              No factual confidence score is produced.
            </span>
          </div>
        )}

      </div>


      {/* EXPLANATION */}

      <div className="result-info-card">

        <div className="result-info-icon purple">
          ✦
        </div>

        <div>

          <h3>
            {isDatasetClassification
              ? "Dataset-Label Scope"
              : "Verification Status"}
          </h3>

          <p>
            {isDatasetClassification
              ? "This output predicts a Fakeddit dataset label only. It does not assess whether any claim is true or false."
              : explanation}
          </p>

        </div>

      </div>


      {/* REASONING */}

      <div className="result-info-card">

        <div className="result-info-icon blue">
          ≡
        </div>

        <div>

          <h3>
            Reasoning Summary
          </h3>

          <div className="reasoning-list">

            {reasoning.length > 0 ? reasoning.map(
              (item, index) => (

                <div
                  className="reasoning-row"
                  key={index}
                >

                  <span className="reasoning-number">
                    {index + 1}
                  </span>

                  <p>
                    {item}
                  </p>

                </div>

              )
            ) : (
              <p>
                {isDatasetClassification
                  ? "This output is limited to the dataset label and does not evaluate factual support."
                  : "No evidence was evaluated, so no evidence-based reasoning is available."}
              </p>
            )}

          </div>

        </div>

      </div>


      {/* DETAILS */}

      <div className="result-details">

        <h3>
          Verification Details
        </h3>

        <div className="detail-row">
          <span>Input Type</span>

          <strong>
            {result?.contentType ||
              "Text"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Processing Time</span>

          <strong>
            {result?.processingTime ||
              "Not run"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Report ID</span>

          <strong>
            {result?.reportId ||
              "Not generated"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Request status</span>

          <strong>
            {result?.status || "unavailable"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Evidence status</span>

          <strong>
            {result?.evidenceStatus || "not available"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Prediction type</span>

          <strong>
            {result?.predictionType ||
              result?.prediction_type ||
              "legacy_unverified"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Mock response</span>

          <strong>
            {mockStatus == null ? "Unknown" : mockStatus ? "Yes" : "No"}
          </strong>
        </div>

        <div className="detail-row">
          <span>Model / dataset</span>

          <strong>
            {result?.modelIdentity ||
              datasetIdentity ||
              "Not applicable"}
          </strong>
        </div>

      </div>


      {/* ACTIONS */}

      <div className="result-actions">

        <button
          className="result-action primary"
          onClick={() =>
            setActiveView("analyze")
          }
        >
          ← Verify Again
        </button>

        <button
          className="result-action secondary"
          disabled={isUnavailable}
          onClick={() => {
            window.print();
          }}
        >
          {isUnavailable
            ? "Report unavailable"
            : "↓ Download Report"}
        </button>

      </div>


      {/* FEEDBACK */}

      <div className="result-feedback">

        <div>

          <h4>
            Was this result helpful?
          </h4>

          <p>
            Your feedback helps improve the verification experience.
          </p>

        </div>

        <div className="feedback-btns">

          <button className="feedback-btn">
            👍 Helpful
          </button>

          <button className="feedback-btn">
            👎 Not helpful
          </button>

        </div>

      </div>

    </div>
  );
};


/* =========================================================
   MAIN DASHBOARD PAGE
========================================================= */

const DashboardPage = ({
  backHome,
}) => {

  const {
    history,
    setHistory,
    result,
    setResult,
  } = useContext(AppContext);


  const [activeView, setActiveView] =
    useState("overview");


  const [notifications, setNotifications] =
    useState([]);


  /* =======================================================
     AI ANALYSIS
  ======================================================= */

  const handleAnalyze = ({
    type,
    content,
    file,
  }) => {
    const newResult = createUnavailableVerification({
      type,
      content,
      fileName: file?.name || "",
    });

    setResult(newResult);
    setHistory((prev) => [newResult, ...prev]);
    setActiveView("result");
  };


  /* =======================================================
     PAGE ROUTER
  ======================================================= */

  const renderView = () => {

    switch (activeView) {


      /* DASHBOARD */

      case "overview":

        return (
          <DashboardOverview
            setActiveView={
              setActiveView
            }
          />
        );


      /* ANALYZE */

      case "analyze":

        return (
          <DashboardHome
            onAnalyze={
              handleAnalyze
            }
          />
        );


      /* RESULT */

      case "result":

        return (
          <VerificationResultPanel
            result={result}
            setActiveView={
              setActiveView
            }
          />
        );


      /* NOTIFICATIONS */

      case "notifications":

        return (
          <NotificationPanel
            setActiveView={
              setActiveView
            }
            notifications={
              notifications
            }
            setNotifications={
              setNotifications
            }
          />
        );



      case "history":

        return <History />;

      case "profile":

  return <Profile />;


case "feedback":

  return <Feedback />;


case "settings":

  return <Settings />;

      case "trending":

        return (
          <TrendingNews
            setActiveView={setActiveView}
          />
        );


      /* SAVED */

      case "saved":

        return (
          <div className="panel dashboard-placeholder">

            <div className="section-heading">

              <div>

                <span className="eyebrow">
                  YOUR LIBRARY
                </span>

                <h2>
                  Saved Articles
                </h2>

              </div>

            </div>

            <p>
              Articles that you save will
              appear here.
            </p>

          </div>
        );


      /* STATISTICS */

      case "statistics": {

        const total =
          history?.length || 0;


        const datasetLabels =
          history?.filter(
            (item) =>
              item.predictionType === "dataset_classification"
          ).length || 0;

        const evidenceVerdicts =
          history?.filter(
            (item) =>
              item.predictionType === "evidence_verification" &&
              item.evidenceStatus === "evaluated" &&
              Boolean(item.verdict)
          ).length || 0;


        return (
          <div className="panel dashboard-placeholder">

            <div className="section-heading">

              <div>

                <span className="eyebrow">
                  YOUR ACTIVITY
                </span>

                <h2>
                  Statistics
                </h2>

              </div>

            </div>


            <div className="mini-stats">

              <div>
                <strong>
                  {total}
                </strong>

                <span>
                  Saved Records
                </span>
              </div>


              <div>
                <strong>
                  {datasetLabels}
                </strong>

                <span>
                  Dataset-Label Predictions
                </span>
              </div>


              <div>
                <strong>
                  {evidenceVerdicts}
                </strong>

                <span>
                  Evaluated Evidence Verdicts
                </span>
              </div>

            </div>

          </div>
        );
      }


      default:

        return (
          <DashboardOverview
            setActiveView={
              setActiveView
            }
          />
        );
    }
  };


  return (
    <main className="dashboard-page">

      <Sidebar
        activeView={
          activeView
        }
        setActiveView={
          setActiveView
        }
        backHome={
          backHome
        }
      />


      <section className="workspace">

        <Header
          activeView={
            activeView
          }
          setActiveView={
            setActiveView
          }
          backHome={
            backHome
          }
        />


        <div className="workspace-content">

          {renderView()}

        </div>

      </section>

    </main>
  );
};


export default DashboardPage;