/* ==========================================
        Local Storage Keys
========================================== */

const STORAGE_KEYS = {
  PROFILE: "fc_profile",
  HISTORY: "fc_history",
  THEME: "fc_theme",
};

/* ==========================================
        Save Data
========================================== */

export const saveProfile = (profile) => {
  localStorage.setItem(
    STORAGE_KEYS.PROFILE,
    JSON.stringify(profile)
  );
};

export const saveHistory = (history) => {
  localStorage.setItem(
    STORAGE_KEYS.HISTORY,
    JSON.stringify(history)
  );
};

export const saveTheme = (darkMode) => {
  localStorage.setItem(
    STORAGE_KEYS.THEME,
    JSON.stringify(darkMode)
  );
};

/* ==========================================
        Load Data
========================================== */

export const loadProfile = () => {
  const data = localStorage.getItem(
    STORAGE_KEYS.PROFILE
  );

  if (!data) return null;

  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
};

export const loadHistory = () => {
  const data = localStorage.getItem(
    STORAGE_KEYS.HISTORY
  );

  if (!data) return [];

  try {
    return JSON.parse(data);
  } catch {
    return [];
  }
};

export const loadTheme = () => {
  const data = localStorage.getItem(
    STORAGE_KEYS.THEME
  );

  if (!data) return false;

  try {
    return JSON.parse(data);
  } catch {
    return false;
  }
};

/* ==========================================
        Remove Data
========================================== */

export const removeProfile = () => {
  localStorage.removeItem(
    STORAGE_KEYS.PROFILE
  );
};

export const removeHistory = () => {
  localStorage.removeItem(
    STORAGE_KEYS.HISTORY
  );
};

export const removeTheme = () => {
  localStorage.removeItem(
    STORAGE_KEYS.THEME
  );
};

/* ==========================================
        Clear Application Data
========================================== */

export const clearAllStorage = () => {
  Object.values(STORAGE_KEYS).forEach((key) =>
    localStorage.removeItem(key)
  );
};

/* ==========================================
        Export History
========================================== */

export const exportHistoryFile = (
  history
) => {
  const blob = new Blob(
    [JSON.stringify(history, null, 2)],
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
    "factchecker-history.json";

  link.click();

  URL.revokeObjectURL(url);
};

/* ==========================================
        Export Settings
========================================== */

export const exportSettingsFile = (
  settings
) => {
  const blob = new Blob(
    [JSON.stringify(settings, null, 2)],
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