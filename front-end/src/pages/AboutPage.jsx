import "../styles/FeatureAbout.css";

function AboutPage({
  openDashboard,
  openLogin,
  openSignup,
  openFeatures,
  backHome,
}) {
  return (
    <div className="about-page">

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

      <section className="about-hero">

        <div className="about-circle"></div>

        <span className="page-badge">
          ✦ ABOUT FACTCHECKER
        </span>

        <h1>
          Building a more
          <span> informed internet.</span>
        </h1>

        <p>
          FactChecker was created to make information
          verification simple, accessible and intelligent.
          Our goal is to help people understand what they
          read before they trust or share it.
        </p>

      </section>


      {/* STORY */}

      <section className="about-story">

        <div className="about-story-text">

          <span className="section-label">
            OUR MISSION
          </span>

          <h2>
            Truth should be
            <span> easier to find.</span>
          </h2>

          <p>
            The internet gives everyone access to an
            enormous amount of information. But with
            that access comes misinformation, misleading
            headlines and unreliable sources.
          </p>

          <p>
            FactChecker uses modern technology to help
            users analyze information and understand
            the reasoning behind every result.
          </p>

        </div>


        {/* VISUAL CARD */}

        <div className="about-visual">

          <div className="verification-card">

            <div className="verification-header">
              <span></span>
              <span></span>
              <span></span>
            </div>

            <div className="verification-content">

              <div className="verification-shield">
                ✓
              </div>

              <div>

                <small>
                  AI ANALYSIS
                </small>

                <h3>
                  Information Verified
                </h3>

                <p>
                  High confidence result
                </p>

              </div>

            </div>

            <div className="verification-line">
              <span></span>
            </div>

            <div className="verification-result">
              <strong>
                92%
              </strong>

              <span>
                Confidence
              </span>
            </div>

          </div>

        </div>

      </section>


      {/* VALUES */}

      <section className="about-values">

        <span className="section-label">
          WHAT WE BELIEVE
        </span>

        <h2>
          Designed around
          <span> trust.</span>
        </h2>

        <div className="values-grid">

          <div className="value-card">

            <span>01</span>

            <h3>
              Transparency
            </h3>

            <p>
              We believe users should understand
              why information receives a particular
              result.
            </p>

          </div>


          <div className="value-card">

            <span>02</span>

            <h3>
              Accuracy
            </h3>

            <p>
              Every analysis is designed to consider
              multiple signals rather than relying on
              a single factor.
            </p>

          </div>


          <div className="value-card">

            <span>03</span>

            <h3>
              Accessibility
            </h3>

            <p>
              Powerful verification technology should
              remain simple enough for everyone to use.
            </p>

          </div>

        </div>

      </section>


      {/* CTA */}

      <section className="about-cta">

        <span>
          VERIFY BEFORE YOU BELIEVE
        </span>

        <h2>
          Ready to discover
          <br />
          what's real?
        </h2>

        <div>

          <button
            type="button"
            className="about-primary"
            onClick={openDashboard}
          >
            Analyze News Now →
          </button>

          <button
            type="button"
            className="about-secondary"
            onClick={openFeatures}
          >
            Explore Features
          </button>

        </div>

      </section>


      {/* BOTTOM */}

      <div className="inner-bottom-nav">

        <button
          type="button"
          onClick={backHome}
        >
          ← Back to Home
        </button>

        <button
          type="button"
          onClick={openFeatures}
        >
          View Features →
        </button>

      </div>

    </div>
  );
}

export default AboutPage;