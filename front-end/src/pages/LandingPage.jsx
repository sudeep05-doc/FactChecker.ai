
import Navbar from "../components/Landing/Navbar";
import HeroSection from "../components/Landing/HeroSection";
import InfoSections from "../components/Landing/InfoSections";
import Footer from "../components/Landing/Footer";

function LandingPage({
  openDashboard,
  openLogin,
  openSignup,
  openFeatures,
  openAbout,
  openLearnMore,
}) {
  // Landing page buttons should open Login first.
  const goToLogin = () => {
    if (openLogin) {
      openLogin();
    }
  };

  return (
    <div className="page-enter landing-page">

      <Navbar
        openDashboard={openDashboard}
        openLogin={openLogin}
        openSignup={openSignup}
        openFeatures={openFeatures}
        openAbout={openAbout}
        openLearnMore={openLearnMore}
      />

      <HeroSection
        openDashboard={goToLogin}
        openLearnMore={openLearnMore}
      />

      <InfoSections
        openDashboard={goToLogin}
      />

      <Footer />

    </div>
  );
}

export default LandingPage;
