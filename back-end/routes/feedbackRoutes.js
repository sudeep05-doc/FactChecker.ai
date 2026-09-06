const express = require("express");
const authMiddleware = require("../middleware/authMiddleware");
const { optionalAuth } = require("../middleware/authMiddleware");
const {
  createFeedback,
  listFeedback,
} = require("../controllers/feedbackController");

const router = express.Router();

router.post("/", optionalAuth, createFeedback);
router.get("/", authMiddleware, listFeedback);

module.exports = router;
