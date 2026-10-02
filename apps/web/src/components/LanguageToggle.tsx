"use client";

import { useEffect, useState } from "react";

import { LANGUAGE_CHANGE_EVENT, getPreferredLanguage, refreshPreferredLanguage, setPreferredLanguage, type Language } from "@/lib/onboarding";
import { applyStoryLanguage, normalizeStoryLanguage, PROFILE_STORAGE_KEY } from "@/lib/storyLanguage";

// Design-review fix: web previously had no site-wide language preference —
// every StoryCard reset to English on every reload. This toggle sets the
// preference every StoryCard reads as its default (see StoryCard.tsx) and
// broadcasts LANGUAGE_CHANGE_EVENT so cards already on the page update too.
export function LanguageToggle() {
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    const sync = () => {
      const next = getPreferredLanguage();
      applyStoryLanguage(next);
      setLanguage(next);
    };
    const changed = (event: Event) => {
      const next = normalizeStoryLanguage((event as CustomEvent<Language>).detail);
      applyStoryLanguage(next);
      setLanguage(next);
    };
    const stored = (event: StorageEvent) => {
      if (event.key !== null && event.key !== PROFILE_STORAGE_KEY) return;
      const next = refreshPreferredLanguage();
      applyStoryLanguage(next);
      setLanguage(next);
    };
    sync();
    window.addEventListener(LANGUAGE_CHANGE_EVENT, changed);
    window.addEventListener("storage", stored);
    return () => { window.removeEventListener(LANGUAGE_CHANGE_EVENT, changed); window.removeEventListener("storage", stored); };
  }, []);

  function choose(next: Language) {
    setLanguage(next);
    setPreferredLanguage(next);
  }

  return (
    <div className="language-toggle" role="group" aria-label="Story language">
      <button type="button" aria-label="English" aria-pressed={language === "en"} onClick={() => choose("en")}>
        EN
      </button>
      <button type="button" aria-label="Telugu" aria-pressed={language === "te"} onClick={() => choose("te")} lang="te">
        తె
      </button>
    </div>
  );
}
