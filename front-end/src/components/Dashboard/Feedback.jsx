import { useState } from "react";

const Feedback = () => {
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
  e.preventDefault();

  if (rating === 0) {
    alert("Please select a rating.");
    return;
  }

  if (!message.trim()) {
    alert("Please enter your feedback.");
    return;
  }

  const token = localStorage.getItem("fc_token");

  if (!token) {
    alert("Please log in to submit feedback.");
    return;
  }

  try {
    const response = await fetch("http://localhost:5000/api/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        rating,
        message: message.trim(),
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || "Failed to submit feedback.");
    }

    setSubmitted(true);
    setMessage("");
    setRating(0);
  } catch (err) {
    console.error("Feedback submission error:", err);
    alert(err.message || "Failed to submit feedback.");
  }
};

  return (
    <div className="feedback-page">
      <div className="feedback-card">
        <span className="feedback-eyebrow">FEEDBACK</span>

        <h1>Give us your feedback</h1>

        <p className="feedback-description">
          Tell us about your experience with VerifyAI.
          Your feedback helps us improve the platform.
        </p>

        {submitted ? (
          <div className="feedback-success">
            <div className="success-icon">✓</div>

            <h2>Thank you!</h2>

            <p>Your feedback has been submitted successfully.</p>

            <button
              type="button"
              onClick={() => setSubmitted(false)}
            >
              Give More Feedback
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="rating-section">
              <label>How would you rate your experience?</label>

              <div className="stars">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star ${
                      star <= rating ? "selected" : ""
                    }`}
                    onClick={() => setRating(star)}
                    aria-label={`${star} star`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>

            <div className="message-section">
              <label htmlFor="feedback-message">
                Your feedback
              </label>

              <textarea
                id="feedback-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Tell us what you think..."
                rows="6"
              />
            </div>

            <button type="submit" className="submit-feedback">
              Submit Feedback
            </button>
          </form>
        )}
      </div>

      <style>{`
        .feedback-page {
          max-width: 850px;
          margin: 0 auto;
          padding: 20px 0 50px;
        }

        .feedback-card {
          background: #ffffff;
          border: 1px solid #dce3eb;
          border-radius: 18px;
          padding: 35px;
          box-shadow: 0 8px 30px rgba(30, 45, 70, 0.06);
        }

        .feedback-eyebrow {
          color: #6542df;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 2px;
        }

        .feedback-card h1 {
          margin: 8px 0 8px;
          color: #172033;
          font-size: 30px;
        }

        .feedback-description {
          margin-bottom: 30px;
          color: #78859a;
          font-size: 14px;
          line-height: 1.6;
        }

        .rating-section label,
        .message-section label {
          display: block;
          margin-bottom: 10px;
          color: #263148;
          font-size: 13px;
          font-weight: 700;
        }

        .stars {
          display: flex;
          gap: 8px;
          margin-bottom: 30px;
        }

        .star {
          border: 0;
          background: transparent;
          color: #d5dbe4;
          font-size: 34px;
          cursor: pointer;
          padding: 0;
          transition: 0.2s ease;
        }

        .star:hover,
        .star.selected {
          color: #f5b82e;
          transform: scale(1.08);
        }

        .message-section {
          margin-bottom: 22px;
        }

.message-section textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  background: #F4F8FF;
  border: 1px solid #D6E4F5;
  border-radius: 10px;
  padding: 13px;
  font-family: inherit;
  font-size: 13px;
  color: #172033;
  outline: none;
}

        .message-section textarea:focus {
          border-color: #6542df;
          box-shadow: 0 0 0 3px rgba(101, 66, 223, 0.08);
        }

        .submit-feedback {
          border: 0;
          border-radius: 9px;
          padding: 12px 20px;
          background: #6542df;
          color: white;
          cursor: pointer;
          font-size: 12px;
          font-weight: 700;
        }

        .submit-feedback:hover {
          background: #5433c7;
        }

        .feedback-success {
          text-align: center;
          padding: 30px 10px;
        }

        .success-icon {
          width: 55px;
          height: 55px;
          margin: 0 auto 15px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          background: #e5f8ef;
          color: #159966;
          font-size: 25px;
          font-weight: 800;
        }

        .feedback-success h2 {
          color: #172033;
          margin-bottom: 8px;
        }

        .feedback-success p {
          color: #78859a;
          margin-bottom: 20px;
        }

        .feedback-success button {
          border: 1px solid #d9e0e8;
          border-radius: 8px;
          padding: 10px 16px;
          background: white;
          color: #354158;
          cursor: pointer;
          font-weight: 600;
        }

        body.dark .feedback-card {
          background: #111d30;
          border-color: #2b3b56;
        }

        body.dark .feedback-card h1,
        body.dark .rating-section label,
        body.dark .message-section label,
        body.dark .feedback-success h2 {
          color: #f0f4fa;
        }

        body.dark .feedback-description,
        body.dark .feedback-success p {
          color: #9ba9bc;
        }

        body.dark .message-section textarea {
          background: #18253b;
          border-color: #30415d;
          color: #f0f4fa;
        }
      `}</style>
    </div>
  );
};

export default Feedback;