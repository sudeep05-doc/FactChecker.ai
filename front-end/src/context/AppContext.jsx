import {
  createContext,
  useEffect,
  useState,
} from "react";
import { createUnavailableVerification } from "../utils/prediction";

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
  const loadData = async () => {
    // Load history
    const historyData = localStorage.getItem("fc_history");

    if (historyData) {
      setHistory(JSON.parse(historyData));
    }

    // Get current login token
    const token = localStorage.getItem("fc_token");

    // No logged-in account
    if (!token) {
      return;
    }

    try {
      const response = await fetch(
        "http://localhost:5000/api/users/profile",
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "Failed to load profile."
        );
      }

      // This profile belongs to the account
      // represented by fc_token.
      const latestProfile = data.data;

      setProfile(latestProfile);

      localStorage.setItem(
        "fc_profile",
        JSON.stringify(latestProfile)
      );
    } catch (error) {
      console.error(
        "Failed to load profile:",
        error
      );
    }
  };

  loadData();
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
        Verification placeholder
     =========================== */

  const analyzeNews = (text) => {
    if (!text.trim()) {
      alert(
        "Please enter news content."
      );
      return;
    }

    setLoading(true);

    const prediction = createUnavailableVerification({
      type: "text",
      content: text,
    });

    setResult(prediction);
    setHistory((prev) => [
      {
        ...prediction,
        text: prediction.text,
      },
      ...prev,
    ]);
    setLoading(false);
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