import {
  createContext,
  useEffect,
  useState,
} from "react";

export const AppContext =
  createContext();

export const AppProvider = ({
  children,
}) => {
  /* ===========================
        Profile
     =========================== */

  const [profile, setProfile] =
    useState({
      name: "Student",
      college: "",
      email: "",
      course: "",
      year: "Final Year",
      role: "Final Year Project",
      about: "",
      photo: "",
    });

  /* ===========================
        Analysis History
     =========================== */

  const [history, setHistory] =
    useState([]);

  /* ===========================
        Loading
     =========================== */

  const [loading, setLoading] =
    useState(false);

  /* ===========================
        Result
     =========================== */

  const [result, setResult] =
    useState(null);

  /* ===========================
        Local Storage Load
     =========================== */

  useEffect(() => {
    const profileData =
      localStorage.getItem(
        "fc_profile"
      );

    const historyData =
      localStorage.getItem(
        "fc_history"
      );

    if (profileData) {
      setProfile(
        JSON.parse(profileData)
      );
    }

    if (historyData) {
      setHistory(
        JSON.parse(historyData)
      );
    }
  }, []);

  /* ===========================
        Save Storage
     =========================== */

  useEffect(() => {
    localStorage.setItem(
      "fc_profile",
      JSON.stringify(profile)
    );
  }, [profile]);

  useEffect(() => {
    localStorage.setItem(
      "fc_history",
      JSON.stringify(history)
    );
  }, [history]);

  /* ===========================
        Fake AI Prediction
     =========================== */

  const analyzeNews = (text) => {
    if (!text.trim()) {
      alert(
        "Please enter news content."
      );
      return;
    }

    setLoading(true);

    setTimeout(() => {
      const confidence =
        Math.floor(
          Math.random() * 21
        ) + 80;

      const fakeWords = [
        "breaking",
        "shocking",
        "viral",
        "exclusive",
        "unbelievable",
        "secret",
        "click",
      ];

      const isFake =
        fakeWords.some((word) =>
          text
            .toLowerCase()
            .includes(word)
        );

      const prediction = {
        id: Date.now(),

        text:
          text.length > 120
            ? text.substring(0, 120) +
              "..."
            : text,

        label: isFake
          ? "Fake News"
          : "Real News",

        confidence,

        time:
          new Date().toLocaleString(),
      };

      setResult(prediction);

      setHistory((prev) => [
        prediction,
        ...prev,
      ]);

      setLoading(false);
    }, 1800);
  };

  /* ===========================
        Delete Record
     =========================== */

  const deleteHistory = (
    id
  ) => {
    setHistory((prev) =>
      prev.filter(
        (item) =>
          item.id !== id
      )
    );
  };

  /* ===========================
        Clear History
     =========================== */

  const clearHistory = () => {
    setHistory([]);
  };

  /* ===========================
        Export History
     =========================== */

  const exportHistory = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          history,
          null,
          2
        ),
      ],
      {
        type: "application/json",
      }
    );

    const url =
      URL.createObjectURL(blob);

    const a =
      document.createElement("a");

    a.href = url;

    a.download =
      "factchecker-history.json";

    a.click();

    URL.revokeObjectURL(url);
  };

  /* ===========================
        Values
     =========================== */

  return (
    <AppContext.Provider
      value={{
        profile,
        setProfile,

        history,
        setHistory,

        result,
        setResult,

        loading,

        analyzeNews,

        deleteHistory,

        clearHistory,

        exportHistory,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};