const { body, validationResult } = require("express-validator");
const User = require("../models/User");
const { hashPassword, comparePassword } = require("../utils/hashPassword");
const generateToken = require("../utils/generateToken");
const { success, error } = require("../utils/apiResponse");
const { seedDefaultNotifications } = require("../services/notificationService");

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
      role: userCount === 0 ? "admin" : "user",
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

module.exports = {
  registerValidators,
  loginValidators,
  register,
  login,
  me,
  logout,
};
