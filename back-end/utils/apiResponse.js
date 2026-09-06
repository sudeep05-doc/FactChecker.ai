const success = (res, data = {}, message = "Operation successful", statusCode = 200) => {
  return res.status(statusCode).json({
    success: true,
    message,
    data,
  });
};

const error = (res, message = "Something went wrong", statusCode = 500, extra = {}) => {
  return res.status(statusCode).json({
    success: false,
    message,
    ...extra,
  });
};

module.exports = {
  success,
  error,
};
