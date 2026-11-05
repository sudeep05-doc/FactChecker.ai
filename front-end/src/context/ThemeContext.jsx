/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useEffect,
  useState,
} from "react";

export const ThemeContext = createContext();

const getInitialTheme = () => {
  const savedTheme = localStorage.getItem("fc_theme");

  // Support old version where fc_theme was saved as true/false
  if (savedTheme === "true") return "dark";
  if (savedTheme === "false") return "light";

  if (
    savedTheme === "dark" ||
    savedTheme === "light" ||
    savedTheme === "system"
  ) {
    return savedTheme;
  }

  return "light";
};

export const ThemeProvider = ({ children }) => {
  const [theme, setThemeState] = useState(getInitialTheme);

  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia(
      "(prefers-color-scheme: dark)"
    );

    const applyTheme = () => {
      const systemDark = mediaQuery.matches;

      const shouldUseDark =
        theme === "dark" ||
        (theme === "system" && systemDark);

      setDarkMode(shouldUseDark);

      document.documentElement.setAttribute(
        "data-theme",
        shouldUseDark ? "dark" : "light"
      );

      document.body.classList.toggle(
        "dark-theme",
        shouldUseDark
      );

      document.body.classList.toggle(
        "dark",
        shouldUseDark
      );
    };

    applyTheme();

    mediaQuery.addEventListener(
      "change",
      applyTheme
    );

    return () => {
      mediaQuery.removeEventListener(
        "change",
        applyTheme
      );
    };
  }, [theme]);

  const setTheme = (newTheme) => {
    if (
      newTheme !== "light" &&
      newTheme !== "dark" &&
      newTheme !== "system"
    ) {
      return;
    }

    setThemeState(newTheme);

    localStorage.setItem(
      "fc_theme",
      newTheme
    );
  };

  const toggleTheme = () => {
    setThemeState((currentTheme) => {
      const nextTheme =
        currentTheme === "dark"
          ? "light"
          : "dark";

      localStorage.setItem(
        "fc_theme",
        nextTheme
      );

      return nextTheme;
    });
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        darkMode,
        setTheme,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};