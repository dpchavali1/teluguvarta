import type { Language } from "./onboarding";

export const PROFILE_STORAGE_KEY = "tg_onboarding_profile_v1";

export function normalizeStoryLanguage(value: unknown): Language {
  return value === "te" ? "te" : "en";
}

export function applyStoryLanguage(language: Language): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-story-language", language);
  }
}

// Select already-rendered bilingual copy before first paint. The preference
// stays in existing localStorage; English remains the no-script default.
export const STORY_LANGUAGE_INIT_SCRIPT = `(function(){var l="en";try{var p=JSON.parse(localStorage.getItem(${JSON.stringify(PROFILE_STORAGE_KEY)}));if(p&&p.language==="te")l="te";}catch(e){}document.documentElement.setAttribute("data-story-language",l);})();`;
