const Footer = () => {
  return (
    <footer className="container">

      {/* Logo */}
      <a className="brand" href="#home">

        <span className="brand-mark fact-logo">
          ✓
        </span>

        <span>
          <b>
            Fact<em>Checker</em>
          </b>

          <small>
            Verify Before You Believe.
          </small>
        </span>

      </a>

      {/* Copyright */}
      <p>
        © {new Date().getFullYear()} FactChecker · Final Year Project Demo
      </p>

      {/* Footer Links */}
      <div>

        <a href="#features">
          Features
        </a>

        <a href="#how-it-works">
          Methodology
        </a>

        <a href="#about">
          About
        </a>

        <a href="#support">
          Support
        </a>

        <a href="#privacy">
          Privacy
        </a>

      </div>

    </footer>
  );
};

export default Footer;