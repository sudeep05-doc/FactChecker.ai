import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import { ThemeContext } from "../../context/ThemeContext";

const Profile = () => {
  const { profile, setProfile, history } = useContext(AppContext);
  const { theme, setTheme } = useContext(ThemeContext);

  const [editing, setEditing] = useState(false);

  const [formData, setFormData] = useState({
    name: profile?.name || "Student",
    email: profile?.email || "",
    role: profile?.role || "Verifier",
    college: profile?.college || "",
    course: profile?.course || "",
    year: profile?.year || "Final Year",
    about: profile?.about || "",
    photo: profile?.photo || "",
  });

  useEffect(() => {
  if (!profile) return;

  setFormData({
    name: profile.name || "Student",
    email: profile.email || "",
    role: profile.role || "Verifier",
    college: profile.college || "",
    course: profile.course || "",
    year: profile.year || "Final Year",
    about: profile.about || "",
    photo: profile.photo || "",
  });
}, [profile]);

  const initials = useMemo(() => {
    const name = formData.name?.trim();

    if (!name) return "ST";

    return name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0])
      .join("")
      .toUpperCase();
  }, [formData.name]);

  const verificationCount = history?.length || 0;

  const savedReports = Number(
    localStorage.getItem("fc_saved_reports_count") || 0
  );

  const downloadedReports = Number(
    localStorage.getItem("fc_downloaded_reports_count") || 0
  );

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handlePhoto = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please select an image file.");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert("Profile image must be smaller than 5 MB.");
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      setFormData((previous) => ({
        ...previous,
        photo: reader.result,
      }));
    };

    reader.readAsDataURL(file);
  };

  const saveProfile = async (event) => {
  event.preventDefault();

  try {
    const token = localStorage.getItem("fc_token");

    if (!token) {
      alert("Your session has expired. Please log in again.");
      return;
    }

    const response = await fetch(
      "http://localhost:5000/api/users/profile",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.message || "Failed to update profile."
      );
    }

    const updatedProfile = data.data;

    // Update React context
    setProfile(updatedProfile);

    // Keep the stored profile synchronized
    localStorage.setItem(
      "fc_profile",
      JSON.stringify(updatedProfile)
    );

    setEditing(false);

    alert("Profile updated successfully.");
  } catch (error) {
    console.error("Profile update error:", error);

    alert(
      error.message ||
        "Unable to update profile. Please try again."
    );
  }
};

  const openSetting = (setting) => {
    if (setting === "profile") {
      setEditing(true);
      return;
    }

    if (setting === "security") {
      alert("Security & Password settings will open here.");
      return;
    }

    if (setting === "notifications") {
      alert("Notification preferences will open here.");
      return;
    }

    if (setting === "billing") {
      alert("Billing & Plans will open here.");
      return;
    }

    if (setting === "integration") {
      alert("API and integration settings will open here.");
    }
  };

  const applyTheme = (selectedTheme) => {
    setTheme(selectedTheme);
  };

  return (
    <div className="verifact-profile-page">

      {/* ================================
          PROFILE HEADER
      ================================= */}

      <section className="profile-hero-card">

        <div className="profile-cover"></div>

        <div className="profile-main-info">

          <div className="profile-avatar-large">

            {formData.photo ? (
              <img
                src={formData.photo}
                alt="Profile"
              />
            ) : (
              <span>{initials}</span>
            )}

          </div>

          <div className="profile-user-details">

            <h1>
              {formData.name || "Student"}
            </h1>

            <p>
              {formData.email || "Add your email address"}
            </p>

            <span className="profile-role">
              {formData.role || "Verifier"}
            </span>

          </div>

          <button
            type="button"
            className="profile-edit-button"
            onClick={() => setEditing(!editing)}
          >
            ✎ {editing ? "Cancel" : "Edit Profile"}
          </button>

        </div>

      </section>

      {/* ================================
          EDIT PROFILE
      ================================= */}

      {editing && (
        <section className="profile-edit-panel">

          <div className="profile-section-title">
            <div>
              <h2>Edit Profile</h2>
              <p>
                Update your personal information and profile picture.
              </p>
            </div>
          </div>

          <form onSubmit={saveProfile}>

            <div className="profile-form-grid">

              <label>
                Full Name

                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="Your full name"
                />
              </label>

              <label>
                Email

                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="your@email.com"
                />
              </label>

              <label>
                Role

                <input
                  type="text"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                  placeholder="Verifier"
                />
              </label>

              <label>
                College / Organization

                <input
                  type="text"
                  name="college"
                  value={formData.college}
                  onChange={handleChange}
                  placeholder="College or organization"
                />
              </label>

              <label>
                Course

                <input
                  type="text"
                  name="course"
                  value={formData.course}
                  onChange={handleChange}
                  placeholder="Computer Science"
                />
              </label>

              <label>
                Year

                <select
                  name="year"
                  value={formData.year}
                  onChange={handleChange}
                >
                  <option>1st Year</option>
                  <option>2nd Year</option>
                  <option>3rd Year</option>
                  <option>Final Year</option>
                </select>
              </label>

            </div>

            <label className="profile-about-field">
              About

              <textarea
                name="about"
                rows="4"
                value={formData.about}
                onChange={handleChange}
                placeholder="Tell something about yourself..."
              />
            </label>

            <div className="profile-upload-row">

              <div>
                <strong>Profile Picture</strong>
                <p>PNG, JPG or WEBP. Maximum 5 MB.</p>
              </div>

              <label className="profile-upload-button">
                Upload Photo

                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handlePhoto}
                  hidden
                />
              </label>

            </div>

            <div className="profile-form-actions">

              <button
                type="submit"
                className="profile-save-button"
              >
                Save Changes
              </button>

              <button
                type="button"
                className="profile-cancel-button"
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>

            </div>

          </form>

        </section>
      )}

      {/* ================================
          VERIFICATION INSIGHTS
      ================================= */}

      <section className="profile-content-section">

        <div className="profile-section-heading">
          <h2>Verification Insights</h2>
        </div>

        <div className="verification-stats">

          <div className="verification-stat-card">

            <div className="verification-stat-icon">
              ✓
            </div>

            <div>
              <span>Verification Count</span>
              <strong>
                {verificationCount.toLocaleString()}
              </strong>
              <small>Total Verifications</small>
            </div>

          </div>

          <div className="verification-stat-card">

            <div className="verification-stat-icon">
              ♡
            </div>

            <div>
              <span>Saved Reports</span>
              <strong>
                {savedReports.toLocaleString()}
              </strong>
              <small>Saved Analyses</small>
            </div>

          </div>

          <div className="verification-stat-card">

            <div className="verification-stat-icon">
              ↓
            </div>

            <div>
              <span>Downloaded Reports</span>
              <strong>
                {downloadedReports.toLocaleString()}
              </strong>
              <small>Downloaded Reports</small>
            </div>

          </div>

        </div>

      </section>

      {/* ================================
          ACCOUNT SETTINGS
      ================================= */}

      <section className="profile-content-section">

        <div className="profile-section-heading">
          <h2>Account Settings</h2>
        </div>

        <div className="account-settings-card">

          <button
            type="button"
            className="account-setting-row"
            onClick={() => openSetting("profile")}
          >
            <span className="account-setting-icon">
              ♙
            </span>

            <span className="account-setting-text">
              <strong>Profile Details</strong>
              <small>
                Edit Personal Information & Role
              </small>
            </span>

            <span className="account-setting-arrow">
              ›
            </span>
          </button>

          <button
            type="button"
            className="account-setting-row"
            onClick={() => openSetting("security")}
          >
            <span className="account-setting-icon">
              ⚿
            </span>

            <span className="account-setting-text">
              <strong>Security & Password</strong>
              <small>
                Update Password, 2FA & Authenticator
              </small>
            </span>

            <span className="account-setting-arrow">
              ›
            </span>
          </button>

          <button
            type="button"
            className="account-setting-row"
            onClick={() => openSetting("notifications")}
          >
            <span className="account-setting-icon">
              ♧
            </span>

            <span className="account-setting-text">
              <strong>Notifications</strong>
              <small>
                Email & Push Notification Preferences
              </small>
            </span>

            <span className="account-setting-arrow">
              ›
            </span>
          </button>

          <button
            type="button"
            className="account-setting-row"
            onClick={() => openSetting("billing")}
          >
            <span className="account-setting-icon">
              ▣
            </span>

            <span className="account-setting-text">
              <strong>Billing & Plans</strong>
              <small>
                Subscription and Billing History
              </small>
            </span>

            <span className="account-setting-arrow">
              ›
            </span>
          </button>

          <button
            type="button"
            className="account-setting-row"
            onClick={() => openSetting("integration")}
          >
            <span className="account-setting-icon">
              ⊕
            </span>

            <span className="account-setting-text">
              <strong>App Integration</strong>
              <small>
                API Keys and Third-Party Tools
              </small>
            </span>

            <span className="account-setting-arrow">
              ›
            </span>
          </button>

        </div>

      </section>

      {/* ================================
          APPLICATION SETTINGS
      ================================= */}

      <section className="profile-content-section">

        <div className="profile-section-heading">
          <h2>Application Settings</h2>
        </div>

        <div className="application-settings-card">

          <div className="theme-setting">

            <div>
              <strong>Theme</strong>
              <small>
                Choose how Verifact AI looks
              </small>
            </div>

            <div className="theme-switcher">

              <button
                type="button"
                className={theme === "light" ? "active" : ""}
                onClick={() => applyTheme("light")}
              >
                Light
              </button>

              <button
                type="button"
                className={theme === "dark" ? "active" : ""}
                onClick={() => applyTheme("dark")}
              >
                Dark
              </button>

              <button
                type="button"
                className={theme === "system" ? "active" : ""}
                onClick={() => applyTheme("system")}
              >
                System
              </button>

            </div>

          </div>

        </div>

      </section>

      {/* ================================
          LOGOUT
      ================================= */}

      <section className="profile-content-section profile-logout-section">

        <div className="logout-card">

          <div>
            <strong>Logout</strong>
            <small>
              End your current dashboard session
            </small>
          </div>

          <button
            type="button"
            onClick={() => {
              localStorage.removeItem("fc_profile");
              window.location.reload();
            }}
          >
            Log Out
          </button>

        </div>

      </section>

    </div>
  );
};

export default Profile;