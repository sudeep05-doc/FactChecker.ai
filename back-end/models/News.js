const mongoose = require("mongoose");

const newsSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    source: {
      type: String,
      default: "",
    },
    url: {
      type: String,
      default: "",
    },
    summary: {
      type: String,
      default: "",
    },
    category: {
      type: String,
      default: "general",
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
    },
  },
  {
    timestamps: true,
  }
);

module.exports = mongoose.model("News", newsSchema);
