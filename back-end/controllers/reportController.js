const Report = require("../models/Report");
const Verification = require("../models/Verification");
const mongoose = require("mongoose");
const { success, error } = require("../utils/apiResponse");

const createReport = async (req, res, next) => {
  try {
    const { reason, details, verification } = req.body;

    if (!reason || !String(reason).trim()) {
      return error(res, "Please provide a report reason.", 400);
    }

    if (verification) {
      if (!mongoose.isValidObjectId(verification)) {
        return error(res, "Invalid verification reference.", 400);
      }

      const record = await Verification.findOne({ _id: verification, user: req.user._id });
      if (!record) return error(res, "Verification not found.", 404);
    }

    const report = await Report.create({
      user: req.user?._id || null,
      verification: verification || null,
      reason: String(reason).trim(),
      details: details || "",
    });

    return success(res, report, "Report submitted.", 201);
  } catch (err) {
    next(err);
  }
};

const listReports = async (req, res, next) => {
  try {
    const reports = await Report.find({ user: req.user._id }).sort({
      createdAt: -1,
    });

    return success(res, reports);
  } catch (err) {
    next(err);
  }
};

module.exports = {
  createReport,
  listReports,
};
