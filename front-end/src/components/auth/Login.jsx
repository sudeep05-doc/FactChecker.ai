import { useState } from "react";
import AuthLayout from "./AuthLayout";

export default function Login({ onSignup, onForgotPassword }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e) => {
  e.preventDefault();

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

    if (!response.ok) {
      throw new Error(data.message || "Login failed.");
    }

    // Save authentication information
    localStorage.setItem("fc_token", data.data.token);

    localStorage.setItem(
      "fc_current_user",
      JSON.stringify(data.data.user)
    );

    localStorage.setItem(
      "fc_profile",
      JSON.stringify(data.data.profile)
    );

    console.log("Login successful:", data.data.user);

    // We'll connect this to your dashboard navigation next.
  } catch (err) {
    console.error("Login error:", err);
    alert(err.message || "Unable to login.");
  }
};

  return (
    <AuthLayout>
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-icon">✓</div>
          <span>FactChecker</span>
        </div>

        <h2>Welcome back,</h2>

        <p className="auth-subtitle">
          Sign in to your account
        </p>

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label>Email</label>

            <div className="input-wrapper">
              <span className="input-icon">♙</span>

              <input
                type="email"
                placeholder="Enter your email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <div className="password-label">
              <label>Password</label>

              <button
                type="button"
                onClick={onForgotPassword}
                className="forgot-password"
              >
                Forgot Password?
              </button>
            </div>

            <div className="input-wrapper">
              <span className="input-icon">🔒</span>

              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowPassword(!showPassword)
                }
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <button className="primary-auth-btn" type="submit">
            Login
          </button>
        </form>

        <div className="divider">
          <span></span>
          <p>or sign in with</p>
          <span></span>
        </div>

        <button className="google-btn">
          <span className="google-icon">G</span>
          Continue with Google
        </button>

        <button className="guest-btn">
          Continue as Guest
        </button>

        <p className="switch-auth">
          Don't have an account?
          <button onClick={onSignup}>
            Register
          </button>
        </p>
      </div>
    </AuthLayout>
  );
}