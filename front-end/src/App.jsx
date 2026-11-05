import { useState } from "react";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import FeaturesPage from "./pages/FeaturesPage";
import AboutPage from "./pages/AboutPage";
import LearnMorePage from "./pages/LearnMorePage";
import SignupPage from "./components/auth/Signup";

import AIScanIntro from "./components/Common/AIScanIntro";

import { AppProvider } from "./context/AppContext";
import { ThemeProvider } from "./context/ThemeContext";

function App() {
  /*
   * =========================================================
   * INTRO SESSION CONTROL
   * =========================================================
   *
   * First visit in a browser session:
   *     Show intro
   *
   * Internal navigation:
   *     Do NOT show intro again
   *
   * Refresh in the same browser session:
   *     Do NOT show intro again
   *
   * New browser session:
   *     Show intro again
   */

  const [showIntro, setShowIntro] = useState(() => {
    try {
      const introShown = sessionStorage.getItem(
        "factchecker_intro_shown"
      );

      return introShown !== "true";
    } catch {
      return true;
    }
  });

  /*
   * =========================================================
   * INTRO COMPLETE
   * =========================================================
   */

  const handleIntroComplete = () => {
    try {
      sessionStorage.setItem(
        "factchecker_intro_shown",
        "true"
      );
    } catch {
      // Ignore storage errors.
    }

    setShowIntro(false);
  };

  const [page, setPage] = useState("landing");

  /* ================= NAVIGATION ================= */

  const openDashboard = () => {
    const hasSession =
      localStorage.getItem("fc_token") ||
      localStorage.getItem("fc_guest_mode") === "true";

    if (!hasSession) {
      setPage("login");
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
      return;
    }

    setPage("dashboard");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openLoginForDashboard = () => {
    setPage("login");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openLogin = () => {
    setPage("login");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openSignup = () => {
    setPage("signup");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openFeatures = () => {
    setPage("features");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openAbout = () => {
    setPage("about");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openLearnMore = () => {
    setPage("learn-more");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const backHome = () => {
    setPage("landing");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  /* ================= APP ================= */

  return (
    <ThemeProvider>
      <AppProvider>

        {/* =================================================
            FACTCHECKER AI INTRO
            ================================================= */}

        {showIntro && (
          <AIScanIntro
            onComplete={handleIntroComplete}
          />
        )}

        {/* =================================================
            MAIN APPLICATION
            ================================================= */}

        {!showIntro && (
          <>

            {/* LANDING PAGE */}

            {page === "landing" && (
              <LandingPage
                openDashboard={openLoginForDashboard}
                openLogin={openLogin}
                openSignup={openSignup}
                openFeatures={openFeatures}
                openAbout={openAbout}
                openLearnMore={openLearnMore}
              />
            )}

            {/* LEARN MORE PAGE */}

            {page === "learn-more" && (
              <LearnMorePage
                openDashboard={openDashboard}
                openLogin={openLogin}
                openSignup={openSignup}
                openFeatures={openFeatures}
                openAbout={openAbout}
                backHome={backHome}
              />
            )}

            {/* FEATURES PAGE */}

            {page === "features" && (
              <FeaturesPage
                openDashboard={openDashboard}
                openLogin={openLogin}
                openSignup={openSignup}
                openAbout={openAbout}
                backHome={backHome}
              />
            )}

            {/* ABOUT PAGE */}

            {page === "about" && (
              <AboutPage
                openDashboard={openDashboard}
                openLogin={openLogin}
                openSignup={openSignup}
                openFeatures={openFeatures}
                backHome={backHome}
              />
            )}

            {/* LOGIN */}

            {page === "login" && (
              <LoginPage
                openDashboard={openDashboard}
                openSignup={openSignup}
                backHome={backHome}
              />
            )}

            {/* SIGNUP */}

            {page === "signup" && (
              <SignupPage
                onLogin={openLogin}
                openDashboard={openDashboard}
                backHome={backHome}
              />
            )}

            {/* DASHBOARD */}

            {page === "dashboard" && (
              <DashboardPage
                backHome={backHome}
              />
            )}

          </>
        )}

      </AppProvider>
    </ThemeProvider>
  );
}

export default App;