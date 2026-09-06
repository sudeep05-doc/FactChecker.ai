const express = require("express");
const authMiddleware = require("../middleware/authMiddleware");
const { optionalAuth } = require("../middleware/authMiddleware");
const { upload } = require("../middleware/uploadMiddleware");
const {
  runVerification,
  getHistory,
  getVerification,
  deleteVerification,
  clearHistory,
} = require("../controllers/verificationController");

const router = express.Router();

router.post("/verify", optionalAuth, upload.single("file"), runVerification);
router.get("/history", authMiddleware, getHistory);
router.get("/:id", authMiddleware, getVerification);
router.delete("/:id", authMiddleware, deleteVerification);
router.delete("/", authMiddleware, clearHistory);

module.exports = router;
