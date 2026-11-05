import "../styles/FeatureAbout.css";
import ThemeToggle from "../components/Common/ThemeToggle";

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
      title: "Research Architecture",
      text: "The project contains multimodal acquisition, representation, reasoning, and explanation components under research.",
    },
    {
      number: "02",
      icon: "◉",
      title: "Dataset-Label Experiments",
      text: "Fakeddit classifiers predict distant-supervision dataset labels; these outputs are not factual verification.",
    },
    {
      number: "03",
      icon: "✓",
      title: "Evidence Verification",
      text: "Claim-evidence retrieval and evaluation are not implemented. The current service returns verification unavailable.",
    },
    {
      number: "04",
      icon: "⌁",
      title: "Open-Source Model Adapters",
      text: "Research adapters for open-source models do not independently establish whether a claim is true.",
    },
    {
      number: "05",
      icon: "◈",
      title: "Structured Explanations",
      text: "CMREA scaffolding is not an evidence-derived explanation until a validated evaluator supplies provenance.",
    },
    {
      number: "06",
      icon: "↓",
      title: "Research Prototype",
      text: "Unavailable responses do not produce verdicts, factual confidence scores, or evidence reports.",
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

          <ThemeToggle className="inner-theme-toggle" />

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
          ✦ RESEARCH PROTOTYPE
        </span>

        <h1>
          Researching explainable
          <span> multimodal verification.</span>
        </h1>

        <p>
          Evidence-based factual verification is not implemented. Dataset
          classification, where present, must not be interpreted as a truth verdict.
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
            PROTOTYPE STATUS
          </span>

          <h2>
            No evidence-based verdicts
            are currently available.
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