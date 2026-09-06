const { error } = require("../utils/apiResponse");

const notFound = (req, res) => {
  return error(res, `Route not found: ${req.originalUrl}`, 404);
};

const errorMiddleware = (err, req, res, next) => {
  if (res.headersSent) {
    return next(err);
  }

  if (err.name === "ValidationError") {
    return error(res, "Invalid data provided.", 400);
  }

  if (err.code === 11000) {
    const field = Object.keys(err.keyPattern || {})[0] || "field";
    return error(res, `An account with that ${field} already exists.`, 409);
  }

  if (err.name === "CastError") {
    return error(res, "Resource not found.", 404);
  }

  if (err.name === "MulterError") {
    if (err.code === "LIMIT_FILE_SIZE") {
      return error(res, "File size must be less than 25 MB.", 400);
    }

    return error(res, err.message || "File upload failed.", 400);
  }

  const statusCode = err.statusCode || 500;
  const message =
    statusCode === 500
      ? "Something went wrong"
      : err.message || "Something went wrong";

  return error(res, message, statusCode);
};

module.exports = {
  notFound,
  errorMiddleware,
};
