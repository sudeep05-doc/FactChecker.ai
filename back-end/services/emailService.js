const nodemailer = require("nodemailer");

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_APP_PASSWORD,
  },
});

const sendOTPEmail = async (email, otp) => {
  await transporter.sendMail({
    from: `"VerifyAI" <${process.env.EMAIL_USER}>`,
    to: email,
    subject: "VerifyAI Password Reset OTP",

    text: `Your VerifyAI password reset OTP is ${otp}. This OTP will expire in 10 minutes.`,

    html: `
      <div style="
        font-family: Arial, sans-serif;
        max-width: 600px;
        margin: 20px auto;
        padding: 24px;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
      ">
        <h2 style="margin-bottom: 10px;">
          VerifyAI Password Reset
        </h2>

        <p>
          We received a request to reset your VerifyAI password.
        </p>

        <p>
          Your one-time password (OTP) is:
        </p>

        <div style="
          font-size: 32px;
          font-weight: bold;
          letter-spacing: 8px;
          text-align: center;
          padding: 18px;
          margin: 20px 0;
          background: #f4f6ff;
          border-radius: 10px;
        ">
          ${otp}
        </div>

        <p>
          This OTP will expire in <strong>10 minutes</strong>.
        </p>

        <p>
          If you did not request a password reset, you can safely ignore
          this email.
        </p>

        <p>
          — VerifyAI Team
        </p>
      </div>
    `,
  });
};

module.exports = {
  sendOTPEmail,
};