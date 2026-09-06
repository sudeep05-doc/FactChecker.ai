const express = require("express");
const authMiddleware = require("../middleware/authMiddleware");
const adminMiddleware = require("../middleware/adminMiddleware");
const { create, list, getById } = require("../controllers/newsController");

const router = express.Router();

router.get("/", list);
router.get("/:id", getById);
router.post("/", authMiddleware, adminMiddleware, create);

module.exports = router;
