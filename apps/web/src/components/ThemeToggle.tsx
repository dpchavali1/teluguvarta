"use client";

import { Icon } from "@/components/Icon";

function resolvedTheme(): "light" | "dark" {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// One button that flips between light and dark. Which icon shows is pure
// CSS keyed off the same data-theme / prefers-color-scheme rules as the
// tokens, so the first paint is always right with no hydration state.
export function ThemeToggle() {
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
    <button type="button" className="icon-button theme-toggle" onClick={toggle} aria-label="Toggle dark mode" title="Toggle dark mode">
      <span className="theme-toggle__to-dark"><Icon name="moon" /></span>
      <span className="theme-toggle__to-light"><Icon name="sun" /></span>
    </button>
  );
}
