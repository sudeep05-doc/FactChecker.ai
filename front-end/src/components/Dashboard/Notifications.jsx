import { useMemo, useState } from "react";
import "./Notifications.css";

const initialNotifications = [
  {
    id: 1,
    type: "warning",
    category: "system",
    title: "Possible misinformation detected in a viral article.",
    message:
      "Article from source [Unknown.news] has multiple misleading claims. Check the article before sharing.",
    time: "1h ago",
    unread: true,
    action: "Analyze Now",
    actionView: "analyze",
  },
  {
    id: 2,
    type: "success",
    category: "system",
    title: "Platform Update complete.",
    message:
      "We've updated our fact-checking algorithms. Explore the latest verification features.",
    time: "3h ago",
    unread: true,
    action: "Explore Features",
    actionView: "settings",
  },
  {
    id: 3,
    type: "mention",
    category: "mentions",
    title: "@Sarah mentioned you in a Saved Article comment.",
    message:
      '@Sarah: "Check this out, it seems related to your saved topic..."',
    time: "3h ago",
    unread: true,
    action: "View Comment",
    actionView: "saved",
  },
  {
    id: 4,
    type: "info",
    category: "system",
    title: "Your weekly credibility report is ready.",
    message:
      "Review your recent verification activity and misinformation trends.",
    time: "Yesterday",
    unread: false,
    action: "View Report",
    actionView: "statistics",
  },
  {
    id: 5,
    type: "success",
    category: "settings",
    title: "Profile settings saved successfully.",
    message:
      "Your Student Profile information has been updated.",
    time: "Yesterday",
    unread: false,
    action: "View Profile",
    actionView: "profile",
  },
];

const Notifications = ({ setActiveView }) => {
  const [notifications, setNotifications] =
    useState(initialNotifications);

  const [activeTab, setActiveTab] = useState("all");

  const unreadCount = notifications.filter(
    (item) => item.unread
  ).length;

  const filteredNotifications = useMemo(() => {
    if (activeTab === "all") {
      return notifications;
    }

    return notifications.filter(
      (item) => item.category === activeTab
    );
  }, [notifications, activeTab]);

  const markAsRead = (id) => {
    setNotifications((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, unread: false }
          : item
      )
    );
  };

  const markAllAsRead = () => {
    setNotifications((prev) =>
      prev.map((item) => ({
        ...item,
        unread: false,
      }))
    );
  };

  const deleteNotification = (id) => {
    setNotifications((prev) =>
      prev.filter((item) => item.id !== id)
    );
  };

  const handleAction = (notification) => {
    markAsRead(notification.id);

    if (notification.actionView) {
      setActiveView?.(notification.actionView);
    }
  };

  return (
    <div className="notifications-page">

      {/* PAGE HEADER */}

      <div className="notifications-page-header">

        <div>
          <span className="notifications-kicker">
            NOTIFICATIONS
          </span>

          <h1>Notifications</h1>

          <p>
            Manage and review important alerts.
          </p>
        </div>

        <button
          className="mark-all-btn"
          onClick={markAllAsRead}
          disabled={unreadCount === 0}
        >
          ✓ Mark all as read
        </button>

      </div>


      {/* NOTIFICATION CARD */}

      <section className="notifications-container">

        {/* TABS */}

        <div className="notification-tabs">

          <button
            className={
              activeTab === "all"
                ? "active"
                : ""
            }
            onClick={() => setActiveTab("all")}
          >
            All
            <span>
              {notifications.length}
            </span>
          </button>

          <button
            className={
              activeTab === "system"
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab("system")
            }
          >
            System
          </button>

          <button
            className={
              activeTab === "mentions"
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab("mentions")
            }
          >
            Mentions
          </button>

          <button
            className={
              activeTab === "settings"
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab("settings")
            }
          >
            Settings
          </button>

        </div>


        {/* NOTIFICATION LIST */}

        <div className="notification-list">

          {filteredNotifications.length > 0 ? (

            filteredNotifications.map(
              (notification) => (

                <article
                  key={notification.id}
                  className={`notification-card ${
                    notification.unread
                      ? "unread"
                      : ""
                  }`}
                >

                  {/* ICON */}

                  <div
                    className={`notification-type-icon ${notification.type}`}
                  >
                    {notification.type ===
                      "warning" && "⚠"}

                    {notification.type ===
                      "success" && "⚙"}

                    {notification.type ===
                      "mention" && "♧"}

                    {notification.type ===
                      "info" && "✓"}
                  </div>


                  {/* CONTENT */}

                  <div className="notification-content">

                    <div className="notification-title-row">

                      <h3>
                        {notification.title}
                      </h3>

                      {notification.unread && (
                        <span className="unread-dot"></span>
                      )}

                    </div>

                    <p>
                      {notification.message}
                    </p>

                  </div>


                  {/* RIGHT SIDE */}

                  <div className="notification-actions">

                    <span className="notification-time">
                      {notification.time}
                    </span>

                    <button
                      className="notification-action-btn"
                      onClick={() =>
                        handleAction(
                          notification
                        )
                      }
                    >
                      {notification.action}
                      <span>↗</span>
                    </button>

                    <button
                      className="notification-delete"
                      title="Delete notification"
                      onClick={() =>
                        deleteNotification(
                          notification.id
                        )
                      }
                    >
                      ×
                    </button>

                  </div>

                </article>

              )
            )

          ) : (

            <div className="notifications-empty">

              <div className="empty-notification-icon">
                ✓
              </div>

              <h2>
                No notifications
              </h2>

              <p>
                You're all caught up. New
                alerts will appear here.
              </p>

            </div>

          )}

        </div>

      </section>


      {/* FOOTER INFO */}

      <div className="notification-security-note">

        <span>🔒</span>

        <div>
          <strong>
            Your notifications are private.
          </strong>

          <p>
            Alerts and activity updates are
            stored locally in your workspace.
          </p>
        </div>

      </div>

    </div>
  );
};

export default Notifications;