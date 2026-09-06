import { useMemo, useState } from "react";
import "./Signup.css";

const USERS_KEY = "fc_users";

function ShieldIcon({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3L20 6V11C20 16.2 16.6 20.1 12 21C7.4 20.1 4 16.2 4 11V6L12 3Z" />
      <path d="M8.5 12L10.8 14.3L15.7 9.4" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.8-3.5 3.2-5.5 7-5.5s6.2 2 7 5.5" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M6.7 3.5h2.5l1.2 4-1.9 1.6c1 2.2 2.7 4 4.9 5l1.6-1.9 4 1.2v2.5c0 1-.8 1.8-1.8 1.8C10.1 17.7 6.3 13.9 6.3 8.8c0-1 .8-1.8 1.8-1.8" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function EyeIcon({ hidden = false }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
      <path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c5 0 8.5 4 10 8-1 2.6-2.5 4.7-4.6 6.1" />
      <path d="M6.6 6.6C4.8 7.8 3.6 9.5 2 12c1.5 4 5 8 10 8 1.6 0 3-.4 4.2-1" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function SignupPage({ onLogin, openDashboard, backHome }) {
  const [form, setForm] = useState({
    fullName: "",
    username: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));

    setError("");
  };

  const passwordStrength = useMemo(() => {
    const password = form.password;

    if (!password) {
      return {
        score: 0,
        label: "",
      };
    }

    let score = 0;

    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    const labels = ["", "Weak", "Fair", "Good", "Strong"];

    return {
      score,
      label: labels[score],
    };
  }, [form.password]);

  const validate = () => {
    if (!form.fullName.trim()) {
      return "Please enter your full name.";
    }

    if (!form.username.trim()) {
      return "Please choose a username.";
    }

    if (!/^[a-zA-Z0-9_.-]{3,20}$/.test(form.username)) {
      return "Username must be 3–20 characters.";
    }

    if (!form.email.trim()) {
      return "Please enter your email address.";
    }

    if (!/^\S+@\S+\.\S+$/.test(form.email)) {
      return "Please enter a valid email address.";
    }

    if (form.password.length < 8) {
      return "Password must contain at least 8 characters.";
    }

    if (passwordStrength.score < 3) {
      return "Use uppercase letters, numbers and symbols.";
    }

    if (form.password !== form.confirmPassword) {
      return "Passwords do not match.";
    }

    if (!agreeTerms) {
      return "Please agree to the Terms and Privacy Policy.";
    }

    const users = JSON.parse(
      localStorage.getItem(USERS_KEY) || "[]"
    );

    const emailExists = users.some(
      (user) =>
        user.email?.toLowerCase() ===
        form.email.trim().toLowerCase()
    );

    if (emailExists) {
      return "An account with this email already exists.";
    }

    const usernameExists = users.some(
      (user) =>
        user.username?.toLowerCase() ===
        form.username.trim().toLowerCase()
    );

    if (usernameExists) {
      return "That username is already taken.";
    }

    return "";
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    const validationError = validate();

    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);

    const users = JSON.parse(
      localStorage.getItem(USERS_KEY) || "[]"
    );

    const newUser = {
      id: Date.now(),
      fullName: form.fullName.trim(),
      username: form.username.trim(),
      email: form.email.trim().toLowerCase(),
      phone: form.phone.trim(),
      password: form.password,
      createdAt: new Date().toISOString(),
    };

    localStorage.setItem(
      USERS_KEY,
      JSON.stringify([...users, newUser])
    );

    localStorage.setItem(
      "fc_profile",
      JSON.stringify({
        name: newUser.fullName,
        college: "",
        email: newUser.email,
        course: "",
        year: "Final Year",
        role: "User",
        about: "",
        photo: "",
        username: newUser.username,
        phone: newUser.phone,
      })
    );

    localStorage.setItem(
      "fc_current_user",
      JSON.stringify({
        id: newUser.id,
        fullName: newUser.fullName,
        username: newUser.username,
        email: newUser.email,
      })
    );

    setTimeout(() => {
      setLoading(false);

      if (openDashboard) {
        openDashboard();
      }
    }, 500);
  };

  return (
    <main className="signup-modern-page">

      {/* =====================================================
          LEFT VISUAL PANEL
      ===================================================== */}

      <section className="signup-visual">

        <img
          src="/src/assets/hero.png"
          alt="FactChecker AI"
          className="signup-hero-image"
        />

        <div className="signup-image-overlay"></div>

        <div className="signup-grid"></div>

        <button
          type="button"
          className="signup-back-button"
          onClick={backHome}
        >
          <span>←</span>
          Back to Home
        </button>

        <div className="signup-visual-content">

          <div className="signup-brand-light">

            <div className="signup-brand-icon-light">
              <ShieldIcon />
            </div>

            <span>FactChecker</span>

          </div>

          <div className="signup-visual-bottom">

            <span className="signup-eyebrow">
              AI-POWERED FACT VERIFICATION
            </span>

            <h1>
              Make every
              <br />
              claim
              <br />
              count.
            </h1>

            <p>
              Join FactChecker and use intelligent AI-powered
              tools to analyze, verify and understand information.
            </p>

            <div className="signup-trust-row">

              <div>
                <span>✓</span>
                Smart Analysis
              </div>

              <div>
                <span>✓</span>
                Fast Results
              </div>

              <div>
                <span>✓</span>
                Secure Account
              </div>

            </div>

          </div>

        </div>

        <div className="signup-glow signup-glow-one"></div>
        <div className="signup-glow signup-glow-two"></div>

      </section>


      {/* =====================================================
          RIGHT FORM PANEL
      ===================================================== */}

      <section className="signup-form-area">

        <div className="signup-card">

          {/* BRAND */}

          <div className="signup-brand">

            <div className="signup-brand-icon">
              <ShieldIcon />
            </div>

            <span>
              FactChecker
            </span>

          </div>


          {/* HEADING */}

          <div className="signup-heading">

            <span className="signup-heading-badge">
              CREATE YOUR ACCOUNT
            </span>

            <h2>
              Get started
            </h2>

            <p>
              Create your FactChecker account and start
              verifying information with confidence.
            </p>

          </div>


          {/* ERROR */}

          {error && (
            <div className="signup-error" role="alert">
              <span className="signup-error-icon">!</span>
              <span>{error}</span>
            </div>
          )}


          {/* FORM */}

          <form
            className="signup-form"
            onSubmit={handleSubmit}
            noValidate
          >

            {/* NAME / USERNAME */}

            <div className="signup-row">

              <div className="signup-field">

                <label htmlFor="signup-name">
                  Full Name
                </label>

                <div className="signup-input">

                  <span className="signup-input-icon">
                    <UserIcon />
                  </span>

                  <input
                    id="signup-name"
                    type="text"
                    placeholder="Your full name"
                    value={form.fullName}
                    onChange={(e) =>
                      update("fullName", e.target.value)
                    }
                    autoComplete="name"
                  />

                </div>

              </div>


              <div className="signup-field">

                <label htmlFor="signup-username">
                  Username
                </label>

                <div className="signup-input">

                  <span className="signup-input-prefix">
                    @
                  </span>

                  <input
                    id="signup-username"
                    type="text"
                    placeholder="username"
                    value={form.username}
                    onChange={(e) =>
                      update("username", e.target.value)
                    }
                    autoComplete="username"
                  />

                </div>

              </div>

            </div>


            {/* EMAIL / PHONE */}

            <div className="signup-row">

              <div className="signup-field">

                <label htmlFor="signup-email">
                  Email Address
                </label>

                <div className="signup-input">

                  <span className="signup-input-icon">
                    <MailIcon />
                  </span>

                  <input
                    id="signup-email"
                    type="email"
                    placeholder="you@example.com"
                    value={form.email}
                    onChange={(e) =>
                      update("email", e.target.value)
                    }
                    autoComplete="email"
                  />

                </div>

              </div>


              <div className="signup-field">

                <label htmlFor="signup-phone">
                  Phone
                  <span className="signup-optional">
                    Optional
                  </span>
                </label>

                <div className="signup-input">

                  <span className="signup-input-icon">
                    <PhoneIcon />
                  </span>

                  <input
                    id="signup-phone"
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={(e) =>
                      update("phone", e.target.value)
                    }
                    autoComplete="tel"
                  />

                </div>

              </div>

            </div>


            {/* PASSWORD / CONFIRM */}

            <div className="signup-row">

              <div className="signup-field">

                <div className="signup-label-row">

                  <label htmlFor="signup-password">
                    Password
                  </label>

                  {passwordStrength.label && (
                    <span
                      className={`signup-strength strength-${passwordStrength.score}`}
                    >
                      {passwordStrength.label}
                    </span>
                  )}

                </div>

                <div className="signup-input">

                  <span className="signup-input-icon">
                    <LockIcon />
                  </span>

                  <input
                    id="signup-password"
                    type={
                      showPassword
                        ? "text"
                        : "password"
                    }
                    placeholder="Create a password"
                    value={form.password}
                    onChange={(e) =>
                      update("password", e.target.value)
                    }
                    autoComplete="new-password"
                  />

                  <button
                    type="button"
                    className="signup-eye"
                    onClick={() =>
                      setShowPassword((value) => !value)
                    }
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                  >
                    <EyeIcon hidden={showPassword} />
                  </button>

                </div>

                {form.password && (
                  <div className="signup-strength-box">

                    <div className="signup-strength-bars">

                      {[1, 2, 3, 4].map((bar) => (
                        <span
                          key={bar}
                          className={
                            bar <= passwordStrength.score
                              ? `active strength-${passwordStrength.score}`
                              : ""
                          }
                        ></span>
                      ))}

                    </div>

                    <small>
                      Use 8+ characters with uppercase,
                      number and symbol.
                    </small>

                  </div>
                )}

              </div>


              <div className="signup-field">

                <label htmlFor="signup-confirm">
                  Confirm Password
                </label>

                <div
                  className={`signup-input ${
                    form.confirmPassword &&
                    form.password === form.confirmPassword
                      ? "signup-valid"
                      : ""
                  } ${
                    form.confirmPassword &&
                    form.password !== form.confirmPassword
                      ? "signup-invalid"
                      : ""
                  }`}
                >

                  <span className="signup-input-icon">
                    <LockIcon />
                  </span>

                  <input
                    id="signup-confirm"
                    type={
                      showConfirm
                        ? "text"
                        : "password"
                    }
                    placeholder="Confirm password"
                    value={form.confirmPassword}
                    onChange={(e) =>
                      update(
                        "confirmPassword",
                        e.target.value
                      )
                    }
                    autoComplete="new-password"
                  />

                  <button
                    type="button"
                    className="signup-eye"
                    onClick={() =>
                      setShowConfirm((value) => !value)
                    }
                    aria-label={
                      showConfirm
                        ? "Hide password"
                        : "Show password"
                    }
                  >
                    <EyeIcon hidden={showConfirm} />
                  </button>

                </div>

                {form.confirmPassword &&
                  form.password === form.confirmPassword && (
                    <small className="signup-match">
                      ✓ Passwords match
                    </small>
                  )}

              </div>

            </div>


            {/* TERMS */}

            <label className="signup-terms">

              <input
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) =>
                  setAgreeTerms(e.target.checked)
                }
              />

              <span className="signup-custom-check">
                {agreeTerms && "✓"}
              </span>

              <span>
                I agree to the{" "}
                <button type="button">
                  Terms of Service
                </button>{" "}
                and{" "}
                <button type="button">
                  Privacy Policy
                </button>
                .
              </span>

            </label>


            {/* SUBMIT */}

            <button
              className="signup-submit"
              type="submit"
              disabled={loading}
            >

              {loading ? (
                <>
                  <span className="signup-spinner"></span>
                  Creating account...
                </>
              ) : (
                <>
                  Create Account
                  <span className="signup-submit-arrow">
                    →
                  </span>
                </>
              )}

            </button>

          </form>


          {/* LOGIN */}

          <div className="signup-login-switch">

            <span>
              Already have an account?
            </span>

            <button
              type="button"
              onClick={onLogin}
            >
              Sign in
            </button>

          </div>


          {/* DIVIDER */}

          <div className="signup-divider">
            <span></span>
            <p>OR CONTINUE WITH</p>
            <span></span>
          </div>


          {/* SOCIAL */}

          <div className="signup-social-row">

            <button
              type="button"
              className="signup-social-button"
            >
              <span className="google-letter">
                G
              </span>

              Google
            </button>

            <button
              type="button"
              className="signup-social-button"
            >
              <span className="apple-symbol">
                ●
              </span>

              Apple
            </button>

          </div>


          {/* SECURITY */}

          <div className="signup-security">

            <LockIcon />

            <span>
              Your information is protected with secure
              authentication.
            </span>

          </div>

        </div>

      </section>

    </main>
  );
}

export default SignupPage;

