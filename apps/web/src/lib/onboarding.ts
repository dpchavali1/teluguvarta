// S1: web has no account system (NON_NEGOTIABLES #9 — browsing works
// without login), so life-stage/preferences live in the browser only, same
// judgment call as ./saved.ts and apps/mobile/src/lib/storage.ts. Life-stage
// values match apps/api's `Segment` (app/schemas.py) directly — unlike
// apps/mobile's storage.ts, there's no legacy SCREAMING_SNAKE format to map.
const STORAGE_KEY = "tg_onboarding_profile_v1";

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

export type OnboardingProfile = {
  lifeStages: LifeStage[];
  residenceCountry?: string;
  homeState?: string;
  homeCity?: string;
};

const EMPTY_PROFILE: OnboardingProfile = { lifeStages: [] };

export function getOnboardingProfile(): OnboardingProfile {
  if (typeof window === "undefined") return EMPTY_PROFILE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_PROFILE;
    return { ...EMPTY_PROFILE, ...JSON.parse(raw) } as OnboardingProfile;
  } catch {
    return EMPTY_PROFILE;
  }
}

export function setOnboardingProfile(profile: OnboardingProfile): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // Private browsing / storage disabled — onboarding silently doesn't
    // persist rather than breaking the page.
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
