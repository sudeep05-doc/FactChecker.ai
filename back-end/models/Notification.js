const mongoose = require("mongoose");

const notificationSchema = new mongoose.Schema(
  {
    user: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    type: {
      type: String,
      enum: ["warning", "system", "mention", "success", "info"],
      default: "system",
    },
    title: {
      type: String,
      required: true,
    },
    description: {
      type: String,
      default: "",
    },
    time: {
      type: String,
      default: "",
    },
    action: {
      type: String,
      default: "",
    },
    unread: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true,
  }
);

notificationSchema.methods.toClientJSON = function toClientJSON() {
  return {
    id: this._id.toString(),
    type: this.type,
    title: this.title,
    description: this.description,
    time: this.time,
    action: this.action,
    unread: this.unread,
  };
};

module.exports = mongoose.model("Notification", notificationSchema);
