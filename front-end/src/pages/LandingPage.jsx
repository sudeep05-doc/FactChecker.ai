
import Navbar from "../components/Landing/Navbar";
import HeroSection from "../components/Landing/HeroSection";
import PromoVideo from "../components/Landing/PromoVideo";
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
  return (
    <div className="page-enter landing-page">

      <Navbar
        openLogin={openLogin}
        openSignup={openSignup}
        openFeatures={openFeatures}
        openAbout={openAbout}
        openLearnMore={openLearnMore}
      />

      {/* MAIN HERO SECTION */}
      <HeroSection
        openDashboard={openDashboard}
        openLearnMore={openLearnMore}
      />

      {/* PROMOTIONAL VIDEO SECTION */}
      <PromoVideo />

      {/* EXISTING INFORMATION SECTIONS */}
      <InfoSections
        openDashboard={openDashboard}
      />

      {/* FOOTER */}
      <Footer />

    </div>
  );
}

export default LandingPage;
