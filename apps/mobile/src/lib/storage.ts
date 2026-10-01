import AsyncStorage from "@react-native-async-storage/async-storage";
import { DeviceEventEmitter } from "react-native";

// §3.1/§16 (ADR-006 proposed, not accepted): V1 has no real account/auth
// backend for end users — `/v1/me/*` is still T04 stub data (see T14's
// PROGRESS.md note). Same judgment call as apps/web/src/lib/saved.ts:
// onboarding answers, notification preferences, and saved stories live on
// the device only. This is additive/reversible — swapping in a real
// account-backed store once ADR-006 ships is not a breaking change.

const KEYS = {
  onboarded: "tg_onboarded_v1",
  profile: "tg_profile_v1",
  notificationPrefs: "tg_notification_prefs_v1",
  savedStories: "tg_saved_stories_v1",
  themePreference: "tg_theme_pref_v1",
  textSize: "tg_text_size_v1",
  hiddenTopics: "tg_hidden_topics_v1",
  readHistory: "tg_read_history_v1",
} as const;

// Every on-device key "Delete account and clear data" must remove. A new key
// added to KEYS is cleared automatically (the client token lives in
// SecureStore and is reset separately by identity.ts).
export const LOCAL_DATA_KEYS: string[] = Object.values(KEYS);

export type LifeStage =
  | "INTERNATIONAL_STUDENT"
  | "GRADUATE_OPT"
  | "PROFESSIONAL"
  | "FAMILY_PARENT"
  | "OTHER";

export const LIFE_STAGES: { value: LifeStage; label: string }[] = [
  { value: "INTERNATIONAL_STUDENT", label: "International Student" },
  { value: "GRADUATE_OPT", label: "Graduate / OPT" },
  { value: "PROFESSIONAL", label: "Professional" },
  { value: "FAMILY_PARENT", label: "Family / Parent" },
  { value: "OTHER", label: "Other" },
];

// S1: apps/api's `Segment` (app/schemas.py) is lowercase snake_case; this
// storage module predates it and uses SCREAMING_SNAKE — map explicitly at
// the API boundary rather than changing either representation.
//
// ADR-005 addendum (2026-09-09): a person can pick more than one life stage
// (e.g. Professional + Family/Parent), but the backend's `segment` query
// param and the `story_why_matters_cache` table are still keyed on exactly
// one value — fragmenting that cache per combination isn't worth the AI-cost
// increase for what's just flavor text. The resolution rule: the *first*
// life stage the user selected (array order = selection order, since this
// module only ever appends) is the "primary segment" sent to the API for
// why-matters generation. Every selected life stage still drives
// on-device gating (see `isStudentSegment` below, which checks the whole
// array) — only the why-matters text is limited to one segment.
export function primaryLifeStageSegment(lifeStages: LifeStage[]): string {
  return lifeStages.length > 0 ? lifeStages[0].toLowerCase() : "general";
}

export function isStudentSegment(lifeStages: LifeStage[]): boolean {
  return lifeStages.includes("INTERNATIONAL_STUDENT") || lifeStages.includes("GRADUATE_OPT");
}

// The study-details questions are asked only of current international students.
export function asksStudentDetails(lifeStages: LifeStage[]): boolean {
  return lifeStages.includes("INTERNATIONAL_STUDENT");
}

// §3.1: conditional student sub-questions — deliberately no university name
// or immigration-document fields (NON_NEGOTIABLES: don't collect what isn't
// needed; immigration content itself is always human-reviewed, but that's
// separate from never asking a user for document-level immigration data).
export type StudentDetails = {
  studyCountry?: string;
  studyRegion?: string;
  studyMetro?: string;
  degreeLevel?: string;
  studentTopics?: string[];
};

export type OnboardingProfile = {
  residenceCountry?: string;
  homeRegion?: string;
  homeCity?: string;
  lifeStages: LifeStage[];
  student?: StudentDetails;
  interestTopicSlugs: string[];
  language: "en" | "te";
};

export const EMPTY_PROFILE: OnboardingProfile = {
  lifeStages: [],
  interestTopicSlugs: [],
  language: "en",
};

// §3.1/§9.2 notification preferences: independent per-topic toggles, quiet
// hours, max alert frequency, and a way to disable all notifications
// without disabling news access (i.e. `disableAll` never gates browsing —
// only push delivery, which T17 wires up for real).
export type NotificationPreferences = {
  topics: Record<string, boolean>;
  breakingEnabled: boolean;
  dailyBriefingEnabled: boolean;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  maxPerDay: number;
  disableAll: boolean;
};

export const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  topics: {},
  breakingEnabled: true,
  dailyBriefingEnabled: true,
  quietHoursEnabled: false,
  quietHoursStart: "22:00",
  quietHoursEnd: "07:00",
  maxPerDay: 5,
  disableAll: false,
};

async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return fallback;
    return { ...fallback, ...JSON.parse(raw) } as T;
  } catch {
    return fallback;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage disabled/full — preferences silently don't persist rather
    // than crashing the app.
  }
}

export async function getOnboarded(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(KEYS.onboarded)) === "true";
  } catch {
    return false;
  }
}

export async function setOnboarded(value: boolean): Promise<void> {
  try {
    await AsyncStorage.setItem(KEYS.onboarded, value ? "true" : "false");
  } catch {
    // ignore
  }
}

export function getProfile(): Promise<OnboardingProfile> {
  return readJson(KEYS.profile, EMPTY_PROFILE);
}

export function setProfile(profile: OnboardingProfile): Promise<void> {
  return writeJson(KEYS.profile, profile);
}

// Settings → "Your profile" saved new answers; Home reloads its personalized
// feed on this rather than waiting for its staleness timer.
export const PROFILE_CHANGE_EVENT = "tg:profile-change";

// Saves edited answers over the stored profile. Language is left as stored
// (it has its own screen), and student details are dropped once the student
// life stage is deselected so nothing unneeded stays on the device.
export async function saveProfileEdits(edits: Omit<OnboardingProfile, "language">): Promise<OnboardingProfile> {
  const current = await getProfile();
  const next: OnboardingProfile = { ...edits, language: current.language };
  if (!asksStudentDetails(next.lifeStages)) delete next.student;
  await setProfile(next);
  DeviceEventEmitter.emit(PROFILE_CHANGE_EVENT);
  return next;
}

// Design-review fix: apps/web broadcasts a language change so every visible
// StoryCard updates immediately (see LANGUAGE_CHANGE_EVENT in
// apps/web/src/lib/onboarding.ts); mobile's LanguageScreen previously only
// wrote to storage, so a card already on screen kept showing the old
// language until its next mount. DeviceEventEmitter is RN's equivalent of
// web's window.dispatchEvent — no new dependency needed.
export const LANGUAGE_CHANGE_EVENT = "tg:language-change";

// Reader's appearance choice. "system" follows the phone's light/dark setting.
export type ThemePreference = "system" | "light" | "dark";

export async function getThemePreference(): Promise<ThemePreference> {
  try {
    const raw = await AsyncStorage.getItem(KEYS.themePreference);
    return raw === "light" || raw === "dark" ? raw : "system";
  } catch {
    return "system";
  }
}

export async function setThemePreference(preference: ThemePreference): Promise<void> {
  try {
    await AsyncStorage.setItem(KEYS.themePreference, preference);
  } catch {
    // Storage disabled — the choice applies for this session only.
  }
}

// Reader's text size for story text (Settings → Text size), on top of the
// phone's own font scale.
export type TextSize = "small" | "default" | "large" | "xlarge";
const TEXT_SIZES: readonly TextSize[] = ["small", "default", "large", "xlarge"];

export async function getTextSize(): Promise<TextSize> {
  try {
    const raw = await AsyncStorage.getItem(KEYS.textSize);
    return TEXT_SIZES.find((size) => size === raw) ?? "default";
  } catch {
    return "default";
  }
}

export async function setTextSize(size: TextSize): Promise<void> {
  try {
    await AsyncStorage.setItem(KEYS.textSize, size);
  } catch {
    // Storage disabled — the choice applies for this session only.
  }
}

// Topic slugs the reader chose "Show less" on. Home and Latest leave out
// stories tagged with any of them; Settings → Hidden topics undoes it.
export async function getHiddenTopics(): Promise<string[]> {
  try {
    const parsed: unknown = JSON.parse((await AsyncStorage.getItem(KEYS.hiddenTopics)) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((slug): slug is string => typeof slug === "string") : [];
  } catch {
    return [];
  }
}

export async function setHiddenTopics(slugs: string[]): Promise<void> {
  return writeJson(KEYS.hiddenTopics, slugs);
}

// Plan M6: ids of stories opened on this device, newest first, capped.
export const READ_HISTORY_LIMIT = 200;

export async function getReadIds(): Promise<string[]> {
  try {
    const parsed: unknown = JSON.parse((await AsyncStorage.getItem(KEYS.readHistory)) ?? "[]");
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === "string").slice(0, READ_HISTORY_LIMIT)
      : [];
  } catch {
    return [];
  }
}

export async function setReadIds(ids: string[]): Promise<void> {
  return writeJson(KEYS.readHistory, ids.slice(0, READ_HISTORY_LIMIT));
}

export async function setLanguage(language: OnboardingProfile["language"]): Promise<void> {
  const profile = await getProfile();
  const next = { ...profile, language };
  await setProfile(next);
  DeviceEventEmitter.emit(LANGUAGE_CHANGE_EVENT, language);
}

export function getNotificationPreferences(): Promise<NotificationPreferences> {
  return readJson(KEYS.notificationPrefs, DEFAULT_NOTIFICATION_PREFERENCES);
}

export function setNotificationPreferences(prefs: NotificationPreferences): Promise<void> {
  return writeJson(KEYS.notificationPrefs, prefs);
}

async function readSavedIds(): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(KEYS.savedStories);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

async function writeSavedIds(ids: string[]): Promise<void> {
  await AsyncStorage.setItem(KEYS.savedStories, JSON.stringify(ids));
}

export async function getSavedIds(): Promise<string[]> {
  return readSavedIds();
}

export async function isSaved(storyId: string): Promise<boolean> {
  return (await readSavedIds()).includes(storyId);
}

async function updateSaved(storyId: string): Promise<boolean> {
  const ids = await readSavedIds();
  const index = ids.indexOf(storyId);
  if (index === -1) {
    ids.push(storyId);
    await writeSavedIds(ids);
    return true;
  }
  ids.splice(index, 1);
  await writeSavedIds(ids);
  return false;
}

// Serialize read/modify/write so rapid saves on different cards cannot lose IDs.
let savedWrite: Promise<unknown> = Promise.resolve();
export function toggleSaved(storyId: string): Promise<boolean> {
  const next = savedWrite.then(() => updateSaved(storyId));
  savedWrite = next.catch(() => undefined);
  return next;
}
