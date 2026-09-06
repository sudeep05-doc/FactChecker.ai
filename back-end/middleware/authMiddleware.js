const jwt = require("jsonwebtoken");
const User = require("../models/User");
const { error } = require("../utils/apiResponse");

const authMiddleware = async (req, res, next) => {
  try {
    const header = req.headers.authorization || "";
    const token = header.startsWith("Bearer ")
      ? header.slice(7)
      : null;

    if (!token) {
      return error(res, "Not authorized. Please log in.", 401);
    }

    let decoded;

    try {
      decoded = jwt.verify(token, process.env.JWT_SECRET);
    } catch (err) {
      if (err.name === "TokenExpiredError") {
        return error(res, "Session expired. Please log in again.", 401);
      }

      return error(res, "Invalid token.", 401);
    }

    const user = await User.findById(decoded.id);

    if (!user) {
      return error(res, "User not found.", 401);
    }

    req.user = user;
    next();
  } catch (err) {
    next(err);
  }
};

const optionalAuth = async (req, res, next) => {
  try {
    const header = req.headers.authorization || "";
    const token = header.startsWith("Bearer ")
      ? header.slice(7)
      : null;

    if (!token) {
      req.user = null;
      return next();
    }

    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      req.user = await User.findById(decoded.id);
    } catch {
      req.user = null;
    }

    next();
  } catch (err) {
    next(err);
  }
};

module.exports = authMiddleware;
module.exports.optionalAuth = optionalAuth;
