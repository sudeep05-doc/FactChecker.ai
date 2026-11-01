import { useContext } from "react";
import { ThemeContext } from "../../context/ThemeContext";
import { AppContext } from "../../context/AppContext";

const Header = ({
  activeView,
  setActiveView,
  backHome,
}) => {

  const {
    darkMode,
    toggleTheme,
  } = useContext(ThemeContext);


  const {
    profile,
  } = useContext(AppContext);


  /* =====================================================
     PAGE TITLE
  ===================================================== */

  const getTitle = () => {

    switch (activeView) {

      case "overview":
        return "Dashboard";

      case "analyze":
        return "Analyze News";

      case "result":
        return "Verification Result";

      case "notifications":
        return "Notifications";

      case "history":
        return "History";

      case "saved":
        return "Saved Articles";

      case "trending":
        return "Trending News";

      case "statistics":
        return "Statistics";

      case "profile":
        return "Student Profile";

      case "settings":
        return "Settings";

      default:
        return "Dashboard";
    }
  };


  /* =====================================================
     INITIALS
  ===================================================== */

  const getInitials = (name) => {

    if (!name) {
      return "S";
    }

    const parts =
      name
        .trim()
        .split(" ")
        .filter(Boolean);


    return parts
      .map(
        (part) =>
          part.charAt(0)
      )
      .slice(0, 2)
      .join("")
      .toUpperCase();
  };


  /* =====================================================
     NAVIGATION
  ===================================================== */

  const handleNotificationClick = () => {

    setActiveView(
      "notifications"
    );
  };


  const handleAnalyzeClick = () => {

    setActiveView(
      "analyze"
    );
  };


  const handleProfileClick = () => {

    setActiveView(
      "profile"
    );
  };


  return (
    <header className="dashboard-header">


      {/* =================================================
          LEFT
      ================================================= */}

      <div className="header-left">

        <div className="header-title-area">

          <h1>
            {getTitle()}
          </h1>

          <p>
            Welcome back,{" "}
            <strong>
              {profile?.name ||
                "Student"}
            </strong>
          </p>

        </div>

      </div>


      {/* =================================================
          RIGHT
      ================================================= */}

      <div className="header-right">


        {/* =================================================
            DARK / LIGHT MODE
        ================================================= */}

        <button
          type="button"
          className="header-icon theme-toggle"
          onClick={toggleTheme}
          title={
            darkMode
              ? "Switch to Light Mode"
              : "Switch to Dark Mode"
          }
          aria-label="Toggle theme"
        >

          <span>
            {darkMode
              ? "☀"
              : "🌙"}
          </span>

        </button>


        {/* =================================================
            NOTIFICATION
        ================================================= */}

        <button
          type="button"
          className={`header-icon notification-button ${
            activeView ===
            "notifications"
              ? "notification-active"
              : ""
          }`}
          onClick={
            handleNotificationClick
          }
          title="Notifications"
          aria-label="Notifications"
        >

          <span className="notification-bell">
            🔔
          </span>


          <span className="notification-badge">
            3
          </span>

        </button>


        {/* =================================================
            ANALYZE
        ================================================= */}

        <button
          type="button"
          className="btn btn-primary header-analyze-btn"
          onClick={
            handleAnalyzeClick
          }
        >
          Analyze
        </button>


        {/* =================================================
            PROFILE
        ================================================= */}

        <button
          type="button"
          className="profile-chip"
          onClick={
            handleProfileClick
          }
          title="Student Profile"
        >

          {profile?.photo ? (

            <img
              src={profile.photo}
              alt={
                profile?.name ||
                "Student"
              }
              className="profile-image"
            />

          ) : (

            <div className="profile-avatar">

              {getInitials(
                profile?.name ||
                "Student"
              )}

            </div>

          )}


          <div className="profile-info">

            <strong>
              {profile?.name ||
                "Student"}
            </strong>

            <small>
              {profile?.role ||
                "Final Year Project"}
            </small>

          </div>

        </button>

      </div>

    </header>
  );
};


export default Header;