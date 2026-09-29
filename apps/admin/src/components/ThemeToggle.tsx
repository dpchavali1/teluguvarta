"use client";

// Mirrors apps/web/src/components/ThemeToggle.tsx: same data-theme attribute,
// same localStorage key, and which label shows is pure CSS keyed off the same
// rules as the tokens, so first paint is right with no hydration state.
function resolvedTheme(): "light" | "dark" {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function ThemeToggle() {
  function toggle() {
    const next = resolvedTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("tg-theme", next);
    } catch {
      // best-effort persistence only
    }
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label="Toggle dark mode">
      <span className="theme-toggle__to-dark">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
        Dark mode
      </span>
      <span className="theme-toggle__to-light">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
        </svg>
        Light mode
      </span>
    </button>
  );
}
