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
      default: 0,
    },
    fakeScore: {
      type: Number,
      default: 0,
    },
    trustedSource: {
      type: Boolean,
      default: false,
    },
    explanation: {
      type: String,
      default: "",
    },
    factors: {
      source: { type: Number, default: 0 },
      credibility: { type: Number, default: 0 },
      writing: { type: Number, default: 0 },
      consistency: { type: Number, default: 0 },
    },
    reasoning: {
      type: [String],
      default: [],
    },
    reportId: {
      type: String,
      required: true,
    },
    processingTime: {
      type: String,
      default: "1.8 seconds",
    },
    time: {
      type: String,
      default: "",
    },
    method: {
      type: String,
      default: "rule-based",
    },
  },
  {
    timestamps: true,
  }
);

verificationSchema.methods.toResultJSON = function toResultJSON() {
  return {
    id: this._id.toString(),
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
    text: this.text,
    label: this.label,
    confidence: this.confidence,
    time: this.time,
    contentType: this.contentType,
    reportId: this.reportId,
  };
};

module.exports = mongoose.model("Verification", verificationSchema);
