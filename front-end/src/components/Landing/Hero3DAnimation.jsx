const Hero3DAnimation = () => {
  return (
    <div className="hero-3d" aria-label="Animated AI verification shield">
      <div className="hero-3d-glow" />

      <div className="hero-3d-orbit hero-3d-orbit-one" />
      <div className="hero-3d-orbit hero-3d-orbit-two" />

      <span className="hero-3d-particle particle-one">✦</span>
      <span className="hero-3d-particle particle-two">•</span>
      <span className="hero-3d-particle particle-three">✦</span>
      <span className="hero-3d-particle particle-four">•</span>

      <div className="hero-3d-stage">
        <div className="hero-3d-card">
          <div className="hero-3d-card-face hero-3d-card-front">
            <div className="hero-3d-shield">
              <div className="hero-3d-shield-inner">
                <span>✓</span>
              </div>
            </div>
            <div className="hero-3d-status">
              <span className="status-dot" />
              AI VERIFIED
            </div>
          </div>
          <div className="hero-3d-card-face hero-3d-card-back">
            <strong>92%</strong>
            <small>Trust Score</small>
          </div>
        </div>
      </div>

      <div className="hero-3d-label label-top">REAL-TIME</div>
      <div className="hero-3d-label label-bottom">FACT CHECKED</div>
    </div>
  );
};

export default Hero3DAnimation;
