"use client";

import { useEffect, useState } from "react";

import { LANGUAGE_CHANGE_EVENT, getPreferredLanguage, setPreferredLanguage, type Language } from "@/lib/onboarding";

// Design-review fix: web previously had no site-wide language preference —
// every StoryCard reset to English on every reload. This toggle sets the
// preference every StoryCard reads as its default (see StoryCard.tsx) and
// broadcasts LANGUAGE_CHANGE_EVENT so cards already on the page update too.
export function LanguageToggle() {
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    const sync = () => setLanguage(getPreferredLanguage());
    sync();
    window.addEventListener(LANGUAGE_CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(LANGUAGE_CHANGE_EVENT, sync); window.removeEventListener("storage", sync); };
  }, []);

  function choose(next: Language) {
    setLanguage(next);
    setPreferredLanguage(next);
  }

  return (
    <div className="language-toggle" role="group" aria-label="Story language">
      <button type="button" aria-pressed={language === "en"} onClick={() => choose("en")}>
        EN
      </button>
      <button type="button" aria-pressed={language === "te"} onClick={() => choose("te")} lang="te">
        తె
      </button>
    </div>
  );
}
