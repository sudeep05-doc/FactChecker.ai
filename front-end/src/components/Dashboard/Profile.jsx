import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import { ThemeContext } from "../../context/ThemeContext";

const avatarLibrary = [
  { name: "Anime Star", category: "Anime", emoji: "👩🏻‍🎤", colors: ["#ffd7e8", "#a9a7ff"] },
  { name: "Anime Hero", category: "Anime", emoji: "🧑🏻‍🚀", colors: ["#c9f0ff", "#8c9dff"] },
  { name: "Anime Artist", category: "Anime", emoji: "👩🏼‍🎨", colors: ["#ffe1c2", "#ff9fbd"] },
  { name: "Anime Musician", category: "Anime", emoji: "🧑🏽‍🎤", colors: ["#e6d3ff", "#ff9fc4"] },
  { name: "Anime Reader", category: "Anime", emoji: "👩🏽‍🎓", colors: ["#c7f5e8", "#93bdff"] },
  { name: "Anime Explorer", category: "Anime", emoji: "🧑🏼‍🚀", colors: ["#d8e9ff", "#c79cff"] },
  { name: "Anime Dreamer", category: "Anime", emoji: "👧🏻", colors: ["#ffe0ed", "#ffb27b"] },
  { name: "Anime Friend", category: "Anime", emoji: "👦🏽", colors: ["#c8f2ff", "#a4d893"] },
  { name: "Anime Creator", category: "Anime", emoji: "👩🏾‍🎨", colors: ["#ffe7ba", "#f7a2a2"] },
  { name: "Anime Pilot", category: "Anime", emoji: "🧑🏾‍🚀", colors: ["#d8d5ff", "#8dd8d0"] },
  { name: "Happy Cat", category: "Animals", emoji: "🐱", colors: ["#ffe4b5", "#ffad9e"] },
  { name: "Puppy Pal", category: "Animals", emoji: "🐶", colors: ["#d9f3c2", "#8ed9c3"] },
  { name: "Little Fox", category: "Animals", emoji: "🦊", colors: ["#ffdfb8", "#ffa76d"] },
  { name: "Panda Bear", category: "Animals", emoji: "🐼", colors: ["#e1e9f5", "#aec6e8"] },
  { name: "Koala Cub", category: "Animals", emoji: "🐨", colors: ["#e5e0ff", "#b3c6ff"] },
  { name: "Tiger Buddy", category: "Animals", emoji: "🐯", colors: ["#ffe7a8", "#ffac74"] },
  { name: "Lion Cub", category: "Animals", emoji: "🦁", colors: ["#ffe8a6", "#ffc16f"] },
  { name: "Frog Friend", category: "Animals", emoji: "🐸", colors: ["#c9f7bd", "#7ed7a2"] },
  { name: "Bunny", category: "Animals", emoji: "🐰", colors: ["#ffe3ef", "#d4b8ff"] },
  { name: "Penguin", category: "Animals", emoji: "🐧", colors: ["#c7edff", "#a5baff"] },
  { name: "Space Buddy", category: "Cartoon", emoji: "👽", colors: ["#ceffd5", "#7ddbb7"] },
  { name: "Robot Pal", category: "Cartoon", emoji: "🤖", colors: ["#d5e7ff", "#98bbf5"] },
  { name: "Magic Unicorn", category: "Cartoon", emoji: "🦄", colors: ["#f5d6ff", "#ffaed7"] },
  { name: "Friendly Ghost", category: "Cartoon", emoji: "👻", colors: ["#e5eaff", "#b7c8ff"] },
  { name: "Little Wizard", category: "Cartoon", emoji: "🧙", colors: ["#dfd5ff", "#9aa7ff"] },
  { name: "Fairy Friend", category: "Cartoon", emoji: "🧚", colors: ["#d5ffe8", "#94dfc2"] },
  { name: "Superhero", category: "Cartoon", emoji: "🦸", colors: ["#ffd6d6", "#ff9b9b"] },
  { name: "Sea Mermaid", category: "Cartoon", emoji: "🧜", colors: ["#c7f5ff", "#a6b5ff"] },
  { name: "Cool Monster", category: "Cartoon", emoji: "👾", colors: ["#e2d4ff", "#9a86ff"] },
  { name: "Tiny Dragon", category: "Cartoon", emoji: "🐲", colors: ["#d2f5c2", "#8bd6a4"] },
  { name: "Cyber Ninja", category: "Cool", emoji: "🥷", colors: ["#2b2d42", "#7b2cbf"] },
  { name: "Neon Gamer", category: "Cool", emoji: "🎮", colors: ["#14213d", "#00b4d8"] },
  { name: "Skater Style", category: "Cool", emoji: "🛹", colors: ["#ff6b35", "#ffd166"] },
  { name: "DJ Beats", category: "Cool", emoji: "🎧", colors: ["#240046", "#e0aaff"] },
  { name: "Cyber Fox", category: "Cool", emoji: "🦊", colors: ["#3a0ca3", "#f72585"] },
  { name: "Shadow Wolf", category: "Cool", emoji: "🐺", colors: ["#14213d", "#4361ee"] },
  { name: "Shark Wave", category: "Cool", emoji: "🦈", colors: ["#0077b6", "#48cae4"] },
  { name: "Street Artist", category: "Cool", emoji: "🎨", colors: ["#ff006e", "#8338ec"] },
  { name: "Space Ranger", category: "Cool", emoji: "🚀", colors: ["#03045e", "#00b4d8"] },
  { name: "Flame Dragon", category: "Cool", emoji: "🐉", colors: ["#9d0208", "#ffba08"] },
];

const avatarCategories = ["All", "Anime", "Animals", "Cartoon", "Cool"];

const createAvatarImage = ({ emoji, colors }) => {
  const [startColor, endColor] = colors;
  const avatarIndex = avatarLibrary.findIndex(
    (avatar) => avatar.emoji === emoji && avatar.colors === colors
  );
  const hairColors = [
    "#35243d",
    "#513b72",
    "#754642",
    "#322f55",
    "#613b55",
    "#3b4e71",
    "#8a4c55",
    "#4b3b32",
    "#68413d",
    "#353b62",
  ];
  const skinColors = [
    "#f1c7a5",
    "#dca47f",
    "#f5d2b5",
    "#bd805f",
    "#e8b99a",
  ];
  const portrait =
    avatarLibrary[avatarIndex]?.category === "Anime"
      ? `
        <path d="M36 160c3-24 18-38 44-38s41 14 44 38" fill="${startColor}"/>
        <path d="M68 110h24v30H68z" fill="${skinColors[avatarIndex % skinColors.length]}"/>
        <path d="M45 77c-5-35 8-57 35-60 33-4 43 21 37 62l-10 34H50z" fill="${hairColors[avatarIndex % hairColors.length]}"/>
        <circle cx="48" cy="82" r="7" fill="${skinColors[avatarIndex % skinColors.length]}"/>
        <circle cx="112" cy="82" r="7" fill="${skinColors[avatarIndex % skinColors.length]}"/>
        <ellipse cx="80" cy="80" rx="31" ry="39" fill="${skinColors[avatarIndex % skinColors.length]}"/>
        <path d="M49 69c1-29 16-45 34-45 21 0 34 15 31 43-10-4-18-12-23-23-9 13-23 21-42 25z" fill="${hairColors[avatarIndex % hairColors.length]}"/>
        <path d="M64 82c4-4 9-4 13 0m7 0c4-4 9-4 13 0" fill="none" stroke="#382a3d" stroke-width="3" stroke-linecap="round"/>
        <circle cx="70" cy="85" r="2" fill="#382a3d"/>
        <circle cx="91" cy="85" r="2" fill="#382a3d"/>
        <path d="M74 101c4 4 9 4 13 0" fill="none" stroke="#a85269" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="59" cy="96" r="4" fill="#ee8d91" fill-opacity=".4"/>
        <circle cx="101" cy="96" r="4" fill="#ee8d91" fill-opacity=".4"/>
      `
      : `<text x="80" y="103" text-anchor="middle" font-size="82"
          font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">${emoji}</text>`;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <defs>
        <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="${startColor}"/>
          <stop offset="100%" stop-color="${endColor}"/>
        </linearGradient>
      </defs>
      <rect width="160" height="160" rx="80" fill="url(#background)"/>
      <circle cx="80" cy="80" r="67" fill="#ffffff" fill-opacity=".24"/>
      ${portrait}
    </svg>`;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

const Profile = () => {
  const { profile, setProfile, history } = useContext(AppContext);
  const { theme, setTheme } = useContext(ThemeContext);

  const [editing, setEditing] = useState(false);
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);
  const [avatarSection, setAvatarSection] = useState("Your Gallery");
  const [avatarCategory, setAvatarCategory] = useState("All");

  const [formData, setFormData] = useState({
    name: profile?.name || "Guest User",
    email: profile?.email || "",
    role: profile?.role || "Verifier",
    college: profile?.college || "",
    course: profile?.course || "",
    year: profile?.year || "Not specified",
    about: profile?.about || "",
    photo: profile?.photo || "",
  });

  useEffect(() => {
  if (!profile || editing) return;

  setFormData({
    name: profile.name || "Guest User",
    email: profile.email || "",
    role: profile.role || "Verifier",
    college: profile.college || "",
    course: profile.course || "",
    year: profile.year || "Not specified",
    about: profile.about || "",
    photo: profile.photo || "",
  });
}, [profile, editing]);

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
    event.target.value = "";

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
      updateProfilePhoto(reader.result);
      setAvatarPickerOpen(false);
    };

    reader.onerror = () => {
      alert("Unable to read this image. Please try another file.");
    };

    reader.readAsDataURL(file);
  };

  const updateProfilePhoto = (photo) => {
    setFormData((previous) => ({
      ...previous,
      photo,
    }));

    const updatedProfile = {
      ...profile,
      photo,
    };

    setProfile(updatedProfile);
    localStorage.setItem(
      "fc_profile",
      JSON.stringify(updatedProfile)
    );
  };

  const visibleAvatars =
    avatarCategory === "All"
      ? avatarLibrary
      : avatarLibrary.filter(
          (avatar) => avatar.category === avatarCategory
        );

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

            <button
              type="button"
              className="profile-avatar-camera"
              aria-label="Change profile picture"
              title="Change profile picture"
              onClick={() => setAvatarPickerOpen(true)}
            >
              <svg
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <path d="M8.2 5.5 9.4 4h5.2l1.2 1.5H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-10a2 2 0 0 1 2-2h3.2Z" />
                <circle cx="12" cy="12.5" r="3.5" />
              </svg>
            </button>

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

      {avatarPickerOpen && (
        <div
          className="profile-avatar-picker-overlay"
          onClick={() => setAvatarPickerOpen(false)}
        >
          <section
            className="profile-avatar-picker"
            role="dialog"
            aria-modal="true"
            aria-labelledby="avatar-picker-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="profile-avatar-picker-header">
              <div>
                <h2 id="avatar-picker-title">Choose a profile picture</h2>
                <p>Pick an image from your device or choose an avatar.</p>
              </div>
              <button
                type="button"
                className="profile-avatar-picker-close"
                aria-label="Close avatar picker"
                onClick={() => setAvatarPickerOpen(false)}
              >
                ×
              </button>
            </header>

            <div className="profile-avatar-picker-tabs" role="tablist">
              {["Your Gallery", "Avatar Library"].map((section) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={avatarSection === section}
                  className={avatarSection === section ? "active" : ""}
                  key={section}
                  onClick={() => setAvatarSection(section)}
                >
                  {section}
                </button>
              ))}
            </div>

            {avatarSection === "Your Gallery" ? (
              <div className="profile-user-gallery">
                <div className="profile-gallery-preview">
                  {formData.photo ? (
                    <img src={formData.photo} alt="Current profile" />
                  ) : (
                    <span>{initials}</span>
                  )}
                </div>
                <h3>Upload from your gallery</h3>
                <p>Select a profile picture saved on your device.</p>
                <label className="profile-gallery-upload">
                  <span aria-hidden="true">↑</span>
                  Choose image
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handlePhoto}
                    hidden
                  />
                </label>
                <small>JPG, PNG, WEBP or another image format · up to 5 MB</small>
              </div>
            ) : (
              <div className="profile-avatar-library">
                <div className="profile-avatar-categories">
                  {avatarCategories.map((category) => (
                    <button
                      type="button"
                      key={category}
                      className={avatarCategory === category ? "active" : ""}
                      onClick={() => setAvatarCategory(category)}
                    >
                      {category}
                    </button>
                  ))}
                </div>
                <div className="profile-avatar-grid">
                  {visibleAvatars.map((avatar) => {
                    const avatarImage = createAvatarImage(avatar);

                    return (
                      <button
                        type="button"
                        className="profile-avatar-option"
                        key={avatar.name}
                        aria-label={`Choose ${avatar.name} avatar`}
                        title={avatar.name}
                        onClick={() => {
                          updateProfilePhoto(avatarImage);
                          setAvatarPickerOpen(false);
                        }}
                      >
                        <img src={avatarImage} alt="" />
                        <span>{avatar.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        </div>
      )}

    </div>
  );
};

export default Profile;