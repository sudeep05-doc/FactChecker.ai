import { useContext, useState } from "react";
import { ThemeContext } from "../../context/ThemeContext";
import { AppContext } from "../../context/AppContext";

const Toggle = ({
  checked,
  onChange,
}) => {
  return (
    <label className="truthlog-switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
      />
      <span></span>
    </label>
  );
};

const Settings = () => {

  const {
    darkMode,
    toggleTheme,
  } = useContext(ThemeContext);

  const {
    history,
    profile,
    setProfile,
    setHistory,
  } = useContext(AppContext);

  const [notifications, setNotifications] =
    useState(true);

  const [emailNotifications, setEmailNotifications] =
    useState(true);

  const [autoSave, setAutoSave] =
    useState(true);

  const [reduceMotion, setReduceMotion] =
    useState(false);

  const [confidenceAlerts, setConfidenceAlerts] =
    useState(true);

  const [savedMessage, setSavedMessage] =
    useState("");

  const showSavedMessage = () => {
    setSavedMessage(
      "Settings saved successfully."
    );

    setTimeout(() => {
      setSavedMessage("");
    }, 2500);
  };

  const exportSettings = () => {

    const data = {
      application: "FactChecker",
      theme: darkMode
        ? "dark"
        : "light",
      notifications,
      emailNotifications,
      autoSave,
      reduceMotion,
      confidenceAlerts,
      profile,
      totalHistory: history.length,
    };

    const blob = new Blob(
      [
        JSON.stringify(
          data,
          null,
          2
        ),
      ],
      {
        type: "application/json",
      }
    );

    const url =
      URL.createObjectURL(blob);

    const link =
      document.createElement("a");

    link.href = url;
    link.download =
      "factchecker-settings.json";

    link.click();

    URL.revokeObjectURL(url);
  };

  const clearHistory = () => {

    if (
      window.confirm(
        "Delete all verification history?"
      )
    ) {
      setHistory([]);

      showSavedMessage();
    }
  };

  const resetProfile = () => {

    if (
      window.confirm(
        "Reset your profile information?"
      )
    ) {
      setProfile({
        name: "Student",
        college: "",
        email: "",
        course: "",
        year: "Final Year",
        role: "Final Year Project",
        about: "",
        photo: "",
      });

      showSavedMessage();
    }
  };

  const resetAllData = () => {

    if (
      window.confirm(
        "This will delete all profile and verification data. Continue?"
      )
    ) {

      localStorage.removeItem(
        "fc_profile"
      );

      localStorage.removeItem(
        "fc_history"
      );

      setHistory([]);

      setProfile({
        name: "Student",
        college: "",
        email: "",
        course: "",
        year: "Final Year",
        role: "Final Year Project",
        about: "",
        photo: "",
      });

      showSavedMessage();
    }
  };

  return (
    <div className="truthlog-settings-page">

      {/* ==========================================
          HEADER
      ========================================== */}

      <div className="truthlog-settings-header">

        <div>
          <span className="settings-eyebrow">
            CONTROL CENTER
          </span>

          <h1>
            Settings
          </h1>

          <p>
            Manage your profile, preferences,
            notifications and application data.
          </p>
        </div>

        {savedMessage && (
          <div className="settings-saved-message">
            ✓ {savedMessage}
          </div>
        )}

      </div>

      {/* ==========================================
          PROFILE
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ◉
          </div>

          <div>
            <h2>
              Profile & Account
            </h2>

            <p>
              Manage your personal information
              and account details.
            </p>
          </div>

        </div>

        <div className="settings-profile-card">

          <div className="settings-profile-avatar">

            {profile?.photo ? (
              <img
                src={profile.photo}
                alt={profile.name}
              />
            ) : (
              <span>
                {profile?.name
                  ?.charAt(0)
                  ?.toUpperCase() || "S"}
              </span>
            )}

          </div>

          <div className="settings-profile-info">

            <h3>
              {profile?.name ||
                "Student"}
            </h3>

            <p>
              {profile?.email ||
                "No email added"}
            </p>

            <span>
              {profile?.role ||
                "Final Year Project"}
            </span>

          </div>

          <button
            className="settings-outline-button"
            onClick={resetProfile}
          >
            Reset Profile
          </button>

        </div>

      </section>

      {/* ==========================================
          APPEARANCE
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ◐
          </div>

          <div>
            <h2>
              Appearance
            </h2>

            <p>
              Choose how FactChecker looks
              on your device.
            </p>
          </div>

        </div>

        <div className="settings-option-card">

          <div className="settings-option-left">

            <div className="option-icon">
              {darkMode ? "☾" : "☀"}
            </div>

            <div>
              <h3>
                Dark Theme
              </h3>

              <p>
                Use the dark navy interface
                throughout the dashboard.
              </p>
            </div>

          </div>

          <Toggle
            checked={darkMode}
            onChange={toggleTheme}
          />

        </div>

      </section>

      {/* ==========================================
          NOTIFICATIONS
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ♧
          </div>

          <div>
            <h2>
              Notifications
            </h2>

            <p>
              Control alerts and verification
              notifications.
            </p>
          </div>

        </div>

        <div className="settings-options-card">

          <div className="settings-option-row">

            <div>
              <h3>
                Notifications
              </h3>

              <p>
                Receive important application
                notifications.
              </p>
            </div>

            <Toggle
              checked={notifications}
              onChange={() =>
                setNotifications(
                  (value) => !value
                )
              }
            />

          </div>

          <div className="settings-option-row">

            <div>
              <h3>
                Email Notifications
              </h3>

              <p>
                Receive verification updates
                by email.
              </p>
            </div>

            <Toggle
              checked={emailNotifications}
              onChange={() =>
                setEmailNotifications(
                  (value) => !value
                )
              }
            />

          </div>

          <div className="settings-option-row">

            <div>
              <h3>
                Confidence Alerts
              </h3>

              <p>
                Show alerts for low-confidence
                verification results.
              </p>
            </div>

            <Toggle
              checked={confidenceAlerts}
              onChange={() =>
                setConfidenceAlerts(
                  (value) => !value
                )
              }
            />

          </div>

        </div>

      </section>

      {/* ==========================================
          ANALYSIS PREFERENCES
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ◈
          </div>

          <div>
            <h2>
              Analysis Preferences
            </h2>

            <p>
              Configure how verification results
              are handled.
            </p>
          </div>

        </div>

        <div className="settings-options-card">

          <div className="settings-option-row">

            <div>
              <h3>
                Auto Save Results
              </h3>

              <p>
                Automatically save completed
                verification results to history.
              </p>
            </div>

            <Toggle
              checked={autoSave}
              onChange={() =>
                setAutoSave(
                  (value) => !value
                )
              }
            />

          </div>

          <div className="settings-option-row">

            <div>
              <h3>
                Reduce Motion
              </h3>

              <p>
                Minimize animations and
                interface transitions.
              </p>
            </div>

            <Toggle
              checked={reduceMotion}
              onChange={() =>
                setReduceMotion(
                  (value) => !value
                )
              }
            />

          </div>

        </div>

      </section>

      {/* ==========================================
          DATA MANAGEMENT
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ▣
          </div>

          <div>
            <h2>
              Data Management
            </h2>

            <p>
              Export, remove or reset your
              locally stored application data.
            </p>
          </div>

        </div>

        <div className="settings-data-grid">

          <div className="settings-data-card">

            <div className="data-card-icon">
              ↓
            </div>

            <div>
              <h3>
                Export Settings
              </h3>

              <p>
                Download your settings and
                profile as a JSON file.
              </p>
            </div>

            <button
              onClick={exportSettings}
            >
              Export
            </button>

          </div>

          <div className="settings-data-card">

            <div className="data-card-icon">
              ◫
            </div>

            <div>
              <h3>
                Clear History
              </h3>

              <p>
                Delete all verification
                history records.
              </p>
            </div>

            <button
              onClick={clearHistory}
              className="data-danger-button"
            >
              Clear
            </button>

          </div>

        </div>

      </section>

      {/* ==========================================
          APPLICATION INFORMATION
      ========================================== */}

      <section className="truthlog-settings-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon">
            ⓘ
          </div>

          <div>
            <h2>
              Application Information
            </h2>

            <p>
              Information about your
              FactChecker application.
            </p>
          </div>

        </div>

        <div className="settings-info-grid">

          <div>
            <span>
              Application
            </span>

            <strong>
              FactChecker
            </strong>
          </div>

          <div>
            <span>
              Version
            </span>

            <strong>
              v1.0.0
            </strong>
          </div>

          <div>
            <span>
              Framework
            </span>

            <strong>
              React + Vite
            </strong>
          </div>

          <div>
            <span>
              Verifications
            </span>

            <strong>
              {history.length}
            </strong>
          </div>

        </div>

      </section>

      {/* ==========================================
          DANGER ZONE
      ========================================== */}

      <section className="truthlog-settings-section settings-danger-section">

        <div className="settings-section-heading">

          <div className="settings-section-icon danger">
            !
          </div>

          <div>
            <h2>
              Danger Zone
            </h2>

            <p>
              These actions permanently remove
              locally stored application data.
            </p>
          </div>

        </div>

        <div className="settings-danger-card">

          <div>
            <h3>
              Reset Application Data
            </h3>

            <p>
              Delete your profile, history and
              local application information.
            </p>
          </div>

          <button
            onClick={resetAllData}
          >
            Reset Everything
          </button>

        </div>

      </section>

    </div>
  );
};

export default Settings;