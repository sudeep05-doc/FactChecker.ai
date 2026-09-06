const {
  listForUser,
  markRead,
  markAllRead,
} = require("../services/notificationService");
const { success, error } = require("../utils/apiResponse");

const getNotifications = async (req, res, next) => {
  try {
    const data = await listForUser(req.user._id);
    return success(res, data);
  } catch (err) {
    next(err);
  }
};

const markNotificationRead = async (req, res, next) => {
  try {
    const item = await markRead(req.user._id, req.params.id);

    if (!item) {
      return error(res, "Notification not found.", 404);
    }

    return success(res, item.toClientJSON(), "Notification marked as read.");
  } catch (err) {
    next(err);
  }
};

const markAllNotificationsRead = async (req, res, next) => {
  try {
    await markAllRead(req.user._id);
    const data = await listForUser(req.user._id);
    return success(res, data, "All notifications marked as read.");
  } catch (err) {
    next(err);
  }
};

module.exports = {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
};
