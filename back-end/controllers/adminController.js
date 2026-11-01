const User = require("../models/User");
const Verification = require("../models/Verification");
const Report = require("../models/Report");
const Feedback = require("../models/Feedback");
const { success, error } = require("../utils/apiResponse");

const dashboard = async (req, res, next) => {
  try {
    const [
      users,
      verifications,
      reports,
      feedbacks,
      datasetLabelFakeCount,
      datasetLabelRealCount,
      legacyUnverifiedCount,
    ] =
      await Promise.all([
        User.countDocuments(),
        Verification.countDocuments(),
        Report.countDocuments(),
        Feedback.countDocuments(),
        Verification.countDocuments({
          predictionType: "dataset_classification",
          datasetPrediction: { $in: ["FAKE", "Fake News"] },
        }),
        Verification.countDocuments({
          predictionType: "dataset_classification",
          datasetPrediction: { $in: ["REAL", "Real News"] },
        }),
        Verification.countDocuments({
          predictionType: { $exists: false },
        }),
      ]);

    return success(res, {
      users,
      verifications,
      reports,
      feedbacks,
      datasetLabelFakeCount,
      datasetLabelRealCount,
      legacyUnverifiedCount,
    });
  } catch (err) {
    next(err);
  }
};

const listUsers = async (req, res, next) => {
  try {
    const users = await User.find().sort({ createdAt: -1 });
    return success(
      res,
      users.map((user) => user.toPublicJSON())
    );
  } catch (err) {
    next(err);
  }
};

const getUser = async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id);

    if (!user) {
      return error(res, "User not found.", 404);
    }

    return success(res, {
      ...user.toPublicJSON(),
      profile: user.toProfileJSON(),
    });
  } catch (err) {
    next(err);
  }
};

const deleteUser = async (req, res, next) => {
  try {
    if (req.user._id.toString() === req.params.id) {
      return error(res, "You cannot delete your own admin account.", 400);
    }

    const user = await User.findByIdAndDelete(req.params.id);

    if (!user) {
      return error(res, "User not found.", 404);
    }

    await Verification.deleteMany({ user: user._id });

    return success(res, {}, "User deleted.");
  } catch (err) {
    next(err);
  }
};

const listVerifications = async (req, res, next) => {
  try {
    const records = await Verification.find()
      .populate("user", "fullName email username")
      .sort({ createdAt: -1 })
      .limit(200);

    return success(
      res,
      records.map((item) => ({
        ...item.toHistoryJSON(),
        user: item.user,
      }))
    );
  } catch (err) {
    next(err);
  }
};

const listReports = async (req, res, next) => {
  try {
    const reports = await Report.find()
      .populate("user", "fullName email username")
      .sort({ createdAt: -1 });

    return success(res, reports);
  } catch (err) {
    next(err);
  }
};

const listFeedback = async (req, res, next) => {
  try {
    const items = await Feedback.find()
      .populate("user", "fullName email username")
      .sort({ createdAt: -1 });

    return success(res, items);
  } catch (err) {
    next(err);
  }
};

const analytics = async (req, res, next) => {
  try {
    const recent = await Verification.find()
      .sort({ createdAt: -1 })
      .limit(20);

    const total = await Verification.countDocuments();
    const [
      datasetLabelFakeCount,
      datasetLabelRealCount,
      legacyUnverifiedCount,
    ] = await Promise.all([
      Verification.countDocuments({
        predictionType: "dataset_classification",
        datasetPrediction: { $in: ["FAKE", "Fake News"] },
      }),
      Verification.countDocuments({
        predictionType: "dataset_classification",
        datasetPrediction: { $in: ["REAL", "Real News"] },
      }),
      Verification.countDocuments({
        predictionType: { $exists: false },
      }),
    ]);

    return success(res, {
      total,
      datasetLabelFakeCount,
      datasetLabelRealCount,
      legacyUnverifiedCount,
      recent: recent.map((item) => item.toHistoryJSON()),
    });
  } catch (err) {
    next(err);
  }
};

module.exports = {
  dashboard,
  listUsers,
  getUser,
  deleteUser,
  listVerifications,
  listReports,
  listFeedback,
  analytics,
};
