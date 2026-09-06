import { useState } from "react";
import "./AuthModern.css";

function FactCheckerLogo({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3L20 6V11C20 16.2 16.6 20.1 12 21C7.4 20.1 4 16.2 4 11V6L12 3Z" />
      <path d="M8.5 12L10.8 14.3L15.7 9.4" />
    </svg>
  );
}

function LoginPage({
  openDashboard,
  openSignup,
  backHome,
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  // ============================================
  // LOGIN
  // ============================================

  const handleSubmit = (event) => {
    event.preventDefault();
    setError("");

    if (!email.trim() || !password.trim()) {
      setError(
        "Please enter both email and password."
      );
      return;
    }

    if (openDashboard) {
      openDashboard();
    }
  };


  // ============================================
  // GUEST
  // ============================================

  const handleGuest = () => {
    if (openDashboard) {
      openDashboard();
    }
  };


  // ============================================
  // FORGOT PASSWORD
  // ============================================

  const handleForgotPassword = () => {
    alert(
      "Password recovery will be connected soon."
    );
  };


  // ============================================
  // CREATE ACCOUNT
  // ============================================

  const handleRegister = () => {
    setError("");

    if (openSignup) {
      openSignup();
    }
  };


  // ============================================
  // GOOGLE
  // ============================================

  const handleGoogleLogin = () => {
    alert(
      "Google sign-in will be connected soon."
    );
  };


  return (
    <main className="modern-auth-page">

      {/* =====================================================
          LEFT VISUAL SECTION
      ===================================================== */}

      <section className="modern-auth-visual">

        <img
          src="/src/assets/hero.png"
          alt="FactChecker AI technology"
          className="auth-hero-image"
        />

        <div className="auth-image-overlay"></div>

        {/* BACK BUTTON */}

        <button
          type="button"
          className="auth-back-button"
          onClick={backHome}
        >
          <span className="back-arrow">
            ←
          </span>

          Back to Home
        </button>


        <div className="auth-visual-content">

          {/* BRAND */}

          <div className="auth-visual-brand">

            <div className="auth-ai-icon">

              <FactCheckerLogo
                className="brand-shield-icon"
              />

            </div>

            <span>
              FactChecker
            </span>

          </div>


          {/* HERO TEXT */}

          <div className="auth-visual-text">

            <span className="auth-eyebrow">
              AI-POWERED FACT VERIFICATION
            </span>

            <h1>
              Detect.
              <br />
              Verify.
              <br />
              Understand.
            </h1>

            <p>
              Verify claims, detect misleading
              information, and discover trustworthy
              facts with intelligent AI-powered analysis.
            </p>


            {/* TRUST ITEMS */}

            <div className="auth-trust-row">

              <div className="auth-trust-item">

                <span className="trust-check">
                  ✓
                </span>

                <span>
                  Smart Analysis
                </span>

              </div>


              <div className="auth-trust-item">

                <span className="trust-check">
                  ✓
                </span>

                <span>
                  Reliable Results
                </span>

              </div>


              <div className="auth-trust-item">

                <span className="trust-check">
                  ✓
                </span>

                <span>
                  Fast Verification
                </span>

              </div>

            </div>

          </div>

        </div>


        {/* BACKGROUND GLOWS */}

        <div className="auth-glow glow-one"></div>

        <div className="auth-glow glow-two"></div>

        <div className="auth-grid-overlay"></div>

      </section>


      {/* =====================================================
          RIGHT LOGIN SECTION
      ===================================================== */}

      <section className="modern-auth-form-area">

        <div className="modern-auth-card">

          {/* BRAND */}

          <div className="modern-brand">

            <div className="modern-brand-icon">

              <FactCheckerLogo
                className="modern-shield-icon"
              />

            </div>

            <span className="modern-brand-name">
              FactChecker
            </span>

          </div>


          {/* HEADING */}

          <div className="modern-auth-heading">

            <span className="auth-welcome-badge">
              TRUSTED INFORMATION
            </span>

            <h2>
              Welcome back
            </h2>

            <p>
              Sign in to FactChecker and verify
              information with confidence.
            </p>

          </div>


          {/* =================================================
              LOGIN FORM
          ================================================= */}

          <form
            className="modern-auth-form"
            onSubmit={handleSubmit}
          >

            {/* EMAIL */}

            <div className="modern-form-group">

              <label htmlFor="login-email">
                Email Address
              </label>

              <div className="modern-input-wrapper">

                <span className="modern-input-icon">

                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  >
                    <rect
                      x="3"
                      y="5"
                      width="18"
                      height="14"
                      rx="2"
                    />

                    <path d="m3 7 9 6 9-6" />
                  </svg>

                </span>

                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    setError("");
                  }}
                />

              </div>

            </div>


            {/* PASSWORD */}

            <div className="modern-form-group">

              <div className="modern-password-heading">

                <label htmlFor="login-password">
                  Password
                </label>

                <button
                  type="button"
                  className="modern-forgot"
                  onClick={handleForgotPassword}
                >
                  Forgot Password?
                </button>

              </div>


              <div className="modern-input-wrapper">

                <span className="modern-input-icon">

                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  >
                    <rect
                      x="4"
                      y="10"
                      width="16"
                      height="11"
                      rx="2"
                    />

                    <path d="M8 10V7a4 4 0 0 1 8 0v3" />

                  </svg>

                </span>


                <input
                  id="login-password"
                  type={
                    showPassword
                      ? "text"
                      : "password"
                  }
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    setError("");
                  }}
                />


                <button
                  type="button"
                  className="modern-password-toggle"
                  onClick={() =>
                    setShowPassword(
                      (previous) => !previous
                    )
                  }
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >

                  {showPassword ? (

                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    >
                      <path d="M3 3l18 18" />

                      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />

                      <path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c5 0 8.5 4 10 8-.5 1.4-1.3 2.7-2.4 3.9" />

                      <path d="M6.6 6.6C4.8 7.8 3.6 9.5 2 12c1.5 4 5 8 10 8 1.6 0 3-.4 4.2-1" />

                    </svg>

                  ) : (

                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    >
                      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />

                      <circle
                        cx="12"
                        cy="12"
                        r="3"
                      />

                    </svg>

                  )}

                </button>

              </div>

            </div>


            {/* ERROR */}

            {error && (
              <div
                className="modern-login-error"
                role="alert"
              >

                <span className="error-icon">
                  !
                </span>

                <span>
                  {error}
                </span>

              </div>
            )}


            {/* LOGIN BUTTON */}

            <button
              type="submit"
              className="modern-login-button"
            >

              <span>
                Sign in to FactChecker
              </span>

              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>

            </button>

          </form>


          {/* =================================================
              DIVIDER
          ================================================= */}

          <div className="modern-divider">

            <span></span>

            <p>
              or continue with
            </p>

            <span></span>

          </div>


          {/* GOOGLE */}

          <button
            type="button"
            className="modern-google-button"
            onClick={handleGoogleLogin}
          >

            <span className="google-logo">
              G
            </span>

            <span>
              Continue with Google
            </span>

          </button>


          {/* GUEST */}

          <button
            type="button"
            className="modern-guest-button"
            onClick={handleGuest}
          >
            Continue as Guest
          </button>


          {/* REGISTER */}

          <p className="modern-switch-auth">

            Don't have an account?

            <button
              type="button"
              onClick={handleRegister}
            >
              Create Account
            </button>

          </p>


          {/* SECURITY NOTE */}

          <div className="auth-security-note">

            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            >

              <rect
                x="5"
                y="10"
                width="14"
                height="10"
                rx="2"
              />

              <path d="M8 10V7a4 4 0 0 1 8 0v3" />

              <circle
                cx="12"
                cy="15"
                r="1"
              />

            </svg>

            <span>
              Your information is protected and secure
            </span>

          </div>

        </div>

      </section>

    </main>
  );
}

export default LoginPage;