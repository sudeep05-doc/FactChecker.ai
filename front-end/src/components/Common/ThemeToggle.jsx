import { useContext } from "react";
import { ThemeContext } from "../../context/ThemeContext";
import "./ThemeToggle.css";

function ThemeToggle({ className = "" }) {
  const { darkMode, toggleTheme } = useContext(ThemeContext);
  const label = darkMode ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      className={`site-theme-toggle ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={label}
      title={label}
    >
      <span aria-hidden="true">{darkMode ? "☀" : "◐"}</span>
    </button>
  );
}

export default ThemeToggle;
