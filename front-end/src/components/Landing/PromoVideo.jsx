import { useEffect, useRef } from "react";

const PromoVideo = () => {
  const sectionRef = useRef(null);

  useEffect(() => {
    const section = sectionRef.current;

    if (!section) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          section.classList.add("is-visible");
          observer.disconnect();
        }
      },
      { threshold: 0.2 }
    );

    observer.observe(section);

    return () => observer.disconnect();
  }, []);

  return (
    <section className="promo-video-section" ref={sectionRef}>
      <div className="promo-video-container">

        <div className="promo-video-heading">
          <span className="promo-badge">
            ✦ DISCOVER FACTCHECKER AI
          </span>

          <h2>
            See How <span>FactChecker</span> Works
          </h2>

          <p>
            Discover how our research prototype helps users
            explore news claims, inspect information and
            understand the importance of evidence-based
            verification.
          </p>
        </div>

        <div className="promo-video-frame">
          <video
            className="promo-video"
            controls
            playsInline
            preload="metadata"
          >
            <source
              src="/videos/factchecker-promo.mp4"
              type="video/mp4"
            />

            Your browser does not support HTML video.
          </video>
        </div>

        <div className="promo-video-footer">
          <span>✦ FactChecker AI</span>
          <span>Explore. Examine. Understand.</span>
        </div>

      </div>

      <style>{`
        .promo-video-section {
          width: 100%;
          padding: 90px 6%;
          background: linear-gradient(
            180deg,
            #f8f7ff 0%,
            #ffffff 100%
          );
          transition: background 250ms ease, color 250ms ease;
        }

        body.dark-theme .promo-video-section {
          background:
            radial-gradient(
              circle at 50% 0,
              rgba(93, 69, 220, 0.13),
              transparent 42%
            ),
            linear-gradient(180deg, #0d1425, #080e1c);
        }

        .promo-video-heading,
        .promo-video-frame,
        .promo-video-footer {
          opacity: 0;
          transform: translateY(24px);
          transition: opacity 650ms ease, transform 650ms ease;
        }

        .promo-video-section.is-visible .promo-video-heading,
        .promo-video-section.is-visible .promo-video-frame,
        .promo-video-section.is-visible .promo-video-footer {
          opacity: 1;
          transform: translateY(0);
        }

        .promo-video-section.is-visible .promo-video-frame {
          transition-delay: 120ms;
        }

        .promo-video-section.is-visible .promo-video-footer {
          transition-delay: 220ms;
        }

        .promo-video-container {
          max-width: 1100px;
          margin: auto;
        }

        .promo-video-heading {
          text-align: center;
          max-width: 720px;
          margin: 0 auto 38px;
        }

        .promo-badge {
          display: inline-block;
          padding: 9px 18px;
          border-radius: 30px;
          background: #eeeaff;
          color: #7046e8;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 1px;
          margin-bottom: 18px;
        }

        body.dark-theme .promo-badge {
          background: #211b42;
          color: #b4a2ff;
        }

        .promo-video-heading h2 {
          color: #17152b;
          font-size: clamp(28px, 4vw, 43px);
          font-weight: 800;
          margin: 0 0 16px;
        }

        body.dark-theme .promo-video-heading h2 {
          color: #f0f4ff;
        }

        .promo-video-heading h2 span {
          color: #7951e8;
        }

        body.dark-theme .promo-video-heading h2 span,
        body.dark-theme .promo-video-footer span:first-child {
          color: #a28cff;
        }

        .promo-video-heading p {
          color: #77748b;
          line-height: 1.8;
          font-size: 15px;
        }

        body.dark-theme .promo-video-heading p,
        body.dark-theme .promo-video-footer {
          color: #9ca8bd;
        }

        .promo-video-frame {
          width: min(100%, 800px);
          margin: 0 auto;
          overflow: hidden;
          border-radius: 22px;
          background: #101020;
          border: 5px solid white;
          box-shadow:
            0 25px 65px rgba(72, 48, 140, 0.16),
            0 5px 20px rgba(0, 0, 0, 0.08);
          transition: transform 0.35s ease,
                      box-shadow 0.35s ease;
        }

        body.dark-theme .promo-video-frame {
          border-color: #222d45;
          box-shadow:
            0 25px 65px rgba(0, 0, 0, 0.35),
            0 5px 20px rgba(0, 0, 0, 0.22);
        }

        .promo-video-frame:hover {
          transform: translateY(-5px);
          box-shadow:
            0 30px 75px rgba(72, 48, 140, 0.23);
        }

        .promo-video {
          width: 100%;
          display: block;
          aspect-ratio: 16 / 9;
          object-fit: contain;
          background: #101020;
        }

        @media (prefers-reduced-motion: reduce) {
          .promo-video-heading,
          .promo-video-frame,
          .promo-video-footer {
            opacity: 1;
            transform: none;
            transition: none;
          }
        }

        .promo-video-footer {
          display: flex;
          justify-content: space-between;
          gap: 15px;
          flex-wrap: wrap;
          margin-top: 20px;
          color: #77748b;
          font-size: 13px;
          font-weight: 600;
        }

        .promo-video-footer span:first-child {
          color: #7951e8;
        }

        @media (max-width: 600px) {
          .promo-video-section {
            padding: 60px 5%;
          }

          .promo-video-frame {
            border-radius: 13px;
            border-width: 3px;
          }

          .promo-video-footer {
            font-size: 11px;
          }
        }
      `}</style>
    </section>
  );
};

export default PromoVideo;
