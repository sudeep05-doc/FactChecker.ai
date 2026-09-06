import React, { useRef, useState } from "react";

const verificationTypes = [
  {
    id: "text",
    label: "Text",
    icon: "T",
  },
  {
    id: "image",
    label: "Image",
    icon: "IMG",
  },
  {
    id: "pdf",
    label: "PDF",
    icon: "PDF",
  },
  {
    id: "video",
    label: "Video",
    icon: "▶",
  },
  {
    id: "website",
    label: "Website URL",
    icon: "↗",
  },
  {
    id: "youtube",
    label: "YouTube Link",
    icon: "▶",
  },
];

const supportedFormats = [
  {
    type: "TXT",
    label: "Text",
    className: "format-text",
  },
  {
    type: "DOCX",
    label: "Document",
    className: "format-docx",
  },
  {
    type: "JPG",
    label: "Image",
    className: "format-jpg",
  },
  {
    type: "PNG",
    label: "Image",
    className: "format-png",
  },
  {
    type: "PDF",
    label: "Document",
    className: "format-pdf",
  },
  {
    type: "MP4",
    label: "Video",
    className: "format-mp4",
  },
  {
    type: "URL",
    label: "Website",
    className: "format-url",
  },
];

const recentVerifications = [
  {
    id: 1,
    title: "Document Analysis (TXT)",
    time: "Just now",
    result: "Likely Human",
    type: "human",
  },
  {
    id: 2,
    title: "Image Check (PNG)",
    time: "2 minutes ago",
    result: "Potential AI",
    type: "ai",
  },
  {
    id: 3,
    title: "Article URL Verification",
    time: "8 minutes ago",
    result: "Confirmed",
    type: "confirmed",
  },
];

export default function DashboardHome({
  onAnalyze,
  onViewHistory,
}) {
  const [activeType, setActiveType] =
    useState("text");

  const [text, setText] =
    useState("");

  const [url, setUrl] =
    useState("");

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [isDragging, setIsDragging] =
    useState(false);

  const [isAnalyzing, setIsAnalyzing] =
    useState(false);

  const fileInputRef =
    useRef(null);

  const handleTypeChange = (type) => {
    setActiveType(type);

    setText("");
    setUrl("");
    setSelectedFile(null);
  };

  const handleFile = (file) => {
    if (!file) return;

    const maxSize =
      25 * 1024 * 1024;

    if (file.size > maxSize) {
      alert(
        "File size must be less than 25 MB."
      );
      return;
    }

    setSelectedFile(file);
  };

  const handleFileChange = (event) => {
    const file =
      event.target.files?.[0];

    handleFile(file);
  };

  const handleDrop = (event) => {
    event.preventDefault();

    setIsDragging(false);

    const file =
      event.dataTransfer.files?.[0];

    handleFile(file);
  };

  const handleAnalyze = async () => {
    let content = "";

    if (activeType === "text") {
      content = text.trim();

      if (content.length < 10) {
        alert(
          "Please enter at least 10 characters."
        );
        return;
      }
    }

    if (
      activeType === "website" ||
      activeType === "youtube"
    ) {
      content = url.trim();

      if (!content) {
        alert(
          "Please enter a valid URL."
        );
        return;
      }
    }

    if (
      activeType === "image" ||
      activeType === "pdf" ||
      activeType === "video"
    ) {
      if (!selectedFile) {
        alert(
          "Please select a file first."
        );
        return;
      }

      content = selectedFile.name;
    }

    setIsAnalyzing(true);

    try {
      if (onAnalyze) {
        await onAnalyze({
          type: activeType,
          content,
          file: selectedFile,
        });
      } else {
        await new Promise(
          (resolve) =>
            setTimeout(resolve, 1000)
        );
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getPlaceholder = () => {
    switch (activeType) {
      case "text":
        return "Paste or type content here for analysis...";

      case "website":
        return "https://example.com/article";

      case "youtube":
        return "https://youtube.com/watch?v=...";

      default:
        return "";
    }
  };

  const isFileType =
    activeType === "image" ||
    activeType === "pdf" ||
    activeType === "video";

  return (
    <div className="modern-dashboard-home">

      {/* ==========================================
          MAIN ANALYZER
      =========================================== */}

      <section className="verification-card">

        <div className="verification-tabs">

          {verificationTypes.map((item) => (
            <button
              key={item.id}
              type="button"
              className={
                activeType === item.id
                  ? "verification-tab active"
                  : "verification-tab"
              }
              onClick={() =>
                handleTypeChange(item.id)
              }
            >
              <span className="tab-icon">
                {item.icon}
              </span>

              <span>
                {item.label}
              </span>
            </button>
          ))}

        </div>

        {/* ========================================
            TEXT
        ========================================= */}

        {activeType === "text" && (
          <div className="verification-input-area">

            <textarea
              value={text}
              onChange={(event) =>
                setText(event.target.value)
              }
              placeholder={getPlaceholder()}
              maxLength={10000}
            />

            <div className="input-footer">
              <span>
                {text.length} / 10,000
              </span>
            </div>

          </div>
        )}

        {/* ========================================
            WEBSITE / YOUTUBE
        ========================================= */}

        {(activeType === "website" ||
          activeType === "youtube") && (
          <div className="verification-url-area">

            <div className="url-input-icon">
              {activeType === "youtube"
                ? "▶"
                : "↗"}
            </div>

            <input
              type="url"
              value={url}
              onChange={(event) =>
                setUrl(event.target.value)
              }
              placeholder={getPlaceholder()}
            />

          </div>
        )}

        {/* ========================================
            IMAGE / PDF / VIDEO
        ========================================= */}

        {isFileType && (
          <div
            className={
              isDragging
                ? "verification-dropzone dragging"
                : "verification-dropzone"
            }
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() =>
              setIsDragging(false)
            }
            onDrop={handleDrop}
            onClick={() =>
              fileInputRef.current?.click()
            }
          >

            <input
              ref={fileInputRef}
              type="file"
              hidden
              accept={
                activeType === "image"
                  ? "image/*"
                  : activeType === "pdf"
                  ? ".pdf"
                  : "video/*"
              }
              onChange={handleFileChange}
            />

            <div className="upload-icon">
              ↑
            </div>

            {selectedFile ? (
              <>
                <strong>
                  {selectedFile.name}
                </strong>

                <span>
                  {(
                    selectedFile.size /
                    (1024 * 1024)
                  ).toFixed(2)}{" "}
                  MB
                </span>

                <small>
                  Click to replace file
                </small>
              </>
            ) : (
              <>
                <strong>
                  Drag and Drop or Click to Upload
                </strong>

                <span>
                  Upload your{" "}
                  {activeType} for AI verification
                </span>

                <small>
                  Maximum file size: 25 MB
                </small>
              </>
            )}

          </div>
        )}

        {/* ========================================
            ANALYZE BUTTON
        ========================================= */}

        <button
          type="button"
          className="verify-ai-button"
          onClick={handleAnalyze}
          disabled={isAnalyzing}
        >
          {isAnalyzing
            ? "Analyzing..."
            : "Verify with AI"}
        </button>

      </section>

      {/* ==========================================
          LOWER DASHBOARD
      =========================================== */}

      <div className="dashboard-information-grid">

        {/* ========================================
            SUPPORTED FORMATS
        ========================================= */}

        <section className="dashboard-info-card">

          <div className="info-card-heading">
            <h2>
              Supported Formats
            </h2>

            <p>
              Upload different types of content
            </p>
          </div>

          <div className="formats-grid">

            {supportedFormats.map(
              (format) => (
                <div
                  key={format.type}
                  className="format-item"
                >
                  <div
                    className={`format-icon ${format.className}`}
                  >
                    {format.type}
                  </div>

                  <span>
                    {format.label}
                  </span>
                </div>
              )
            )}

          </div>

        </section>

        {/* ========================================
            DRAG & DROP
        ========================================= */}

        <section className="dashboard-info-card">

          <div className="info-card-heading">
            <h2>
              Drag and Drop upload
            </h2>

            <p>
              Quickly upload content for verification
            </p>
          </div>

          <div
            className={
              isDragging
                ? "small-upload-box dragging"
                : "small-upload-box"
            }
            onClick={() =>
              fileInputRef.current?.click()
            }
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() =>
              setIsDragging(false)
            }
            onDrop={handleDrop}
          >
            <div className="small-upload-icon">
              ↑
            </div>

            <strong>
              Drag and Drop or Click to Upload
            </strong>

            <span>
              Supports images, PDF and video
              files
            </span>
          </div>

        </section>

        {/* ========================================
            RECENT VERIFICATIONS
        ========================================= */}

        <section className="dashboard-info-card">

          <div className="info-card-heading recent-heading">
            <div>
              <h2>
                Recent Verifications
              </h2>

              <p>
                Your latest AI checks
              </p>
            </div>

            <button
              type="button"
              onClick={onViewHistory}
            >
              View all
            </button>
          </div>

          <div className="recent-verification-list">

            {recentVerifications.map(
              (item) => (
                <div
                  key={item.id}
                  className="recent-verification"
                >

                  <div>
                    <strong>
                      {item.title}
                    </strong>

                    <span>
                      {item.time}
                    </span>
                  </div>

                  <span
                    className={`verification-result ${item.type}`}
                  >
                    {item.result}
                  </span>

                </div>
              )
            )}

          </div>

        </section>

      </div>

      {/* ==========================================
          QUICK INFORMATION
      =========================================== */}

      <section className="verification-info-strip">

        <div>
          <span className="info-symbol">
            ✓
          </span>

          <div>
            <strong>
              AI-powered verification
            </strong>

            <p>
              Analyze text, images, documents,
              videos and online sources.
            </p>
          </div>
        </div>

        <div>
          <span className="info-symbol">
            🔒
          </span>

          <div>
            <strong>
              Privacy focused
            </strong>

            <p>
              Your uploaded content stays
              private in your workspace.
            </p>
          </div>
        </div>

        <div>
          <span className="info-symbol">
            ⚡
          </span>

          <div>
            <strong>
              Fast analysis
            </strong>

            <p>
              Get verification results quickly
              and review them in History.
            </p>
          </div>
        </div>

      </section>

    </div>
  );
}
