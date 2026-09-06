import {
  useEffect,
  useRef,
  useState,
} from "react";

import "./AIScanIntro.css";

const STATUS_MESSAGES = [
  "INITIALIZING AI CORE",
  "SCANNING INFORMATION",
  "VERIFYING SOURCES",
  "ANALYSIS COMPLETE",
];

function AIScanIntro({ onComplete }) {
  const [statusIndex, setStatusIndex] = useState(0);
  const [closing, setClosing] = useState(false);

  const audioContextRef = useRef(null);
  const soundPlayedRef = useRef(false);

  /*
   * =========================================================
   * FACTCHECKER TRUTH PULSE SOUND
   * =========================================================
   */

  const playScanSound = () => {
    if (soundPlayedRef.current) {
      return;
    }

    soundPlayedRef.current = true;

    try {
      const AudioContext =
        window.AudioContext ||
        window.webkitAudioContext;

      if (!AudioContext) {
        return;
      }

      const audioContext =
        new AudioContext();

      audioContextRef.current =
        audioContext;

      if (
        audioContext.state === "suspended"
      ) {
        audioContext
          .resume()
          .catch(() => {});
      }

      const now =
        audioContext.currentTime;

      /*
       * MASTER
       */

      const master =
        audioContext.createGain();

      master.gain.setValueAtTime(
        0.0001,
        now
      );

      master.gain.exponentialRampToValueAtTime(
        0.72,
        now + 0.04
      );

      master.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 1.8
      );

      master.connect(
        audioContext.destination
      );

      /*
       * =====================================================
       * DEEP AI BASS
       * =====================================================
       */

      const bass =
        audioContext.createOscillator();

      const bassGain =
        audioContext.createGain();

      bass.type = "sine";

      bass.frequency.setValueAtTime(
        80,
        now
      );

      bass.frequency.exponentialRampToValueAtTime(
        38,
        now + 0.5
      );

      bassGain.gain.setValueAtTime(
        0.0001,
        now
      );

      bassGain.gain.exponentialRampToValueAtTime(
        0.7,
        now + 0.025
      );

      bassGain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 0.6
      );

      bass.connect(bassGain);
      bassGain.connect(master);

      bass.start(now);
      bass.stop(now + 0.65);

      /*
       * =====================================================
       * DIGITAL SCAN
       * =====================================================
       */

      const scan =
        audioContext.createOscillator();

      const scanGain =
        audioContext.createGain();

      scan.type = "square";

      scan.frequency.setValueAtTime(
        250,
        now + 0.22
      );

      scan.frequency.exponentialRampToValueAtTime(
        700,
        now + 0.7
      );

      scanGain.gain.setValueAtTime(
        0.0001,
        now + 0.22
      );

      scanGain.gain.exponentialRampToValueAtTime(
        0.045,
        now + 0.3
      );

      scanGain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 0.78
      );

      scan.connect(scanGain);
      scanGain.connect(master);

      scan.start(now + 0.22);
      scan.stop(now + 0.82);

      /*
       * =====================================================
       * RISING AI PULSE
       * =====================================================
       */

      const pulse =
        audioContext.createOscillator();

      const pulseGain =
        audioContext.createGain();

      pulse.type = "triangle";

      pulse.frequency.setValueAtTime(
        180,
        now + 0.42
      );

      pulse.frequency.exponentialRampToValueAtTime(
        900,
        now + 1.05
      );

      pulseGain.gain.setValueAtTime(
        0.0001,
        now + 0.42
      );

      pulseGain.gain.exponentialRampToValueAtTime(
        0.2,
        now + 0.6
      );

      pulseGain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 1.15
      );

      pulse.connect(pulseGain);
      pulseGain.connect(master);

      pulse.start(now + 0.42);
      pulse.stop(now + 1.2);

      /*
       * =====================================================
       * VERIFICATION SOUND
       * =====================================================
       */

      const verify =
        audioContext.createOscillator();

      const verifyGain =
        audioContext.createGain();

      verify.type = "sine";

      verify.frequency.setValueAtTime(
        760,
        now + 0.95
      );

      verify.frequency.exponentialRampToValueAtTime(
        1250,
        now + 1.1
      );

      verifyGain.gain.setValueAtTime(
        0.0001,
        now + 0.95
      );

      verifyGain.gain.exponentialRampToValueAtTime(
        0.25,
        now + 1.0
      );

      verifyGain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 1.28
      );

      verify.connect(verifyGain);
      verifyGain.connect(master);

      verify.start(now + 0.95);
      verify.stop(now + 1.32);

      /*
       * =====================================================
       * FINAL TRUTH CONFIRMATION
       * =====================================================
       */

      const truth =
        audioContext.createOscillator();

      const truthGain =
        audioContext.createGain();

      truth.type = "sine";

      truth.frequency.setValueAtTime(
        1100,
        now + 1.18
      );

      truth.frequency.exponentialRampToValueAtTime(
        1800,
        now + 1.34
      );

      truthGain.gain.setValueAtTime(
        0.0001,
        now + 1.18
      );

      truthGain.gain.exponentialRampToValueAtTime(
        0.27,
        now + 1.25
      );

      truthGain.gain.exponentialRampToValueAtTime(
        0.0001,
        now + 1.62
      );

      truth.connect(truthGain);
      truthGain.connect(master);

      truth.start(now + 1.18);
      truth.stop(now + 1.68);

      /*
       * CLEANUP
       */

      setTimeout(() => {
        try {
          audioContext.close();
        } catch {
          // Ignore cleanup errors.
        }
      }, 1900);

    } catch {
      // Animation works even if audio is unavailable.
    }
  };

  /*
   * =========================================================
   * INTRO LIFECYCLE
   * =========================================================
   */

  useEffect(() => {
    playScanSound();

    /*
     * Browser autoplay fallback.
     */

    const handleFirstInteraction = () => {
      playScanSound();
    };

    window.addEventListener(
      "pointerdown",
      handleFirstInteraction,
      {
        once: true,
      }
    );

    /*
     * Reduced motion support.
     */

    const reducedMotion =
      window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;

    if (reducedMotion) {
      const reducedTimer =
        setTimeout(() => {
          onComplete();
        }, 350);

      return () => {
        clearTimeout(reducedTimer);

        window.removeEventListener(
          "pointerdown",
          handleFirstInteraction
        );
      };
    }

    /*
     * =====================================================
     * STATUS TIMING
     * =====================================================
     *
     * 0.0s INITIALIZING AI CORE
     * 0.5s SCANNING INFORMATION
     * 1.0s VERIFYING SOURCES
     * 1.5s ANALYSIS COMPLETE
     */

    const statusTimer =
      setInterval(() => {
        setStatusIndex((current) => {
          if (
            current <
            STATUS_MESSAGES.length - 1
          ) {
            return current + 1;
          }

          return current;
        });
      }, 500);

    /*
     * =====================================================
     * TOTAL INTRO = 2.4 SECONDS
     * =====================================================
     *
     * 1.9s → close animation starts
     * 2.4s → intro completely removed
     */

    const closeTimer =
      setTimeout(() => {
        setClosing(true);

        setTimeout(() => {
          onComplete();
        }, 500);
      }, 1900);

    return () => {
      clearInterval(statusTimer);
      clearTimeout(closeTimer);

      window.removeEventListener(
        "pointerdown",
        handleFirstInteraction
      );

      if (audioContextRef.current) {
        audioContextRef.current
          .close()
          .catch(() => {});
      }
    };
  }, [onComplete]);

  /*
   * =========================================================
   * UI
   * =========================================================
   */

  return (
    <div
      className={`ai-intro ${
        closing
          ? "ai-intro--closing"
          : ""
      }`}
      onPointerDown={playScanSound}
      role="status"
      aria-label="FactChecker loading"
    >

      {/* AMBIENT LIGHTS */}

      <div
        className="
          ai-intro__ambient
          ai-intro__ambient--one
        "
      />

      <div
        className="
          ai-intro__ambient
          ai-intro__ambient--two
        "
      />

      {/* GRID */}

      <div className="ai-intro__grid" />

      {/* PARTICLES */}

      <div className="ai-intro__particles">

        {Array.from({
          length: 28,
        }).map((_, index) => (
          <span
            key={index}
            className="ai-particle"
          />
        ))}

      </div>

      {/* MAIN CONTENT */}

      <div className="ai-intro__content">

        {/* LOGO */}

        <div className="ai-logo-stage">

          <div
            className="
              ai-logo-orbit
              ai-logo-orbit--outer
            "
          />

          <div
            className="
              ai-logo-orbit
              ai-logo-orbit--inner
            "
          />

          <div className="ai-logo-glow" />

          <div className="ai-logo-mark">

            <div className="ai-logo-shield">

              <span className="ai-logo-check">
                ✓
              </span>

            </div>

          </div>

          <div className="ai-scan-line" />

        </div>

        {/* BRAND */}

        <div className="ai-brand">

          <div className="ai-brand-name">

            <span>FACT</span>

            <strong>CHECKER</strong>

          </div>

          <div className="ai-brand-subtitle">
            INTELLIGENT NEWS VERIFICATION
          </div>

        </div>

        {/* STATUS */}

        <div className="ai-status">

          <span className="ai-status__dot" />

          <span className="ai-status__text">
            {STATUS_MESSAGES[statusIndex]}
          </span>

        </div>

        {/* PROGRESS */}

        <div className="ai-progress">

          <div
            className="ai-progress__bar"
            style={{
              width: `${Math.min(
                (statusIndex + 1) * 25,
                100
              )}%`,
            }}
          />

        </div>

        <div className="ai-progress-label">

          <span>
            AI ENGINE
          </span>

          <span>
            {Math.min(
              (statusIndex + 1) * 25,
              100
            )}
            %
          </span>

        </div>

      </div>

      {/* CORNERS */}

      <div
        className="
          ai-corner
          ai-corner--top-left
        "
      >
        <span />
        <span />
      </div>

      <div
        className="
          ai-corner
          ai-corner--top-right
        "
      >
        <span />
        <span />
      </div>

      <div
        className="
          ai-corner
          ai-corner--bottom-left
        "
      >
        <span />
        <span />
      </div>

      <div
        className="
          ai-corner
          ai-corner--bottom-right
        "
      >
        <span />
        <span />
      </div>

      {/* FOOTER */}

      <div className="ai-intro__footer">

        <span>
          SECURE AI ANALYSIS
        </span>

        <span>•</span>

        <span>
          REAL-TIME VERIFICATION
        </span>

      </div>

    </div>
  );
}

export default AIScanIntro;
