import { useContext, useMemo, useState } from "react";
import { AppContext } from "../../context/AppContext";
import { ThemeContext } from "../../context/ThemeContext";

const buildProfileFormData = (nextProfile) => ({
  name: nextProfile?.name || "Guest User",
  email: nextProfile?.email || "",
  role: nextProfile?.role || "Verifier",
  college: nextProfile?.college || "",
  course: nextProfile?.course || "",
  year: nextProfile?.year || "Not specified",
  about: nextProfile?.about || "",
  photo: nextProfile?.photo || "",
});

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

const animeLooks = [
  {
    hair: `<path d="M43 83c-9-42 10-66 39-66 34 0 47 28 35 68l-7 42H49z"/>`,
    fringe: `<path d="M48 69c0-31 16-48 38-48 21 0 35 17 31 44-13-3-23-12-28-25-10 15-24 24-41 29z"/>`,
    accessory: `<path d="m105 36 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1z" fill="#fff1a8" stroke="#f0a52e" stroke-width="2"/>`,
  },
  {
    hair: `<path d="M48 76c-8-30 4-56 32-59 32-4 46 21 36 55l-8 43H51z"/>`,
    fringe: `<path d="M45 69c1-35 15-52 37-52 22 0 37 18 34 47-8-8-14-17-17-27-13 13-31 21-54 24z"/>`,
    accessory: `<path d="M47 48c4-20 17-31 34-31 19 0 32 12 36 32-15-9-24-12-36-11-12 0-22 4-34 10z" fill="#67d5cf" stroke="#287f9b" stroke-width="3"/><path d="M72 20h19" stroke="#eaffff" stroke-width="4" stroke-linecap="round"/>`,
  },
  {
    hair: `<path d="M44 83c-9-36 4-64 36-66 34-2 47 26 36 66l-10 39H53z"/>`,
    fringe: `<path d="M47 67c-2-29 12-48 33-50 24-2 39 15 37 45-10-2-19-9-25-20-10 12-26 20-45 25z"/>`,
    accessory: `<circle cx="107" cy="70" r="10" fill="none" stroke="#f6d365" stroke-width="4"/><circle cx="107" cy="70" r="3" fill="#fff4b8"/>`,
  },
  {
    hair: `<path d="M48 78c-9-37 5-59 32-61 30-2 43 23 34 62l-8 42H53z"/><path d="M52 48C34 31 30 55 38 78l13 3zm54-3c20-17 24 7 16 31l-13 5z"/>`,
    fringe: `<path d="M47 67c-1-32 14-50 34-50 22 0 36 17 35 44-10-4-18-12-24-23-10 15-25 24-45 29z"/>`,
    accessory: `<path d="M41 78v-8a39 39 0 0 1 78 0v8" fill="none" stroke="#d58aff" stroke-width="7"/><rect x="36" y="70" width="12" height="22" rx="6" fill="#d58aff"/><rect x="112" y="70" width="12" height="22" rx="6" fill="#d58aff"/>`,
  },
  {
    hair: `<path d="M44 83c-8-39 7-64 37-66 32-2 46 24 36 66l-8 46H52z"/>`,
    fringe: `<path d="M47 68c0-34 14-51 35-51 22 0 36 17 34 45-11-2-20-11-25-24-11 16-26 24-44 30z"/>`,
    accessory: `<path d="M48 41c3-15 17-24 33-24 17 0 31 9 34 24z" fill="#ff9b72"/><path d="M45 42h73" stroke="#ffe2c9" stroke-width="5"/><circle cx="81" cy="27" r="5" fill="#fff0b0"/>`,
  },
  {
    hair: `<path d="M44 84c-9-41 8-66 37-67 34-1 48 28 36 69l-11 41H53z"/>`,
    fringe: `<path d="M47 68c1-33 14-50 35-50 24 0 37 19 33 46-13-4-22-12-28-24-10 15-23 24-40 28z"/>`,
    accessory: `<path d="M108 36a15 15 0 1 0 15 22 13 13 0 1 1-15-22z" fill="#fff2a8"/><circle cx="123" cy="43" r="2" fill="#fff"/>`,
  },
  {
    hair: `<path d="M47 79c-7-34 5-59 32-62 30-3 44 22 35 57l-7 47H52z"/>`,
    fringe: `<path d="M47 68c-1-33 14-51 34-51 23 0 37 19 33 46-10-2-20-10-26-23-10 14-23 23-41 28z"/>`,
    accessory: `<path d="M49 42 57 23 72 35 85 17 99 35 113 23 119 43c-20-7-49-7-70-1z" fill="#ffc85b" stroke="#b8772d" stroke-width="2"/>`,
  },
  {
    hair: `<path d="M44 82c-9-38 8-63 37-65 33-2 47 25 36 65l-10 44H52z"/><circle cx="51" cy="42" r="13"/><circle cx="68" cy="28" r="14"/><circle cx="89" cy="27" r="15"/><circle cx="108" cy="43" r="13"/>`,
    fringe: `<path d="M47 68c1-31 15-51 35-51 23 0 37 18 33 46-12-3-20-10-26-22-9 14-23 23-42 27z"/>`,
    accessory: `<circle cx="54" cy="58" r="7" fill="#ff8bc1"/><circle cx="54" cy="58" r="3" fill="#fff5a8"/>`,
  },
  {
    hair: `<path d="M43 83c-8-40 8-63 38-65 32-2 46 24 36 65l-8 46H51z"/>`,
    fringe: `<path d="M47 68c0-32 14-50 34-50 23 0 37 17 34 45-13-3-22-12-27-23-10 15-24 23-41 28z"/>`,
    accessory: `<rect x="56" y="78" width="20" height="13" rx="6" fill="none" stroke="#624f74" stroke-width="3"/><rect x="85" y="78" width="20" height="13" rx="6" fill="none" stroke="#624f74" stroke-width="3"/><path d="M76 84h9" stroke="#624f74" stroke-width="3"/>`,
  },
  {
    hair: `<path d="M43 84c-9-43 8-66 38-67 34-1 47 26 36 69l-9 42H50z"/>`,
    fringe: `<path d="M47 68c0-32 14-50 35-50 23 0 37 18 34 46-13-3-23-12-28-24-10 15-23 23-41 28z"/>`,
    accessory: `<path d="M105 44c15 2 19 13 13 25l-4 9h-8l5-12c3-8-1-13-9-14z" fill="#7be0cf"/><circle cx="106" cy="43" r="7" fill="#7be0cf"/>`,
  },
];

const createAvatarImage = (avatar) => {
  const { emoji, colors, category, name } = avatar;
  const [startColor, endColor] = colors;
  const avatarIndex = avatarLibrary.findIndex((item) => item.name === name);
  const skinColors = ["#f1c7a5", "#dca47f", "#f5d2b5", "#bd805f", "#e8b99a"];
  const hairColors = ["#35243d", "#513b72", "#754642", "#322f55", "#613b55", "#3b4e71", "#8a4c55", "#4b3b32", "#68413d", "#353b62"];
  const skin = skinColors[avatarIndex % skinColors.length];
  const hair = hairColors[avatarIndex % hairColors.length];
  const look = animeLooks[avatarIndex % animeLooks.length];
  const portrait =
    category === "Anime"
      ? `
        <path d="M31 160c4-30 20-43 49-43s45 13 49 43" fill="${startColor}"/>
        <path d="M68 111h24v30H68z" fill="${skin}"/>
        ${look.hair.replaceAll("/>", ` fill="${hair}"/>`)}
        <circle cx="48" cy="82" r="8" fill="${skin}"/>
        <circle cx="112" cy="82" r="8" fill="${skin}"/>
        <ellipse cx="80" cy="80" rx="31" ry="39" fill="${skin}"/>
        ${look.fringe.replace("/>", ` fill="${hair}"/>`)}
        <path d="M62 79c4-4 9-4 13 0m10 0c4-4 9-4 13 0" fill="none" stroke="#382a3d" stroke-width="3" stroke-linecap="round"/>
        <ellipse cx="69" cy="85" rx="3.3" ry="5" fill="#382a3d"/>
        <ellipse cx="92" cy="85" rx="3.3" ry="5" fill="#382a3d"/>
        <circle cx="70" cy="83" r="1.2" fill="#fff"/>
        <circle cx="93" cy="83" r="1.2" fill="#fff"/>
        <path d="M75 101c3 3 8 3 11 0" fill="none" stroke="#a85269" stroke-width="2.5" stroke-linecap="round"/>
        <ellipse cx="57" cy="96" rx="6" ry="3" fill="#ee8d91" fill-opacity=".45"/>
        <ellipse cx="103" cy="96" rx="6" ry="3" fill="#ee8d91" fill-opacity=".45"/>
        ${look.accessory}
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
        <radialGradient id="shine">
          <stop offset="0%" stop-color="#ffffff" stop-opacity=".45"/>
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="160" height="160" rx="80" fill="url(#background)"/>
      <circle cx="80" cy="80" r="67" fill="none" stroke="#ffffff" stroke-opacity=".46" stroke-width="2"/>
      <circle cx="80" cy="80" r="62" fill="url(#shine)"/>
      <path d="m28 47 3 7 7 3-7 3-3 7-3-7-7-3 7-3zm105 50 2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#fff" fill-opacity=".78"/>
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

  const [formData, setFormData] = useState(() => buildProfileFormData(profile));

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
      setFormData(buildProfileFormData(profile));
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
            onClick={() => {
              const nextEditing = !editing;
              setEditing(nextEditing);

              if (!nextEditing) {
                setFormData(buildProfileFormData(profile));
              }
            }}
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