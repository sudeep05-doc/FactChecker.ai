import { useContext, useState } from "react";
import { ThemeContext } from "../../context/ThemeContext";

const Navbar = ({
  openDashboard,
  openLogin,
  openSignup,
  openFeatures,
  openAbout,
  openLearnMore,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);

  const { darkMode, toggleTheme } = useContext(ThemeContext);

  const closeMenu = () => {
    setMenuOpen(false);
  };

  const handleLogin = () => {
    closeMenu();
    if (openLogin) openLogin();
  };

  const handleSignup = () => {
    closeMenu();
    if (openSignup) openSignup();
  };

  const handleFeatures = () => {
    closeMenu();
    if (openFeatures) openFeatures();
  };

  const handleAbout = () => {
    closeMenu();
    if (openAbout) openAbout();
  };

  const handleLearnMore = () => {
    closeMenu();
    if (openLearnMore) openLearnMore();
  };

  const handleHome = () => {
    closeMenu();

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const scrollToSection = (id) => {
    closeMenu();

    const section = document.getElementById(id);

    if (section) {
      section.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  };

  return (
    <nav className="navbar container">

      {/* LOGO */}
      <button
        type="button"
        className="brand"
        onClick={handleHome}
        aria-label="FactChecker Home"
      >
        <span className="brand-mark fact-logo">
          ✓
        </span>

        <span className="brand-text">
          <b>
            Fact<em>Checker</em>
          </b>

          <small>
            Verify Before You Believe.
          </small>
        </span>
      </button>

      {/* NAVIGATION */}
      <div
        className={`nav-links ${menuOpen ? "open" : ""}`}
      >
        <button
          type="button"
          className="nav-page-link active"
          onClick={handleHome}
        >
          Home
        </button>

        <button
          type="button"
          className="nav-page-link"
          onClick={handleFeatures}
        >
          Features
        </button>

        <button
          type="button"
          className="nav-page-link"
          onClick={handleLearnMore}
        >
          How It Works
        </button>

        <button
          type="button"
          className="nav-page-link"
          onClick={handleAbout}
        >
          About Us
        </button>

        <button
          type="button"
          className="nav-page-link"
          onClick={() => scrollToSection("support")}
        >
          Support
        </button>

        <button
          type="button"
          className="nav-page-link"
          onClick={() => scrollToSection("pricing")}
        >
          Pricing
        </button>
      </div>

      {/* RIGHT ACTIONS */}
      <div className="nav-actions">

        {/* DARK / LIGHT MODE */}
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={
            darkMode
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
          title={
            darkMode
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
        >
          {darkMode ? "☀" : "◐"}
        </button>

        {/* LOGIN */}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleLogin}
        >
          Login
        </button>

        {/* SIGN UP */}
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleSignup}
        >
          Get Started
        </button>

      </div>

      {/* MOBILE MENU */}
      <button
        type="button"
        className="mobile-menu"
        onClick={() => setMenuOpen((prev) => !prev)}
        aria-label="Toggle navigation menu"
        aria-expanded={menuOpen}
      >
        {menuOpen ? "✕" : "☰"}
      </button>

    </nav>
  );
};

export default Navbar;