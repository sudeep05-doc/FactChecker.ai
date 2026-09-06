import "../styles/FeatureAbout.css";

function FeaturesPage({
  openDashboard,
  openLogin,
  openSignup,
  openAbout,
  backHome,
}) {
  const features = [
    {
      number: "01",
      icon: "✦",
      title: "AI-Powered Analysis",
      text: "Our intelligent system analyzes news content and identifies suspicious claims using advanced AI techniques.",
    },
    {
      number: "02",
      icon: "◉",
      title: "Real-Time Detection",
      text: "Get fast analysis results so you can verify information before sharing or believing it.",
    },
    {
      number: "03",
      icon: "✓",
      title: "High Accuracy",
      text: "FactChecker evaluates multiple factors to provide reliable and easy-to-understand results.",
    },
    {
      number: "04",
      icon: "⌁",
      title: "Source Verification",
      text: "Analyze the credibility and reliability of information sources before trusting a claim.",
    },
    {
      number: "05",
      icon: "◈",
      title: "Smart Explanations",
      text: "Understand why a piece of information is classified as real, misleading, or potentially fake.",
    },
    {
      number: "06",
      icon: "↓",
      title: "Report & Download",
      text: "Save your analysis results and generate useful reports for future reference.",
    },
  ];

  return (
    <div className="feature-page">

      {/* HEADER */}

      <header className="inner-page-nav">

        <button
          type="button"
          className="inner-logo"
          onClick={backHome}
        >
          <span>✓</span>

          <strong>
            Fact<em>Checker</em>
          </strong>
        </button>

        <div className="inner-actions">

          <button
            type="button"
            onClick={openLogin}
          >
            Login
          </button>

          <button
            type="button"
            className="inner-signup"
            onClick={openSignup}
          >
            Sign Up
          </button>

        </div>

      </header>


      {/* HERO */}

      <section className="inner-hero">

        <div className="hero-orb orb-one"></div>
        <div className="hero-orb orb-two"></div>

        <span className="page-badge">
          ✦ POWERFUL FEATURES
        </span>

        <h1>
          Everything you need to
          <span> verify the truth.</span>
        </h1>

        <p>
          FactChecker combines intelligent analysis,
          source verification and clear explanations
          to help you make better decisions online.
        </p>

      </section>


      {/* FEATURE GRID */}

      <section className="feature-grid-section">

        <div className="feature-grid">

          {features.map((feature, index) => (
            <article
              className="feature-card"
              key={feature.number}
              style={{
                "--delay": `${index * 80}ms`,
              }}
            >

              <div className="feature-card-top">

                <span className="feature-number">
                  {feature.number}
                </span>

                <span className="feature-icon">
                  {feature.icon}
                </span>

              </div>

              <h2>
                {feature.title}
              </h2>

              <p>
                {feature.text}
              </p>

              <span className="feature-arrow">
                →
              </span>

            </article>
          ))}

        </div>

      </section>


      {/* CTA */}

      <section className="feature-cta">

        <div>

          <span>
            READY TO VERIFY?
          </span>

          <h2>
            Start checking information
            with confidence.
          </h2>

        </div>

        <button
          type="button"
          onClick={openDashboard}
        >
          Analyze News Now
          <span>→</span>
        </button>

      </section>


      {/* FOOTER NAV */}

      <div className="inner-bottom-nav">

        <button
          type="button"
          onClick={backHome}
        >
          ← Back to Home
        </button>

        <button
          type="button"
          onClick={openAbout}
        >
          About FactChecker →
        </button>

      </div>

    </div>
  );
}

export default FeaturesPage;