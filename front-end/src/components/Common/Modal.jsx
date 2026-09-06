import { useEffect } from "react";

const Modal = ({
  isOpen,
  title = "",
  children,
  onClose,
  footer = null,
  size = "md",
  closeOnOverlay = true,
}) => {
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };

    if (isOpen) {
      document.addEventListener(
        "keydown",
        handleKeyDown
      );
    }

    return () => {
      document.removeEventListener(
        "keydown",
        handleKeyDown
      );
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={() => {
        if (closeOnOverlay) {
          onClose?.();
        }
      }}
    >
      <div
        className={`modal modal-${size}`}
        onClick={(e) =>
          e.stopPropagation()
        }
      >
        <div className="modal-header">

          <h2>{title}</h2>

          <button
            className="modal-close"
            onClick={onClose}
          >
            ✕
          </button>

        </div>

        <div className="modal-body">
          {children}
        </div>

        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

export default Modal;