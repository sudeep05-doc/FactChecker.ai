const { error } = require("../utils/apiResponse");

const adminMiddleware = (req, res, next) => {
  if (!req.user) {
    return error(res, "Not authorized. Please log in.", 401);
  }

  if (req.user.role !== "admin") {
    return error(res, "Admin access required.", 403);
  }

  next();
};

module.exports = adminMiddleware;
