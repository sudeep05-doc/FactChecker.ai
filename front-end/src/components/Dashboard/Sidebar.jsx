import { useState } from "react";

const Sidebar = ({
  activeView,
  setActiveView,
  backHome,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(
    () => window.innerWidth > 780
  );

  const menus = [
    {
      id: "overview",
      icon: "⌂",
      title: "Dashboard",
    },
    {
      id: "analyze",
      icon: "⌕",
      title: "Analyze News",
    },
    {
      id: "trending",
      icon: "↗",
      title: "Trending News",
    },
    {
      id: "history",
      icon: "◷",
      title: "History",
    },
    {
      id: "saved",
      icon: "♧",
      title: "Saved Articles",
    },
    {
      id: "statistics",
      icon: "▥",
      title: "Statistics",
    },
    {
      id: "profile",
      icon: "◉",
      title: "Student Profile",
    },
    {
  id: "feedback",
  icon: "♡",
  title: "Feedback",
},
    {
      id: "settings",
      icon: "⚙",
      title: "Settings",
    },
  ];

  const handleMenu = (view) => {
    setActiveView(view);

    if (window.innerWidth <= 780) {
      setSidebarOpen(false);
    }
  };

  return (
    <>
      {/* Mobile Overlay */}
      <div
        className={`sidebar-overlay ${
          sidebarOpen ? "open" : ""
        }`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside
        className={`sidebar ${
          sidebarOpen ? "open" : "collapsed"
        }`}
      >
        {/* Clean Purple Collapse / Expand Arrow */}
        <button
          type="button"
          className="sidebar-collapse-btn"
          onClick={() => setSidebarOpen((open) => !open)}
          title={
            sidebarOpen
              ? "Collapse sidebar"
              : "Expand sidebar"
          }
          aria-label={
            sidebarOpen
              ? "Collapse sidebar"
              : "Expand sidebar"
          }
        >
          <span aria-hidden="true">
            {sidebarOpen ? "‹" : "›"}
          </span>
        </button>

        {/* Logo */}
        <div className="sidebar-brand">
          <span className="brand-mark fact-logo">
            ✓
          </span>

          <span>
            <b>
              Fact<em>Checker</em>
            </b>

            <small>
              Verify Before You Believe.
            </small>
          </span>
        </div>

        {/* Illustration */}
        <div className="sidebar-visual">
          <div className="world-lines"></div>

          <span>▤</span>

          <b>⌕</b>

        </div>

        {/* Navigation */}
        <nav className="side-nav">
          {menus.map((menu) => (
            <button
              type="button"
              key={menu.id}
              className={`side-link ${
                activeView === menu.id
                  ? "active"
                  : ""
              }`}
              onClick={() => handleMenu(menu.id)}
            >
              <span>{menu.icon}</span>
              {menu.title}
            </button>
          ))}
        </nav>

        {/* Bottom */}
        <div className="side-bottom">
          <button
            type="button"
            className="side-link"
            onClick={backHome}
          >
            <span>←</span>
            Back To Home
          </button>

          <p>
            ◈ Your local data stays in your
            browser.
          </p>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;