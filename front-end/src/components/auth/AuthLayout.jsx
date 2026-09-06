import React from "react";
import "./Auth.css";

export default function AuthLayout({ children }) {
  return (
    <div className="auth-page">
      <div className="auth-visual">
        <div className="visual-overlay"></div>

        <div className="visual-content">
          <div className="visual-logo">
            <span className="logo-check">✓</span>
            <span>FactChecker</span>
          </div>

          <h1>
            Detect.
            <br />
            Verify.
            <br />
            Stay Informed.
          </h1>

          <p>
            AI-powered verification that helps you separate
            <br />
            real information from misinformation.
          </p>
        </div>
      </div>

      <div className="auth-form-area">
        {children}
      </div>
    </div>
  );
}