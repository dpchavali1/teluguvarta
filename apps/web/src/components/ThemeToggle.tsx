"use client";

import { useEffect, useState } from "react";

type ThemeChoice = "light" | "dark" | null;

function applyTheme(theme: ThemeChoice) {
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeChoice>(null);

  useEffect(() => {
    let stored: ThemeChoice = null;
    try {
      const raw = localStorage.getItem("tg-theme");
      if (raw === "light" || raw === "dark") stored = raw;
    } catch {
      // localStorage unavailable — fall back to system preference
    }
    setTheme(stored);
  }, []);

  function choose(next: "light" | "dark") {
    const value = theme === next ? null : next;
    setTheme(value);
    applyTheme(value);
    try {
      if (value) {
        localStorage.setItem("tg-theme", value);
      } else {
        localStorage.removeItem("tg-theme");
      }
    } catch {
      // best-effort persistence only
    }
  }

  return (
    <div className="theme-toggle" role="group" aria-label="Color theme">
      <button
        type="button"
        aria-pressed={theme === "light"}
        aria-label="Light theme"
        title="Light theme"
        onClick={() => choose("light")}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      </button>
      <button
        type="button"
        aria-pressed={theme === "dark"}
        aria-label="Dark theme"
        title="Dark theme"
        onClick={() => choose("dark")}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      </button>
    </div>
  );
}
