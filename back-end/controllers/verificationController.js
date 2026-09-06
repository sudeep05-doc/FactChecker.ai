const Verification = require("../models/Verification");
const Report = require("../models/Report");
const Feedback = require("../models/Feedback");
const { verifyContent } = require("../services/verificationService");
const { success, error } = require("../utils/apiResponse");

const runVerification = async (req, res, next) => {
  try {
    const type = req.body.type || "text";
    const content = req.body.content || "";
    const file = req.file || null;

    const allowedTypes = ["text", "website", "youtube", "image", "pdf", "video"];

    if (!allowedTypes.includes(type)) {
      return error(res, "Unsupported verification type.", 400);
    }

    if (type === "text" && String(content).trim().length < 10) {
      return error(res, "Please enter at least 10 characters.", 400);
    }

    if ((type === "website" || type === "youtube") && !String(content).trim()) {
      return error(res, "Please enter a valid URL.", 400);
    }

    if ((type === "image" || type === "pdf" || type === "video") && !file) {
      return error(res, "Please select a file first.", 400);
    }

    const result = await verifyContent({
      type,
      content,
      file,
    });

    if (!req.user) {
      return success(res, {
        ...result,
        id: Date.now(),
      }, "Verification completed.");
    }

    const record = await Verification.create({
      user: req.user._id,
      contentType: result.contentType,
      text: result.text,
      url: type === "website" || type === "youtube" ? content : "",
      inputContent: result.inputContent,
      fileName: result.fileName,
      storedFileName: file ? file.filename : "",
      label: result.label,
      confidence: result.confidence,
      fakeScore: result.fakeScore,
      trustedSource: result.trustedSource,
      explanation: result.explanation,
      factors: result.factors,
      reasoning: result.reasoning,
      reportId: result.reportId,
      processingTime: result.processingTime,
      time: result.time,
      method: result.method,
    });

    return success(
      res,
      record.toResultJSON(),
      "Verification completed."
    );
  } catch (err) {
    next(err);
  }
};

const getHistory = async (req, res, next) => {
  try {
    const records = await Verification.find({ user: req.user._id }).sort({
      createdAt: -1,
    });

    return success(
      res,
      records.map((item) => item.toHistoryJSON())
    );
  } catch (err) {
    next(err);
  }
};

const getVerification = async (req, res, next) => {
  try {
    const record = await Verification.findOne({
      _id: req.params.id,
      user: req.user._id,
    });

    if (!record) {
      return error(res, "Verification not found.", 404);
    }

    return success(res, record.toResultJSON());
  } catch (err) {
    next(err);
  }
};

const deleteVerification = async (req, res, next) => {
  try {
    const record = await Verification.findOneAndDelete({
      _id: req.params.id,
      user: req.user._id,
    });

    if (!record) {
      return error(res, "Verification not found.", 404);
    }

    await Promise.all([
      Report.deleteMany({ verification: record._id }),
      Feedback.deleteMany({ verification: record._id }),
    ]);

    return success(res, {}, "Verification deleted.");
  } catch (err) {
    next(err);
  }
};

const clearHistory = async (req, res, next) => {
  try {
    const records = await Verification.find({ user: req.user._id }).select("_id");
    const verificationIds = records.map((record) => record._id);

    await Promise.all([
      Verification.deleteMany({ _id: { $in: verificationIds } }),
      Report.deleteMany({ verification: { $in: verificationIds } }),
      Feedback.deleteMany({ verification: { $in: verificationIds } }),
    ]);
    return success(res, {}, "History cleared.");
  } catch (err) {
    next(err);
  }
};

module.exports = {
  runVerification,
  getHistory,
  getVerification,
  deleteVerification,
  clearHistory,
};
