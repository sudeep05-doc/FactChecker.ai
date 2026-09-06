const Feedback = require("../models/Feedback");
const Verification = require("../models/Verification");
const mongoose = require("mongoose");
const { success, error } = require("../utils/apiResponse");

const createFeedback = async (req, res, next) => {
  try {
    const { helpful, comment, verification } = req.body;

    if (typeof helpful !== "boolean") {
      return error(res, "Please indicate whether the result was helpful.", 400);
    }

    if (verification) {
      if (!mongoose.isValidObjectId(verification)) {
        return error(res, "Invalid verification reference.", 400);
      }

      // Authenticated users may only attach feedback to their own history.
      if (req.user) {
        const record = await Verification.findOne({ _id: verification, user: req.user._id });
        if (!record) return error(res, "Verification not found.", 404);
      }
    }

    const feedback = await Feedback.create({
      user: req.user?._id || null,
      verification: verification || null,
      helpful,
      comment: comment || "",
    });

    return success(res, feedback, "Feedback saved.", 201);
  } catch (err) {
    next(err);
  }
};

const listFeedback = async (req, res, next) => {
  try {
    const items = await Feedback.find({ user: req.user._id }).sort({
      createdAt: -1,
    });

    return success(res, items);
  } catch (err) {
    next(err);
  }
};

module.exports = {
  createFeedback,
  listFeedback,
};
