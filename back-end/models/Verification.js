const mongoose = require("mongoose");

const verificationSchema = new mongoose.Schema(
  {
    user: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    contentType: {
      type: String,
      enum: ["text", "website", "youtube", "image", "pdf", "video"],
      default: "text",
    },
    text: {
      type: String,
      default: "",
    },
    url: {
      type: String,
      default: "",
    },
    inputContent: {
      type: String,
      default: "",
    },
    fileName: {
      type: String,
      default: "",
    },
    storedFileName: {
      type: String,
      default: "",
    },
    label: {
      type: String,
      default: "Unknown",
    },
    confidence: {
      type: Number,
      default: null,
    },
    fakeScore: {
      type: Number,
      default: null,
    },
    trustedSource: {
      type: Boolean,
      default: null,
    },
    predictionType: {
      type: String,
      enum: ["evidence_verification", "dataset_classification"],
    },
    datasetPrediction: {
      type: String,
      default: null,
    },
    datasetScore: {
      type: Number,
      min: 0,
      max: 1,
      default: null,
    },
    classScores: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },
    modelIdentity: {
      type: String,
      default: null,
    },
    datasetIdentity: {
      type: String,
      default: null,
    },
    confidenceSemantics: {
      type: String,
      enum: [
        "calibrated_class_probability",
        "uncalibrated_dataset_score",
        "not_available",
      ],
    },
    isMock: {
      type: Boolean,
    },
    evidenceStatus: {
      type: String,
      enum: [
        "not_implemented",
        "unavailable",
        "not_applicable",
        "evaluated",
        "failed",
      ],
    },
    explanationProvenance: {
      type: String,
      enum: ["mock_notice", "evidence_evaluator", "dataset_classifier"],
    },
    status: {
      type: String,
    },
    verdict: {
      type: String,
      enum: [
        "SUPPORTED",
        "REFUTED",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
        "CHERRY_PICKING",
      ],
      default: null,
    },
    explanation: {
      type: String,
      default: "",
    },
    factors: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },
    reasoning: {
      type: [String],
      default: [],
    },
    reportId: {
      type: String,
      default: null,
    },
    processingTime: {
      type: String,
      default: null,
    },
    time: {
      type: String,
      default: "",
    },
    method: {
      type: String,
      default: "unknown",
    },
  },
  {
    timestamps: true,
  }
);

verificationSchema.pre("validate", function validatePredictionSemantics() {
  if (
    this.isMock &&
    (this.verdict != null || this.confidence != null)
  ) {
    throw new Error("Mock records cannot contain a verdict or confidence.");
  }

  if (
    this.predictionType === "dataset_classification" &&
    (this.verdict != null ||
      this.evidenceStatus !== "not_applicable" ||
      !this.datasetIdentity ||
      !this.modelIdentity ||
      ((this.datasetScore != null || this.classScores != null) &&
        this.confidenceSemantics !== "uncalibrated_dataset_score" &&
        this.confidenceSemantics !== "calibrated_class_probability"))
  ) {
    throw new Error(
      "Dataset predictions require model and dataset identity and cannot be factual verdicts."
    );
  }

  if (
    (this.datasetPrediction != null ||
      this.datasetScore != null ||
      this.classScores != null) &&
    this.predictionType !== "dataset_classification"
  ) {
    throw new Error(
      "Dataset predictions and scores require dataset-classification scope."
    );
  }

  if (
    this.verdict != null &&
    (this.predictionType !== "evidence_verification" ||
      this.evidenceStatus !== "evaluated")
  ) {
    throw new Error("Evidence verdicts require evaluated evidence.");
  }

  if (
    this.evidenceStatus === "evaluated" &&
    (this.verdict == null ||
      this.explanationProvenance !== "evidence_evaluator")
  ) {
    throw new Error(
      "Evaluated evidence requires a verdict and evidence-evaluator provenance."
    );
  }

  if (
    this.confidence != null &&
    (this.predictionType != null && !this.confidenceSemantics ||
      this.confidenceSemantics === "not_available")
  ) {
    throw new Error("Confidence requires explicit score semantics.");
  }
});

verificationSchema.methods.toResultJSON = function toResultJSON() {
  return {
    id: this._id.toString(),
    predictionType: this.predictionType || "legacy_unverified",
    datasetPrediction: this.datasetPrediction ?? null,
    datasetScore: this.datasetScore ?? null,
    classScores: this.classScores ?? null,
    modelIdentity: this.modelIdentity ?? null,
    datasetIdentity: this.datasetIdentity ?? null,
    confidenceSemantics:
      this.confidenceSemantics || "legacy_unknown",
    isMock: this.isMock ?? null,
    evidenceStatus:
      this.evidenceStatus || "not_available",
    explanationProvenance:
      this.explanationProvenance || "legacy_unverified",
    status: this.status || "legacy_unverified",
    verdict: this.verdict ?? null,
    label: this.label,
    confidence: this.confidence,
    fakeScore: this.fakeScore,
    trustedSource: this.trustedSource,
    explanation: this.explanation,
    factors: this.factors,
    reasoning: this.reasoning,
    contentType: this.contentType,
    inputContent: this.inputContent,
    fileName: this.fileName,
    reportId: this.reportId,
    processingTime: this.processingTime,
    time: this.time,
    method: this.method,
    text: this.text,
  };
};

verificationSchema.methods.toHistoryJSON = function toHistoryJSON() {
  return {
    id: this._id.toString(),
    predictionType: this.predictionType || "legacy_unverified",
    datasetPrediction: this.datasetPrediction ?? null,
    datasetScore: this.datasetScore ?? null,
    classScores: this.classScores ?? null,
    modelIdentity: this.modelIdentity ?? null,
    datasetIdentity: this.datasetIdentity ?? null,
    confidenceSemantics:
      this.confidenceSemantics || "legacy_unknown",
    isMock: this.isMock ?? null,
    evidenceStatus:
      this.evidenceStatus || "not_available",
    explanationProvenance:
      this.explanationProvenance || "legacy_unverified",
    status: this.status || "legacy_unverified",
    verdict: this.verdict ?? null,
    text: this.text,
    label: this.label,
    confidence: this.confidence,
    time: this.time,
    contentType: this.contentType,
    reportId: this.reportId,
  };
};

module.exports = mongoose.model("Verification", verificationSchema);
