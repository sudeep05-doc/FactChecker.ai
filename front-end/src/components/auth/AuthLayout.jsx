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
            Research.
            <br />
            Evaluate.
            <br />
            Stay Informed.
          </h1>

          <p>
            Evidence-based factual verification is not
            <br />
            implemented in this prototype.
          </p>
        </div>
      </div>

      <div className="auth-form-area">
        {children}
      </div>
    </div>
  );
}