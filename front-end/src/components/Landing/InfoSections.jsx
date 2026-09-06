const InfoSections = ({ openDashboard }) => {
  return (
    <>
      {/* ================= HOW IT WORKS ================= */}

      <section
        className="how-section section container"
        id="how-it-works"
      >
        <div className="section-heading">
          <span>Simple & Transparent</span>

          <h2>How It Works</h2>

          <p>
            From article to insight in four simple steps.
          </p>
        </div>

        <div className="steps">

          <article className="step">
            <div className="step-icon">
              ▤<b>1</b>
            </div>

            <div>
              <h3>Input News</h3>

              <p>
                Paste news text or article URL into
                the analyzer.
              </p>
            </div>
          </article>

          <span className="step-arrow">→</span>

          <article className="step">
            <div className="step-icon">
              ♧<b>2</b>
            </div>

            <div>
              <h3>AI Analysis</h3>

              <p>
                Our models analyze content using
                multiple credibility signals.
              </p>
            </div>
          </article>

          <span className="step-arrow">→</span>

          <article className="step">
            <div className="step-icon">
              ▥<b>3</b>
            </div>

            <div>
              <h3>Get Results</h3>

              <p>
                Receive a confidence score and
                detailed report instantly.
              </p>
            </div>
          </article>

          <span className="step-arrow">→</span>

          <article className="step">
            <div className="step-icon">
              ♢<b>4</b>
            </div>

            <div>
              <h3>Stay Informed</h3>

              <p>
                Make better decisions and share
                verified information responsibly.
              </p>
            </div>
          </article>

        </div>
      </section>

      {/* ================= FEATURES ================= */}

      <section
        className="features-section"
        id="features"
      >
        <div className="container">

          <div className="section-heading">

            <span>Why FactChecker?</span>

            <h2>
              Smart Detection. Clear Answers.
            </h2>

            <p>
              A modern AI platform built for
              responsible information verification.
            </p>

          </div>

          <div className="feature-grid">

            <article className="feature-card">
              <span>♧</span>

              <h3>Advanced AI Models</h3>

              <p>
                Multiple AI signals work together to
                identify misleading and manipulated
                news articles.
              </p>
            </article>

            <article className="feature-card">
              <span>ϟ</span>

              <h3>Instant Results</h3>

              <p>
                Analyze articles in just a few
                seconds with high-speed processing.
              </p>
            </article>

            <article className="feature-card">
              <span>◎</span>

              <h3>Confidence Score</h3>

              <p>
                Every prediction includes a detailed
                confidence percentage for better
                transparency.
              </p>
            </article>

            <article className="feature-card">
              <span>♙</span>

              <h3>Privacy First</h3>

              <p>
                Your analysis history stays inside
                your browser unless you export it.
              </p>
            </article>

            <article className="feature-card">
              <span>⊕</span>

              <h3>Anywhere Access</h3>

              <p>
                Optimized for desktop, tablet and
                mobile devices with a responsive UI.
              </p>
            </article>

          </div>

        </div>
      </section>

      {/* ================= CTA ================= */}

      <section
        className="cta-section container"
        id="about"
      >

        <div>

          <span className="eyebrow">
            <i>✦</i> READY TO VERIFY?
          </span>

          <h2>
            Make Every Share A Responsible One.
          </h2>

          <p>
            Start using the FactChecker dashboard
            and verify information before sharing.
          </p>

        </div>

        <button
          className="btn btn-primary btn-large"
          onClick={openDashboard}
        >
          Open Dashboard <b>→</b>
        </button>

      </section>

      {/* ================= SUPPORT ================= */}

      <section
        className="support-section container"
        id="support"
      >

        <span className="eyebrow">
          <i>✦</i> PROJECT SUPPORT
        </span>

        <h2>
          Need Help Using FactChecker?
        </h2>

        <p>
          Access the dashboard guide, review your
          previous analyses or contact the project
          team for assistance.
        </p>

        <a
          className="btn btn-outline"
          href="mailto:support@factchecker.demo"
        >
          Contact Support
        </a>

      </section>
    </>
  );
};

export default InfoSections;