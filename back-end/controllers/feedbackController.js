const Feedback = require("../models/Feedback");
const { success, error } = require("../utils/apiResponse");

const createFeedback = async (req, res, next) => {
  try {
    // Feedback must come from a logged-in user
    if (!req.user) {
      return error(res, "Please log in to submit feedback.", 401);
    }

    const { rating, message } = req.body;

    // Validate rating
    const numericRating = Number(rating);

    if (
      !Number.isInteger(numericRating) ||
      numericRating < 1 ||
      numericRating > 5
    ) {
      return error(res, "Please select a rating from 1 to 5.", 400);
    }

    // Validate message
    if (!message || !message.trim()) {
      return error(res, "Please enter your feedback.", 400);
    }

    // Create or update the user's feedback
    const feedback = await Feedback.findOneAndUpdate(
      { user: req.user._id },
      {
        user: req.user._id,
        email: req.user.email,
        rating: numericRating,
        message: message.trim(),
      },
      {
        new: true,
        upsert: true,
        runValidators: true,
        setDefaultsOnInsert: true,
      }
    );

    return success(
      res,
      feedback,
      "Feedback submitted successfully."
    );
  } catch (err) {
    next(err);
  }
};

const listFeedback = async (req, res, next) => {
  try {
    if (!req.user) {
      return error(res, "Please log in to view feedback.", 401);
    }

    const feedback = await Feedback.findOne({
  user: req.user._id,
}).populate("user", "email");

    return success(res, feedback);
  } catch (err) {
    next(err);
  }
};

module.exports = {
  createFeedback,
  listFeedback,
};