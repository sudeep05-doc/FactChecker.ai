import "../styles/LearnMore.css";
import ThemeToggle from "../components/Common/ThemeToggle";

function LearnMorePage({
  openDashboard,
  openLogin,
  openSignup,
  openFeatures,
  openAbout,
  backHome,
}) {
  const steps = [
    {
      icon: "▤",
      title: "Submit News",
      text: "Submit supported content to the research prototype.",
    },
    {
      icon: "AI",
      title: "Verification Status",
      text: "Evidence-based factual verification is not implemented.",
    },
    {
      icon: "▥",
      title: "Unavailable Response",
      text: "No factual verdict or confidence score is generated.",
    },
    {
      icon: "♢",
      title: "Research Scope",
      text: "Fakeddit dataset labels are not independently verified truth labels.",
    },
  ];

  const features = [
    {
      icon: "✦",
      title: "Multimodal Research",
      text: "The repository contains research components; they are not an end-to-end fact-checking system.",
    },
    {
      icon: "◷",
      title: "Evidence Evaluation",
      text: "Evidence retrieval, claim-evidence assessment, and evidence-backed verdicts are not implemented.",
    },
    {
      icon: "♢",
      title: "Dataset Classifiers",
      text: "A dataset-classification score is scoped to its labels and is not factual confidence.",
    },
    {
      icon: "▥",
      title: "Explanation Boundaries",
      text: "No explanation or citation is presented as evidence unless it can be traced to evaluated sources.",
    },
  ];

  const factors = [
    ["Source Reliability", 92],
    ["Content Credibility", 88],
    ["Writing Patterns", 85],
    ["Fact Consistency", 90],
  ];

  const testimonials = [
    {
      text: "FactChecker has become my go-to tool before sharing any news. It's fast, accurate, and incredibly reliable.",
      name: "Arjun Sharma",
      role: "Journalist",
    },
    {
      text: "As a teacher, I use FactChecker to educate students about fake news. The analysis reports are very helpful.",
      name: "Priya Mehta",
      role: "Educator",
    },
    {
      text: "Illustrative testimonial only; it is not evidence of model performance or verification accuracy.",
      name: "Rahul Verma",
      role: "Researcher",
    },
  ];

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: "smooth",
    });
  };

  return (
    <div className="learn-page">

      {/* ================= NAVBAR ================= */}

      <header className="learn-nav">

        <button
          className="learn-brand"
          onClick={backHome}
          type="button"
        >
          <span className="learn-brand-mark">✓</span>

          <span>
            <strong>
              Fact<em>Checker</em>
            </strong>

            <small>
              Verify Before You Believe.
            </small>
          </span>
        </button>

        <nav>
          <button onClick={backHome}>
            Home
          </button>

          <button onClick={openFeatures}>
            Features
          </button>

          <button
            className="active"
            onClick={() => scrollTo("learn-how")}
          >
            How It Works
          </button>

          <button onClick={openAbout}>
            About Us
          </button>

          <button
            onClick={() => scrollTo("learn-support")}
          >
            Support
          </button>

          <button
            onClick={() => scrollTo("learn-pricing")}
          >
            Pricing
          </button>
        </nav>

        <div className="learn-actions">

          <ThemeToggle className="learn-theme" />

          <button
            className="learn-login"
            onClick={openLogin}
          >
            Login
          </button>

          <button
            className="learn-signup"
            onClick={openSignup}
          >
            Sign Up
          </button>

        </div>

      </header>


      {/* ================= HERO ================= */}

      <main>

        <section className="learn-hero">

          <div className="learn-hero-copy">

            <span className="learn-eyebrow">
              ✦ ABOUT FACTCHECKER
            </span>

            <h1>
              Learn More About
              <br />
              <span>FactChecker</span>
            </h1>

            <p>
              FactChecker is an AI-powered platform designed
              to help you detect fake news, misinformation,
              and unreliable sources in just a few seconds.
            </p>

            <ul>

              <li>
                ✓
                <span>
                  Advanced AI models analyze content deeply
                </span>
              </li>

              <li>
                ✓
                <span>
                  Real-time results you can trust
                </span>
              </li>

              <li>
                ✓
                <span>
                  Verified sources & transparent analysis
                </span>
              </li>

              <li>
                ✓
                <span>
                  Built for everyone who values the truth
                </span>
              </li>

            </ul>

          </div>


          {/* ================= DASHBOARD MOCKUP ================= */}

          <div className="learn-dashboard-art">

            <div className="art-orbit orbit-x" />
            <div className="art-orbit orbit-y" />

            <div className="mini-sidebar">

              <b>
                <span>✓</span>
                FactChecker
              </b>

              <a className="selected">
                ⌂ Dashboard
              </a>

              <a>
                ◷ History
              </a>

              <a>
                ▢ Bookmarks
              </a>

              <a>
                ▤ Reports
              </a>

              <a>
                ⚙ Settings
              </a>

              <a>
                ?
              </a>

            </div>


            <div className="analysis-window">

              <div className="analysis-head">

                <b>
                  Illustrative mockup — not a result
                </b>

                <span>
                  •
                </span>

              </div>


              <div className="analysis-main">

                <div className="score-ring">
                  <strong>
                    N/A
                  </strong>
                </div>

                <div>

                  <h3>
                    Verification unavailable
                  </h3>

                  <p>
                    Evidence-based factual verification is not implemented.
                  </p>

                  <small>
                    No factual confidence score
                  </small>

                </div>

              </div>


              <div className="factor-box">

                <b>
                  Analysis Factors
                </b>

                {factors.map(([name, value]) => (

                  <div
                    className="factor-row"
                    key={name}
                  >

                    <span>
                      {name}
                    </span>

                    <i>
                      <b
                        style={{
                          width: `${value}%`,
                        }}
                      />
                    </i>

                    <em>
                      {value}%
                    </em>

                  </div>

                ))}

              </div>


              <div className="news-preview">

                <div>

                  <b>
                    News Analyzed
                  </b>

                  <strong>
                    Government announces new
                    <br />
                    digital media policy
                  </strong>

                  <small>
                    Trending News · 2h ago
                  </small>

                </div>

                <div className="news-image">
                  🏛️
                </div>

              </div>

            </div>

          </div>

        </section>


        {/* ================= HOW IT WORKS ================= */}

        <section
          className="learn-section bordered"
          id="learn-how"
        >

          <div className="learn-title">

            <h2>
              How <span>FactChecker</span> Works
            </h2>

          </div>


          <div className="learn-steps">

            {steps.map((step, index) => (

              <div
                className="learn-step-wrap"
                key={step.title}
              >

                <article className="learn-step">

                  <div className="step-badge">

                    {step.icon}

                    <b>
                      {index + 1}
                    </b>

                  </div>

                  <div>

                    <h3>
                      {step.title}
                    </h3>

                    <p>
                      {step.text}
                    </p>

                  </div>

                </article>

                {index < steps.length - 1 && (
                  <span className="learn-arrow">
                    →
                  </span>
                )}

              </div>

            ))}

          </div>

        </section>


        {/* ================= FEATURES ================= */}

        <section
          className="learn-section"
          id="learn-features"
        >

          <div className="learn-title">

            <h2>
              Powerful <span>Features</span>
              {" "}for Smarter Decisions
            </h2>

          </div>


          <div className="learn-feature-grid">

            {features.map((feature) => (

              <article
                className="learn-feature"
                key={feature.title}
              >

                <div className="feature-icon">
                  {feature.icon}
                </div>

                <h3>
                  {feature.title}
                </h3>

                <p>
                  {feature.text}
                </p>

              </article>

            ))}

          </div>

        </section>


        {/* ================= AI TECHNOLOGY ================= */}

        <section className="ai-tech">

          <div>

            <h2>
              Research Components
            </h2>

            <p>
              The project explores open-source foundation models and
              multimodal reasoning. No evidence-backed factual verdict is
              currently produced.
            </p>


            <div className="tech-tags">

              {[
                "NLP Processing",
                "Machine Learning",
                "Deep Learning",
                "Data Mining",
                "Pattern Recognition",
                "Evidence Verification (not implemented)",
              ].map((tag) => (

                <span key={tag}>
                  {tag}
                </span>

              ))}

            </div>

          </div>


          <div className="brain-art">

            <div className="brain">
              🧠
            </div>

            <div className="brain-base" />

          </div>

        </section>


        {/* ================= STATISTICS ================= */}

        <section className="stats-section">

          <div className="learn-title">

            <h2>
              Trusted by <span>Thousands</span>
              {" "}Worldwide
            </h2>

          </div>


          <div className="stats-grid">

            {[
              ["♙", "50K+", "Active Users"],
              ["♢", "2M+", "News Analyzed"],
              ["◉", "98.7%", "Accuracy Rate"],
              ["◎", "120+", "Countries"],
            ].map(([icon, value, label]) => (

              <div key={value}>

                <i>
                  {icon}
                </i>

                <b>
                  {value}
                </b>

                <small>
                  {label}
                </small>

              </div>

            ))}

          </div>

        </section>


        {/* ================= TESTIMONIALS ================= */}

        <section className="learn-section testimonials">

          <div className="learn-title">

            <h2>
              What Our <span>Users</span> Say
            </h2>

          </div>


          <div className="testimonial-grid">

            {testimonials.map((testimonial) => (

              <article
                key={testimonial.name}
              >

                <span className="quote">
                  “
                </span>

                <p>
                  {testimonial.text}
                </p>


                <div className="person">

                  <span>
                    {testimonial.name[0]}
                  </span>

                  <div>

                    <b>
                      {testimonial.name}
                    </b>

                    <small>
                      {testimonial.role}
                    </small>

                  </div>

                  <strong>
                    ★★★★★
                  </strong>

                </div>

              </article>

            ))}

          </div>

        </section>


        {/* ================= CTA ================= */}

        <section
          className="learn-cta"
          id="learn-pricing"
        >

          <div>

            <h2>
              Evidence-Based Verification Is Not Available Yet
            </h2>

            <p>
              This research prototype does not currently verify factual claims.
            </p>

          </div>


          <button onClick={openDashboard}>
            Analyze News Now →
          </button>

          <button
            className="cta-outline"
            onClick={openSignup}
          >
            Sign Up Free
          </button>

        </section>

      </main>


      {/* ================= FOOTER ================= */}

      <footer
        className="learn-footer"
        id="learn-support"
      >

        <div className="footer-brand">

          <button
            className="learn-brand"
            onClick={backHome}
          >

            <span className="learn-brand-mark">
              ✓
            </span>

            <span>

              <strong>
                Fact<em>Checker</em>
              </strong>

              <small>
                Verify Before You Believe.
              </small>

            </span>

          </button>


          <p>
            Our mission is to empower everyone with
            the ability to provide accurate AI-powered
            news verification.
          </p>

        </div>


        <div>

          <b>
            Product
          </b>

          <a onClick={openFeatures}>
            Features
          </a>

          <a onClick={() => scrollTo("learn-how")}>
            How It Works
          </a>

          <a onClick={() => scrollTo("learn-pricing")}>
            Pricing
          </a>

          <a>
            Updates
          </a>

        </div>


        <div>

          <b>
            Company
          </b>

          <a onClick={openAbout}>
            About Us
          </a>

          <a>
            Blog
          </a>

          <a>
            Careers
          </a>

          <a>
            Press Kit
          </a>

        </div>


        <div>

          <b>
            Support
          </b>

          <a>
            Help Center
          </a>

          <a>
            Contact Us
          </a>

          <a>
            Privacy Policy
          </a>

          <a>
            Terms of Service
          </a>

        </div>


        <div>

          <b>
            Newsletter
          </b>

          <p>
            Stay updated with our latest news
            and product updates.
          </p>

          <div className="subscribe">

            <input
              placeholder="Enter your email"
            />

            <button>
              Subscribe
            </button>

          </div>

        </div>


        <div className="footer-bottom">

          © {new Date().getFullYear()}
          {" "}FactChecker. All rights reserved.

        </div>

      </footer>

    </div>
  );
}

export default LearnMorePage;