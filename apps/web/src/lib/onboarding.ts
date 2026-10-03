// S1: web has no account system (NON_NEGOTIABLES #9 — browsing works
// without login), so life-stage/preferences live in the browser only, same
// judgment call as ./saved.ts and apps/mobile/src/lib/storage.ts. Life-stage
// values match apps/api's `Segment` (app/schemas.py) directly — unlike
// apps/mobile's storage.ts, there's no legacy SCREAMING_SNAKE format to map.
import type { PersonaState } from "@teluguvarta/domain";
import { applyStoryLanguage, normalizeStoryLanguage, PROFILE_STORAGE_KEY } from "./storyLanguage";

const STORAGE_KEY = PROFILE_STORAGE_KEY;

export type LifeStage =
  | "international_student"
  | "graduate_opt"
  | "professional"
  | "family_parent"
  | "other";

export const LIFE_STAGES: { value: LifeStage; label: string }[] = [
  { value: "international_student", label: "International Student" },
  { value: "graduate_opt", label: "Graduate / OPT" },
  { value: "professional", label: "Professional" },
  { value: "family_parent", label: "Family / Parent" },
  { value: "other", label: "Other" },
];

export type Language = "en" | "te";

export type OnboardingProfile = {
  lifeStages: LifeStage[];
  topics: string[];
  residenceCountry?: string;
  homeState?: string;
  homeCity?: string;
  // P01: what each applied persona preset added, so unchecking it reverts
  // only its own choices. Local only; never sent to the server.
  personaApplied?: PersonaState["applied"];
  // Design-review fix: previously there was no site-wide language
  // preference at all — every StoryCard defaulted to "en" and reset on
  // every reload. Mirrors apps/mobile/src/lib/storage.ts's profile.language.
  language: Language;
};

const EMPTY_PROFILE: OnboardingProfile = { lifeStages: [], topics: [], language: "en" };

export const LANGUAGE_CHANGE_EVENT = "tg:language-change";
let sessionLanguage: Language | null = null;

export function getPreferredLanguage(): Language {
  return sessionLanguage ?? normalizeStoryLanguage(getOnboardingProfile().language);
}

// A relevant change in another tab supersedes a choice held in this tab.
export function refreshPreferredLanguage(): Language {
  sessionLanguage = null;
  return getPreferredLanguage();
}

export function setPreferredLanguage(language: Language): void {
  setOnboardingProfile({ ...getOnboardingProfile(), language });
}

export function getOnboardingProfile(): OnboardingProfile {
  if (typeof window === "undefined") return EMPTY_PROFILE;
  let profile = EMPTY_PROFILE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) profile = { ...EMPTY_PROFILE, ...JSON.parse(raw) } as OnboardingProfile;
  } catch {
    // Keep the current session's language even when storage is unavailable.
  }
  return { ...profile, language: sessionLanguage ?? normalizeStoryLanguage(profile.language) };
}

export function setOnboardingProfile(profile: OnboardingProfile): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // Private browsing / storage disabled — onboarding silently doesn't
    // persist rather than breaking the page.
  }
  // Reflect the choice for this session even when storage cannot persist it.
  const language = normalizeStoryLanguage(profile.language);
  sessionLanguage = language;
  applyStoryLanguage(language);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<Language>(LANGUAGE_CHANGE_EVENT, { detail: language }));
  }
}

// §3.5 / docs/tickets/S1.md: student signals come only from what the user
// explicitly selected here — never inferred from reading behavior.
export function isStudentLifeStage(lifeStages: LifeStage[] | null | undefined): boolean {
  return !!lifeStages && (lifeStages.includes("international_student") || lifeStages.includes("graduate_opt"));
}

// ADR-005 addendum (2026-09-09), mirrored from apps/mobile/src/lib/storage.ts
// primaryLifeStageSegment: a person can select more than one life stage
// (e.g. Professional + Family/Parent) but the backend's `segment` query
// param is still keyed on exactly one value, so the *first* life stage the
// user selected (array order = selection order) is what's sent as the
// personalization segment. Every selected life stage still drives on-device
// gating (see isStudentLifeStage above, which checks the whole array).
export function primaryLifeStageSegment(lifeStages: LifeStage[]): string | null {
  const [first] = lifeStages;
  return first ?? null;
}
