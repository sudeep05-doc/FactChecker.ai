const Notification = require("../models/Notification");

const defaultNotifications = [
  {
    type: "warning",
    title: "Possible misinformation detected in a viral article.",
    description:
      "An article from an unknown source contains multiple misleading claims. Check the article before sharing.",
    time: "1h ago",
    action: "Analyze Now",
    unread: true,
  },
  {
    type: "system",
    title: "Platform Update complete.",
    description:
      "We've updated our fact-checking algorithms. Explore the latest verification features.",
    time: "3h ago",
    action: "Explore Features",
    unread: true,
  },
  {
    type: "mention",
    title: "@Sarah mentioned you in a Saved Article comment.",
    description:
      '@Sarah: "Check this out, it seems related to your saved topic..."',
    time: "3h ago",
    action: "View Comment",
    unread: true,
  },
];

const seedDefaultNotifications = async (userId) => {
  const existing = await Notification.countDocuments({ user: userId });

  if (existing > 0) {
    return;
  }

  await Notification.insertMany(
    defaultNotifications.map((item) => ({
      ...item,
      user: userId,
    }))
  );
};

const listForUser = async (userId) => {
  const items = await Notification.find({ user: userId }).sort({
    createdAt: -1,
  });

  return items.map((item) => item.toClientJSON());
};

const markRead = async (userId, id) => {
  return Notification.findOneAndUpdate(
    { _id: id, user: userId },
    { unread: false },
    { new: true }
  );
};

const markAllRead = async (userId) => {
  await Notification.updateMany({ user: userId }, { unread: false });
};

module.exports = {
  seedDefaultNotifications,
  listForUser,
  markRead,
  markAllRead,
};
