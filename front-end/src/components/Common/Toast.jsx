import { useEffect } from "react";

const Toast = ({
  open,
  message,
  title = "",
  type = "success",
  duration = 3000,
  onClose,
}) => {
  useEffect(() => {
    if (!open) return;

    const timer = setTimeout(() => {
      onClose?.();
    }, duration);

    return () => clearTimeout(timer);
  }, [open, duration, onClose]);

  if (!open) return null;

  const icons = {
    success: "✅",
    error: "❌",
    warning: "⚠️",
    info: "ℹ️",
  };

  return (
    <div className={`toast toast-${type}`}>

      <div className="toast-icon">
        {icons[type]}
      </div>

      <div className="toast-content">

        <h4>
          {title ||
            type.charAt(0).toUpperCase() +
              type.slice(1)}
        </h4>

        <p>{message}</p>

      </div>

      <button
        className="toast-close"
        onClick={onClose}
      >
        ✕
      </button>

    </div>
  );
};

export default Toast;