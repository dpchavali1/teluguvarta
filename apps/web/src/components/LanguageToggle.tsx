"use client";

import { useEffect, useState } from "react";

import { getPreferredLanguage, setPreferredLanguage, type Language } from "@/lib/onboarding";

// Design-review fix: web previously had no site-wide language preference —
// every StoryCard reset to English on every reload. This toggle sets the
// preference every StoryCard reads as its default (see StoryCard.tsx) and
// broadcasts LANGUAGE_CHANGE_EVENT so cards already on the page update too.
export function LanguageToggle() {
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    setLanguage(getPreferredLanguage());
  }, []);

  function choose(next: Language) {
    setLanguage(next);
    setPreferredLanguage(next);
  }

  return (
    <div className="language-toggle" role="group" aria-label="Site language">
      <button type="button" aria-pressed={language === "en"} onClick={() => choose("en")}>
        EN
      </button>
      <button type="button" aria-pressed={language === "te"} onClick={() => choose("te")} lang="te">
        తె
      </button>
    </div>
  );
}
