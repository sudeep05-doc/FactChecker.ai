const express = require("express");
const rateLimit = require("express-rate-limit");
const authMiddleware = require("../middleware/authMiddleware");
const { optionalAuth } = require("../middleware/authMiddleware");
const {
  registerValidators,
  loginValidators,
  register,
  login,
  me,
  logout,
} = require("../controllers/authController");

const router = express.Router();

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    success: false,
    message: "Too many authentication attempts. Please try again later.",
  },
});

router.post("/register", authLimiter, registerValidators, register);
router.post("/login", authLimiter, loginValidators, login);
router.get("/me", authMiddleware, me);
router.post("/logout", optionalAuth, logout);

module.exports = router;
