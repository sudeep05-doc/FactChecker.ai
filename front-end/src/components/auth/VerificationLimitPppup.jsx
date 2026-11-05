import { useEffect, useRef } from "react";

export default function VerificationLimitPopup({
  open,
  onClose,
  onRegister,
  onLogin,
}) {
  const popupRef = useRef(null);

  useEffect(() => {
    if (!open) return;

    const handleOutsideClick = (event) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(event.target)
      ) {
        onClose();
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener(
      "mousedown",
      handleOutsideClick
    );

    document.addEventListener(
      "keydown",
      handleEscape
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleOutsideClick
      );

      document.removeEventListener(
        "keydown",
        handleEscape
      );
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="limit-overlay">
      <div
        className="limit-popup"
        ref={popupRef}
      >
        <button
          className="popup-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>

        <div className="popup-brand">
          <div className="popup-brand-icon">
            ✓
          </div>

          <span>FactChecker</span>
        </div>

        <h2>
          You've used your 2 free
          <br />
          verifications.
        </h2>

        <p className="popup-description">
          Create a free account to continue.
        </p>

        <div className="popup-divider"></div>

        <div className="popup-feature">
          <div className="feature-icon">∞</div>

          <div>
            <strong>Unlimited Verification</strong>
            <p>
              Continue verifying content without
              the free limit.
            </p>
          </div>
        </div>

        <div className="popup-feature">
          <div className="feature-icon">▣</div>

          <div>
            <strong>Save Reports</strong>
            <p>
              Save your verification reports and
              access them anytime.
            </p>
          </div>
        </div>

        <div className="popup-feature">
          <div className="feature-icon">◷</div>

          <div>
            <strong>Verification History</strong>
            <p>
              Keep track of your previous
              verification results.
            </p>
          </div>
        </div>

        <div className="popup-feature">
          <div className="feature-icon">⇩</div>

          <div>
            <strong>Download Reports</strong>
            <p>
              Download reports for your records.
            </p>
          </div>
        </div>

        <div className="popup-actions">
          <button
            className="popup-register"
            onClick={onRegister}
          >
            Register
          </button>

          <button
            className="popup-login"
            onClick={onLogin}
          >
            Login
          </button>

          <button
            className="popup-cancel"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}