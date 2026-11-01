const mongoose = require("mongoose");

const userSchema = new mongoose.Schema(
  {
    fullName: {
      type: String,
      required: true,
      trim: true,
    },
    username: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      lowercase: true,
    },
    email: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      lowercase: true,
    },
    phone: {
      type: String,
      default: "",
      trim: true,
    },
    password: {
      type: String,
      required: true,
      select: false,
    },
    resetPasswordOTP: {
  type: String,
  default: null,
},

resetPasswordOTPExpires: {
  type: Date,
  default: null,
},

resetPasswordOTPAttempts: {
  type: Number,
  default: 0,
},
    role: {
      type: String,
      enum: ["user", "admin"],
      default: "user",
    },
    college: {
      type: String,
      default: "",
    },
    course: {
      type: String,
      default: "",
    },
    year: {
      type: String,
      default: "Final Year",
    },
    displayRole: {
      type: String,
      default: "User",
    },
    about: {
      type: String,
      default: "",
    },
    photo: {
      type: String,
      default: "",
    },
  },
  {
    timestamps: true,
  }
);

userSchema.methods.toPublicJSON = function toPublicJSON() {
  return {
    id: this._id.toString(),
    fullName: this.fullName,
    username: this.username,
    email: this.email,
    phone: this.phone || "",
    role: this.role,
    createdAt: this.createdAt,
    updatedAt: this.updatedAt,
  };
};

userSchema.methods.toProfileJSON = function toProfileJSON() {
  return {
    name: this.fullName,
    college: this.college || "",
    email: this.email,
    course: this.course || "",
    year: this.year || "Final Year",
    role: this.displayRole || "User",
    about: this.about || "",
    photo: this.photo || "",
    username: this.username,
    phone: this.phone || "",
  };
};

module.exports = mongoose.model("User", userSchema);