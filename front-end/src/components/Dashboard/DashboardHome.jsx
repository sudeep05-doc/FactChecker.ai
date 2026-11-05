import { useContext, useEffect, useRef, useState } from "react";
import { AppContext } from "../../context/AppContext";
import { getPredictionPresentation } from "../../utils/prediction";

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

export default function DashboardHome({
  onAnalyze,
  onViewHistory,
}) {
  const { history = [] } = useContext(AppContext);
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

  const cameraVideoRef = useRef(null);
  const cameraRequestRef = useRef(0);
  const [cameraStream, setCameraStream] = useState(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraError, setCameraError] = useState("");

  useEffect(() => {
    if (!cameraStream) return undefined;

    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = cameraStream;
    }

    return () => {
      cameraStream.getTracks().forEach((track) => track.stop());
    };
  }, [cameraStream]);

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

  const handleRemoveFile = (event) => {
    event.stopPropagation();
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();

    setIsDragging(false);

    const file =
      event.dataTransfer.files?.[0];

    handleFile(file);
  };

  const closeCamera = () => {
    cameraRequestRef.current += 1;
    setCameraStream(null);
    setCameraOpen(false);
    setCameraLoading(false);
    setCameraError("");
  };

  const openCamera = async (event) => {
    event.stopPropagation();
    setCameraOpen(true);
    setCameraLoading(true);
    setCameraError("");

    const requestId = cameraRequestRef.current + 1;
    cameraRequestRef.current = requestId;

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraLoading(false);
      setCameraError(
        "Camera access is not available in this browser. Use HTTPS or localhost, or upload an image instead."
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });

      if (cameraRequestRef.current !== requestId) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      setCameraStream(stream);
      setCameraLoading(false);
    } catch (error) {
      if (cameraRequestRef.current !== requestId) return;

      setCameraLoading(false);
      setCameraError(
        error.name === "NotAllowedError" || error.name === "PermissionDeniedError"
          ? "Camera permission was denied. Allow camera access in your browser settings, then try again."
          : error.name === "NotFoundError"
          ? "No camera was found on this device. You can upload an image instead."
          : `Unable to open the camera: ${error.message || "Please try again."}`
      );
    }
  };

  const captureCameraImage = () => {
    const video = cameraVideoRef.current;
    if (!video?.videoWidth || !video?.videoHeight) {
      setCameraError("The camera is not ready yet. Please wait and try again.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);

    canvas.toBlob((blob) => {
      if (!blob) {
        setCameraError("Unable to capture an image. Please try again.");
        return;
      }

      handleFile(
        new File([blob], `camera-capture-${Date.now()}.jpg`, {
          type: "image/jpeg",
        })
      );
      closeCamera();
    }, "image/jpeg", 0.92);
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
                <button
                  type="button"
                  className="remove-upload-button"
                  aria-label="Remove uploaded file"
                  title="Remove uploaded file"
                  onClick={handleRemoveFile}
                >
                  ×
                </button>

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
                  {activeType} to check prototype availability
                </span>

                <small>
                  Maximum file size: 25 MB
                </small>
              </>
            )}

            {activeType === "image" && (
              <button
                type="button"
                className="camera-upload-button"
                aria-label="Take or upload a photo with your camera"
                title="Take or upload a photo with your camera"
                onClick={openCamera}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7.5h3l1.5-2h7l1.5 2h3A1.5 1.5 0 0 1 21.5 9v9a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 18V9A1.5 1.5 0 0 1 4 7.5Z" />
                  <circle cx="12" cy="13" r="3.5" />
                </svg>
                <span>Camera</span>
              </button>
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

              <p>Your latest submissions</p>
            </div>

            <button
              type="button"
              onClick={onViewHistory}
            >
              View all
            </button>
          </div>

          <div className="recent-verification-list">

            {history.slice(0, 3).map(
              (item) => {
                const presentation = getPredictionPresentation(item);
                const inputType = item.contentType || "Content";
                const title = `${inputType.charAt(0).toUpperCase()}${inputType.slice(1)} submission`;
                const hasVerdict = [
                  "evidence_verdict",
                  "dataset_classification",
                ].includes(presentation.kind);

                return (
                <div
                  key={item.id}
                  className="recent-verification"
                >

                  <div>
                    <strong>
                      {title}
                    </strong>

                    <span>
                      {item.time || "Saved"}
                    </span>
                  </div>

                  <span
                    className={`verification-result ${hasVerdict ? "available" : "unavailable"}`}
                  >
                    {hasVerdict ? presentation.summary : "No verdict generated"}
                  </span>

                </div>
                );
              }
            )}

            {history.length === 0 && (
              <p className="recent-verification-empty">
                No submissions yet. Start an analysis to see it here.
              </p>
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
              Research prototype — verification unavailable
            </strong>

            <p>
              Evidence-based factual verification is not implemented. Submissions
              do not receive a factual verdict or confidence score.
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

      {cameraOpen && (
        <div
          className="camera-capture-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeCamera();
          }}
        >
          <section
            className="camera-capture-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="camera-dialog-title"
          >
            <header>
              <h2 id="camera-dialog-title">Capture an image</h2>
              <button
                type="button"
                aria-label="Close camera"
                onClick={closeCamera}
              >
                ×
              </button>
            </header>

            {cameraStream ? (
              <video
                ref={cameraVideoRef}
                className="camera-preview"
                autoPlay
                playsInline
                muted
              />
            ) : (
              <div className="camera-preview camera-preview-message" role="status">
                {cameraLoading
                  ? "Requesting camera permission…"
                  : cameraError || "Camera is unavailable."}
              </div>
            )}

            {cameraError && cameraStream && (
              <p className="camera-error" role="alert">{cameraError}</p>
            )}

            <footer>
              <button type="button" className="camera-cancel-button" onClick={closeCamera}>
                Cancel
              </button>
              <button
                type="button"
                className="camera-capture-button"
                onClick={captureCameraImage}
                disabled={!cameraStream}
              >
                Capture photo
              </button>
            </footer>
          </section>
        </div>
      )}

    </div>
  );
}
