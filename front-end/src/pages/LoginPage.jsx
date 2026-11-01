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
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [forgotMode, setForgotMode] = useState(false);
  const [forgotStep, setForgotStep] = useState(1);
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetOTP, setResetOTP] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [forgotMessage, setForgotMessage] = useState("");
  const [forgotLoading, setForgotLoading] = useState(false);

  // ============================================
  // LOGIN
  // ============================================

  const handleSubmit = async (event) => {
  event.preventDefault();
  setError("");

  if (!email.trim() || !password.trim()) {
    setError("Please enter both email and password.");
    return;
  }

  try {
    const response = await fetch(
      "http://localhost:5000/api/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      }
    );

    const data = await response.json();

    // Backend rejected the login
    if (!response.ok) {
      throw new Error(
        data.message || "Invalid email or password."
      );
    }

    // Login was successful
    localStorage.setItem(
      "fc_token",
      data.data.token
    );

    localStorage.setItem(
      "fc_current_user",
      JSON.stringify(data.data.user)
    );

    localStorage.setItem(
      "fc_profile",
      JSON.stringify(data.data.profile)
    );

    localStorage.removeItem("fc_guest_mode");

    console.log(
      "Login successful:",
      data.data.user
    );

    // ONLY successful login reaches dashboard
    if (openDashboard) {
      openDashboard();
    }
  } catch (err) {
    console.error("Login error:", err);

    setError(
      err.message ||
        "Unable to login. Please try again."
    );
  }
};


  // ============================================
  // GUEST
  // ============================================

  const handleGuest = () => {
    // Clear any previous guest session information.
    localStorage.removeItem("fc_token");
    localStorage.removeItem("fc_current_user");

    // Activate guest mode.
    localStorage.setItem("fc_guest_mode", "true");

    // Set a default guest profile.
    const guestProfile = {
      name: "Guest User",
      email: "",
      role: "Guest",
      college: "",
      course: "",
      year: "Not specified",
      about: "",
      photo: "",
    };

    localStorage.setItem(
      "fc_profile",
      JSON.stringify(guestProfile)
    );

    // Open dashboard.
    if (openDashboard) {
      openDashboard();
    }
  };


  // ============================================
  // FORGOT PASSWORD
  // ============================================

  const handleForgotPassword = () => {
  setError("");
  setForgotMessage("");
  setForgotEmail(email);
  setForgotStep(1);
  setForgotMode(true);
};
const handleSendOTP = async (event) => {
  event.preventDefault();

  setError("");
  setForgotMessage("");

  if (!forgotEmail.trim()) {
    setError("Please enter your email address.");
    return;
  }

  setForgotLoading(true);

  try {
    const response = await fetch(
      "http://localhost:5000/api/auth/forgot-password",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: forgotEmail.trim().toLowerCase(),
        }),
      }
    );

    // Get the raw response first
    const rawText = await response.text();

    console.log("Forgot password HTTP status:", response.status);
    console.log("Forgot password raw response:", rawText);

    let data;

    try {
      data = JSON.parse(rawText);
    } catch {
      throw new Error(
        `Backend returned invalid response (${response.status}): ${rawText}`
      );
    }

    console.log("Forgot password parsed response:", data);

    if (!response.ok) {
      throw new Error(
        data.message ||
        data.error ||
        data?.data?.message ||
        `Request failed with status ${response.status}`
      );
    }

    setForgotMessage(
      data.message ||
      "OTP sent successfully. Please check your email."
    );

    setForgotStep(2);

  } catch (err) {
    console.error("FORGOT PASSWORD ERROR:", err);

    setError(
      err.message ||
      "Unable to send OTP."
    );

  } finally {
    setForgotLoading(false);
  }
};


const handleVerifyOTP = async (event) => {
  event.preventDefault();

  setError("");
  setForgotMessage("");

  if (!resetOTP.trim()) {
    setError("Please enter the OTP.");
    return;
  }

  setForgotLoading(true);

  try {
    const response = await fetch(
      "http://localhost:5000/api/auth/verify-reset-otp",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: forgotEmail.trim().toLowerCase(),
          otp: resetOTP.trim(),
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.message || "Invalid OTP."
      );
    }

    setForgotMessage(
      "OTP verified successfully."
    );

    setForgotStep(3);
  } catch (err) {
    console.error("OTP verification error:", err);

    setError(
      err.message ||
        "Invalid OTP. Please try again."
    );
  } finally {
    setForgotLoading(false);
  }
};


const handleResetPassword = async (event) => {
  event.preventDefault();

  setError("");
  setForgotMessage("");

  if (!newPassword || !confirmPassword) {
    setError("Please enter and confirm your new password.");
    return;
  }

  if (newPassword !== confirmPassword) {
    setError("Passwords do not match.");
    return;
  }

  if (newPassword.length < 8) {
    setError(
      "Password must contain at least 8 characters."
    );
    return;
  }

  if (!/[A-Z]/.test(newPassword)) {
    setError(
      "Password must contain at least one uppercase letter."
    );
    return;
  }

  if (!/[0-9]/.test(newPassword)) {
    setError(
      "Password must contain at least one number."
    );
    return;
  }

  if (!/[^A-Za-z0-9]/.test(newPassword)) {
    setError(
      "Password must contain at least one special character."
    );
    return;
  }

  setForgotLoading(true);

  try {
    const response = await fetch(
      "http://localhost:5000/api/auth/reset-password",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: forgotEmail.trim().toLowerCase(),
          otp: resetOTP.trim(),
          newPassword,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.message || "Unable to reset password."
      );
    }

    setForgotMessage(
      "Password reset successfully. You can now log in."
    );

    setForgotMode(false);
    setForgotStep(1);
    setPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setResetOTP("");
  } catch (err) {
    console.error("Password reset error:", err);

    setError(
      err.message ||
        "Unable to reset password. Please try again."
    );
  } finally {
    setForgotLoading(false);
  }
};


const handleBackToLogin = () => {
  setForgotMode(false);
  setForgotStep(1);
  setForgotMessage("");
  setError("");
  setResetOTP("");
  setNewPassword("");
  setConfirmPassword("");
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


  {/* =================================================
      FORGOT PASSWORD FLOW
  ================================================= */}

  {forgotMode ? (

    <>
      <div className="modern-auth-heading">

        <span className="auth-welcome-badge">
          PASSWORD RECOVERY
        </span>

        <h2>
          {forgotStep === 1 && "Forgot Password?"}
          {forgotStep === 2 && "Verify OTP"}
          {forgotStep === 3 && "Create New Password"}
        </h2>

        <p>
          {forgotStep === 1 &&
            "Enter your email address and we'll send you a verification code."}

          {forgotStep === 2 &&
            "Enter the 6-digit OTP sent to your email address."}

          {forgotStep === 3 &&
            "Create a new secure password for your FactChecker account."}
        </p>

      </div>


      {/* =================================================
          STEP 1 — EMAIL
      ================================================= */}

      {forgotStep === 1 && (

        <form
          className="modern-auth-form"
          onSubmit={handleSendOTP}
        >

          <div className="modern-form-group">

            <label htmlFor="forgot-email">
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
                id="forgot-email"
                type="email"
                autoComplete="email"
                placeholder="Enter your email address"
                value={forgotEmail}
                onChange={(event) => {
                  setForgotEmail(event.target.value);
                  setError("");
                }}
              />

            </div>

          </div>


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


          {forgotMessage && (
            <div className="modern-success-message">
              {forgotMessage}
            </div>
          )}


          <button
            type="submit"
            className="modern-login-button"
            disabled={forgotLoading}
          >

            <span>
              {forgotLoading
                ? "Sending OTP..."
                : "Send OTP"}
            </span>

            {!forgotLoading && (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            )}

          </button>

        </form>
      )}


      {/* =================================================
          STEP 2 — OTP
      ================================================= */}

      {forgotStep === 2 && (

        <form
          className="modern-auth-form"
          onSubmit={handleVerifyOTP}
        >

          <div className="modern-form-group">

            <label htmlFor="reset-otp">
              Verification Code
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

                  <path d="M7 9h10" />
                  <path d="M7 13h6" />

                </svg>

              </span>

              <input
                id="reset-otp"
                type="text"
                inputMode="numeric"
                maxLength="6"
                placeholder="Enter 6-digit OTP"
                value={resetOTP}
                onChange={(event) => {
                  const value =
                    event.target.value
                      .replace(/\D/g, "")
                      .slice(0, 6);

                  setResetOTP(value);
                  setError("");
                }}
              />

            </div>

          </div>


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


          {forgotMessage && (
            <div className="modern-success-message">
              {forgotMessage}
            </div>
          )}


          <button
            type="submit"
            className="modern-login-button"
            disabled={forgotLoading}
          >

            <span>
              {forgotLoading
                ? "Verifying..."
                : "Verify OTP"}
            </span>

            {!forgotLoading && (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            )}

          </button>

        </form>
      )}


      {/* =================================================
          STEP 3 — NEW PASSWORD
      ================================================= */}

      {forgotStep === 3 && (

        <form
          className="modern-auth-form"
          onSubmit={handleResetPassword}
        >

          {/* NEW PASSWORD */}

          <div className="modern-form-group">

            <label htmlFor="new-password">
              New Password
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
                id="new-password"
                type="password"
                autoComplete="new-password"
                placeholder="Enter new password"
                value={newPassword}
                onChange={(event) => {
                  setNewPassword(event.target.value);
                  setError("");
                }}
              />

            </div>

          </div>


          {/* CONFIRM PASSWORD */}

          <div className="modern-form-group">

            <label htmlFor="confirm-password">
              Confirm New Password
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
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                placeholder="Confirm your new password"
                value={confirmPassword}
                onChange={(event) => {
                  setConfirmPassword(event.target.value);
                  setError("");
                }}
              />

            </div>

          </div>


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


          <button
            type="submit"
            className="modern-login-button"
            disabled={forgotLoading}
          >

            <span>
              {forgotLoading
                ? "Resetting Password..."
                : "Reset Password"}
            </span>

            {!forgotLoading && (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            )}

          </button>

        </form>
      )}


      {/* BACK TO LOGIN */}

      <button
        type="button"
        className="modern-guest-button"
        onClick={handleBackToLogin}
      >
        ← Back to Login
      </button>

    </>

  ) : (

    /* =================================================
       NORMAL LOGIN
    ================================================= */

    <>

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


      {/* LOGIN FORM */}

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


      {/* DIVIDER */}

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

    </>

  )}

</div>

      </section>

    </main>
  );
}

export default LoginPage;