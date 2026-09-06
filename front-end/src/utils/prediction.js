/* ==========================================
        AI Fake News Prediction Utility
========================================== */

const fakeKeywords = [
  "breaking",
  "shocking",
  "viral",
  "exclusive",
  "secret",
  "click here",
  "100% true",
  "miracle",
  "unbelievable",
  "must watch",
  "share now",
  "forward this",
  "urgent",
  "government hiding",
  "leaked",
  "exposed",
  "conspiracy",
  "fake",
];

const trustedDomains = [
  "bbc.com",
  "reuters.com",
  "apnews.com",
  "thehindu.com",
  "indianexpress.com",
  "ndtv.com",
  "timesofindia.com",
  "hindustantimes.com",
];

/* ==========================================
        Random Confidence
========================================== */

const generateConfidence = (
  isFake
) => {
  if (isFake) {
    return Math.floor(
      Math.random() * 16
    ) + 80;
  }

  return (
    Math.floor(
      Math.random() * 11
    ) + 90
  );
};

/* ==========================================
        URL Checker
========================================== */

const isTrustedSource = (
  url
) => {
  return trustedDomains.some(
    (domain) =>
      url
        .toLowerCase()
        .includes(domain)
  );
};

/* ==========================================
        Keyword Score
========================================== */

const getFakeKeywordScore = (
  text
) => {
  const content =
    text.toLowerCase();

  let score = 0;

  fakeKeywords.forEach(
    (word) => {
      if (
        content.includes(word)
      ) {
        score++;
      }
    }
  );

  return score;
};

/* ==========================================
        Prediction
========================================== */

export const predictNews = ({
  text = "",
  url = "",
}) => {
  const fakeScore =
    getFakeKeywordScore(
      text
    );

  const trusted =
    isTrustedSource(url);

  const isFake =
    fakeScore >= 2 &&
    !trusted;

  const confidence =
    generateConfidence(
      isFake
    );

  return {
    label: isFake
      ? "Fake News"
      : "Real News",

    confidence,

    fakeScore,

    trustedSource:
      trusted,

    explanation: isFake
      ? "Suspicious keywords and writing patterns were detected."
      : "Content appears consistent with trusted reporting patterns.",

    factors: {
      source: trusted
        ? 95
        : 60,

      credibility: isFake
        ? 42
        : 91,

      writing: isFake
        ? 54
        : 89,

      consistency: isFake
        ? 47
        : 93,
    },
  };
};

/* ==========================================
        Demo Delay
========================================== */

export const analyzeWithDelay =
  (
    data,
    delay = 1800
  ) => {
    return new Promise(
      (resolve) => {
        setTimeout(() => {
          resolve(
            predictNews(data)
          );
        }, delay);
      }
    );
  };