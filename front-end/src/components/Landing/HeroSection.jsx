const HeroSection = ({
  openDashboard,
  openLearnMore,
}) => {
  return (
    <section
      className="hero container apple-motion"
      id="home"
    >

      {/* ================= LEFT CONTENT ================= */}

      <div className="hero-copy reveal">

        <span className="eyebrow">
          <i>✦</i> AI POWERED
        </span>


        <h1>
          Detect <span>Fake News.</span>
          <br />
          Trust <strong>Real News.</strong>
        </h1>


        <p>
          Our advanced AI analyzes news content in seconds
          and helps you identify misinformation, so you can
          stay informed with confidence.
        </p>


        {/* ================= BUTTONS ================= */}

        <div className="hero-buttons">

          {/* Analyze News */}

          <button
            type="button"
            className="btn btn-primary btn-large"
            onClick={openDashboard}
          >
            Analyze News Now <b>→</b>
          </button>


          {/* Learn More */}

          <button
            type="button"
            className="btn btn-outline btn-large"
            onClick={openLearnMore}
          >
            Learn More <b className="play">▶</b>
          </button>

        </div>


        {/* ================= TRUST POINTS ================= */}

        <div className="trust-points">

          <div>

            <span>✧</span>

            <p>
              <b>
                AI-Powered Analysis
              </b>

              <small>
                Advanced ML Models
              </small>
            </p>

          </div>


          <div>

            <span>◉</span>

            <p>
              <b>
                Real-time Results
              </b>

              <small>
                Instant Detection
              </small>
            </p>

          </div>


          <div>

            <span>⌁</span>

            <p>
              <b>
                High Accuracy
              </b>

              <small>
                Trusted & Reliable
              </small>
            </p>

          </div>

        </div>

      </div>


      {/* ================= RIGHT ILLUSTRATION ================= */}

      <div
        className="hero-visual reveal delay-1"
        aria-label="Example AI analysis visual"
      >

        {/* Decorative Orbits */}

        <span className="orbit orbit-a"></span>

        <span className="orbit orbit-b"></span>


        {/* Decorative Sparks */}

        <span className="spark s1">
          ✦
        </span>

        <span className="spark s2">
          ✦
        </span>


        {/* ================= NEWS WINDOW ================= */}

        <div className="news-window">

          <div className="browser-dots">

            <i></i>
            <i></i>
            <i></i>

          </div>


          <span className="window-label">
            ◉ News Analysis
          </span>


          <h3>
            Government to ban social
            <br />
            media apps in next month?
          </h3>


          <small className="tag">
            Trending News
          </small>


          <div className="article-skeleton">

            <div className="image-placeholder">
              ▱
            </div>

            <i></i>

            <i></i>

            <i></i>

          </div>

        </div>


        {/* ================= AI RESULT ================= */}

        <div className="result-card floating-card">

          <small>
            AI Analysis Result
          </small>


          <div className="result-main">

            <div
              className="progress-ring"
              style={{
                "--p": 92,
              }}
            >
              <b>
                92%
              </b>
            </div>


            <div>

              <h3>
                Real News
              </h3>


              <p>
                This news is highly likely to be
                real and credible.
              </p>


              <span className="confidence">
                High Confidence
              </span>

            </div>

          </div>

        </div>


        {/* ================= ANALYSIS FACTORS ================= */}

        <div className="factor-card floating-card">

          <b>
            Analysis Factors
          </b>


          {/* Source Reliability */}

          <div className="factor">

            <span>
              ◉ Source Reliability
            </span>

            <i>
              <b
                style={{
                  width: "92%",
                }}
              ></b>
            </i>

            <em>
              92%
            </em>

          </div>


          {/* Content Credibility */}

          <div className="factor">

            <span>
              ◉ Content Credibility
            </span>

            <i>
              <b
                style={{
                  width: "88%",
                }}
              ></b>
            </i>

            <em>
              88%
            </em>

          </div>


          {/* Writing Patterns */}

          <div className="factor">

            <span>
              ◉ Writing Patterns
            </span>

            <i>
              <b
                style={{
                  width: "85%",
                }}
              ></b>
            </i>

            <em>
              85%
            </em>

          </div>


          {/* Fact Consistency */}

          <div className="factor">

            <span>
              ◉ Fact Consistency
            </span>

            <i>
              <b
                style={{
                  width: "90%",
                }}
              ></b>
            </i>

            <em>
              90%
            </em>

          </div>

        </div>


        {/* ================= SHIELD ================= */}

        <div className="shield">
          ✓
        </div>

      </div>

    </section>
  );
};


export default HeroSection;