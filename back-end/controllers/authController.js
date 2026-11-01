const { body, validationResult } = require("express-validator");
const crypto = require("crypto");

const User = require("../models/User");

const { hashPassword, comparePassword } = require("../utils/hashPassword");
const generateToken = require("../utils/generateToken");
const { success, error } = require("../utils/apiResponse");
const { seedDefaultNotifications } = require("../services/notificationService");
const { sendOTPEmail } = require("../services/emailService");

const handleValidation = (req, res) => {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    return error(res, errors.array()[0].msg, 400);
  }

  return null;
};

const registerValidators = [
  body("fullName").trim().notEmpty().withMessage("Please enter your full name."),
  body("username")
    .trim()
    .matches(/^[a-zA-Z0-9_.-]{3,20}$/)
    .withMessage("Username must be 3–20 characters."),
  body("email").trim().isEmail().withMessage("Please enter a valid email address."),
  body("password")
    .isLength({ min: 8 })
    .withMessage("Password must contain at least 8 characters.")
    .matches(/[A-Z]/)
    .withMessage("Use uppercase letters, numbers and symbols.")
    .matches(/[0-9]/)
    .withMessage("Use uppercase letters, numbers and symbols.")
    .matches(/[^A-Za-z0-9]/)
    .withMessage("Use uppercase letters, numbers and symbols."),
  body("phone").optional({ values: "falsy" }).trim(),
];

const loginValidators = [
  body("email").trim().notEmpty().withMessage("Please enter both email and password."),
  body("password").notEmpty().withMessage("Please enter both email and password."),
];

const register = async (req, res, next) => {
  try {
    if (handleValidation(req, res)) return;

    const fullName = req.body.fullName.trim();
    const username = req.body.username.trim().toLowerCase();
    const email = req.body.email.trim().toLowerCase();
    const phone = (req.body.phone || "").trim();
    const password = req.body.password;

    const emailExists = await User.findOne({ email });

    if (emailExists) {
      return error(res, "An account with this email already exists.", 409);
    }

    const usernameExists = await User.findOne({ username });

    if (usernameExists) {
      return error(res, "That username is already taken.", 409);
    }

    const userCount = await User.countDocuments();
    const hashed = await hashPassword(password);

    const user = await User.create({
      fullName,
      username,
      email,
      phone,
      password: hashed,
      role: "user",
      displayRole: "User",
      year: "Final Year",
    });

    await seedDefaultNotifications(user._id);

    const token = generateToken(user._id, user.role);

    return success(
      res,
      {
        token,
        user: user.toPublicJSON(),
        profile: user.toProfileJSON(),
      },
      "Account created successfully.",
      201
    );
  } catch (err) {
    next(err);
  }
};

const login = async (req, res, next) => {
  try {
    if (handleValidation(req, res)) return;

    const email = req.body.email.trim().toLowerCase();
    const password = req.body.password;

    const user = await User.findOne({ email }).select("+password");

    if (!user) {
      return error(res, "Invalid email or password.", 401);
    }

    const match = await comparePassword(password, user.password);

    if (!match) {
      return error(res, "Invalid email or password.", 401);
    }

    const token = generateToken(user._id, user.role);

    return success(res, {
      token,
      user: user.toPublicJSON(),
      profile: user.toProfileJSON(),
    }, "Login successful.");
  } catch (err) {
    next(err);
  }
};

const me = async (req, res) => {
  return success(res, {
    user: req.user.toPublicJSON(),
    profile: req.user.toProfileJSON(),
  });
};

const logout = async (req, res) => {
  return success(res, {}, "Logged out successfully.");
};

const forgotPassword = async (req, res, next) => {
  try {
    const email = req.body.email?.trim().toLowerCase();

    if (!email) {
      return error(res, "Please enter your email address.", 400);
    }
    const user = await User.findOne({ email });
    if (!user) {
      return success(
        res,
        {},
        "If an account exists with this email, an OTP has been sent."
      );
    }
    const otp = crypto.randomInt(100000, 1000000).toString();
    user.resetPasswordOTP = otp;
    user.resetPasswordOTPExpires = new Date(
      Date.now() + 10 * 60 * 1000
    );
    user.resetPasswordOTPAttempts = 0;
    await user.save();
    await sendOTPEmail(user.email, otp);
    return success(
      res,
      {},
      "If an account exists with this email, an OTP has been sent."
    );
  } catch (err) {
    next(err);
  }
};
const verifyResetOTP = async (req, res, next) => {
  try {
    const email = req.body.email?.trim().toLowerCase();
    const otp = req.body.otp?.trim();

    if (!email || !otp) {
      return error(res, "Email and OTP are required.", 400);
    }

    const user = await User.findOne({ email });

    if (!user) {
      return error(res, "Invalid or expired OTP.", 400);
    }

    if (!user.resetPasswordOTP || !user.resetPasswordOTPExpires) {
      return error(res, "Invalid or expired OTP.", 400);
    }

    // Check expiry
    if (user.resetPasswordOTPExpires < new Date()) {
      user.resetPasswordOTP = null;
      user.resetPasswordOTPExpires = null;
      user.resetPasswordOTPAttempts = 0;

      await user.save();

      return error(
        res,
        "OTP has expired. Please request a new one.",
        400
      );
    }

    // Maximum 5 incorrect attempts
    if (user.resetPasswordOTPAttempts >= 5) {
      return error(
        res,
        "Too many incorrect attempts. Please request a new OTP.",
        429
      );
    }

    // Check OTP
    if (user.resetPasswordOTP !== otp) {
      user.resetPasswordOTPAttempts += 1;

      await user.save();

      return error(res, "Invalid OTP.", 400);
    }

    return success(
      res,
      {},
      "OTP verified successfully."
    );
  } catch (err) {
    next(err);
  }
};
const resetPassword = async (req, res, next) => {
  try {
    const email = req.body.email?.trim().toLowerCase();
    const otp = req.body.otp?.trim();
    const newPassword = req.body.newPassword;

    if (!email || !otp || !newPassword) {
      return error(
        res,
        "Email, OTP and new password are required.",
        400
      );
    }

    // Same password rules as signup
    if (newPassword.length < 8) {
      return error(
        res,
        "Password must contain at least 8 characters.",
        400
      );
    }

    if (!/[A-Z]/.test(newPassword)) {
      return error(
        res,
        "Password must contain an uppercase letter.",
        400
      );
    }

    if (!/[0-9]/.test(newPassword)) {
      return error(
        res,
        "Password must contain a number.",
        400
      );
    }

    if (!/[^A-Za-z0-9]/.test(newPassword)) {
      return error(
        res,
        "Password must contain a special character.",
        400
      );
    }

    const user = await User.findOne({ email }).select(
      "+password"
    );

    if (!user) {
      return error(res, "Invalid or expired OTP.", 400);
    }

    if (!user.resetPasswordOTP || !user.resetPasswordOTPExpires) {
      return error(res, "Invalid or expired OTP.", 400);
    }

    // Check expiry
    if (user.resetPasswordOTPExpires < new Date()) {
      return error(
        res,
        "OTP has expired. Please request a new one.",
        400
      );
    }

    // Check OTP
    if (user.resetPasswordOTP !== otp) {
      return error(res, "Invalid OTP.", 400);
    }

    // Hash new password
    const hashedPassword = await hashPassword(newPassword);

    user.password = hashedPassword;

    // Clear OTP after successful reset
    user.resetPasswordOTP = null;
    user.resetPasswordOTPExpires = null;
    user.resetPasswordOTPAttempts = 0;

    await user.save();

    return success(
      res,
      {},
      "Password reset successfully. You can now log in."
    );
  } catch (err) {
    next(err);
  }
};
module.exports = {
  registerValidators,
  loginValidators,
  register,
  login,
  me,
  logout,
  forgotPassword,
  verifyResetOTP,
  resetPassword,
};