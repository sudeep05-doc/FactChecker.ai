const express = require("express");
const authMiddleware = require("../middleware/authMiddleware");
const adminMiddleware = require("../middleware/adminMiddleware");
const {
  dashboard,
  listUsers,
  getUser,
  deleteUser,
  listVerifications,
  listReports,
  listFeedback,
  analytics,
} = require("../controllers/adminController");

const router = express.Router();

router.use(authMiddleware, adminMiddleware);

router.get("/dashboard", dashboard);
router.get("/users", listUsers);
router.get("/users/:id", getUser);
router.delete("/users/:id", deleteUser);
router.get("/verifications", listVerifications);
router.get("/reports", listReports);
router.get("/feedback", listFeedback);
router.get("/analytics", analytics);

module.exports = router;
