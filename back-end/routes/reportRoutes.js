const express = require("express");
const authMiddleware = require("../middleware/authMiddleware");
const { createReport, listReports } = require("../controllers/reportController");

const router = express.Router();

router.post("/", authMiddleware, createReport);
router.get("/", authMiddleware, listReports);

module.exports = router;
