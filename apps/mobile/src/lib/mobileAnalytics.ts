import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  getAnalytics,
  logEvent,
  resetAnalyticsData,
  setAnalyticsCollectionEnabled,
  setConsent,
} from "@react-native-firebase/analytics";
import { ANALYTICS_CONSENT_KEY } from "./storage";

// Separate from alert consent. On by default (ADR-051); only an explicit "false"
// stored by the Privacy toggle turns it off. Native firebase.json and Info.plist
// match that default so first-launch events are not lost.
let consent: boolean | null = null;

async function storedConsent(): Promise<boolean> {
  if (consent !== null) return consent;
  try {
    consent = (await AsyncStorage.getItem(ANALYTICS_CONSENT_KEY)) !== "false";
  } catch {
    consent = false;
  }
  return consent;
}

async function applyConsent(enabled: boolean): Promise<void> {
  if (!enabled) await setAnalyticsCollectionEnabled(getAnalytics(), false);
  // Advertising uses are never enabled by this reader analytics choice.
  await setConsent(getAnalytics(), {
    analytics_storage: enabled,
    ad_storage: false,
    ad_user_data: false,
    ad_personalization: false,
  });
  if (enabled) await setAnalyticsCollectionEnabled(getAnalytics(), true);
}

export async function initializeMobileAnalytics(): Promise<void> {
  await applyConsent(await storedConsent());
}

export async function getMobileAnalyticsConsent(): Promise<boolean> {
  return storedConsent();
}

export async function setMobileAnalyticsConsent(enabled: boolean): Promise<void> {
  if (!enabled) {
    consent = false;
    let failure: unknown;
    try {
      await AsyncStorage.setItem(ANALYTICS_CONSENT_KEY, "false");
    } catch (error) {
      failure = error;
    }
    try {
      await applyConsent(false);
    } catch (error) {
      failure ??= error;
    }
    if (failure) throw failure;
    return;
  }
  await AsyncStorage.setItem(ANALYTICS_CONSENT_KEY, "true");
  try {
    await applyConsent(true);
    consent = true;
  } catch (error) {
    consent = false;
    await AsyncStorage.setItem(ANALYTICS_CONSENT_KEY, "false");
    await applyConsent(false).catch(() => undefined);
    throw error;
  }
}

export async function clearMobileAnalyticsOnDeletion(): Promise<void> {
  consent = false;
  await applyConsent(false);
  await resetAnalyticsData(getAnalytics());
  await AsyncStorage.removeItem(ANALYTICS_CONSENT_KEY);
}

// Only coarse interaction names are sent: no story IDs, search text, user ID,
// notification payload, profile attributes, or free-form values.
const SAFE_EVENTS = new Set([
  "onboarding_complete", "feed_view", "story_open", "story_save", "story_share",
  "language_switch", "search", "notification_opt_in", "notification_open",
]);

export async function trackMobileEvent(event: string): Promise<void> {
  if (!SAFE_EVENTS.has(event) || !(await storedConsent())) return;
  try {
    await logEvent(getAnalytics(), event);
  } catch {
    // Analytics must never block the reader flow.
  }
}

// For test isolation after the in-memory AsyncStorage mock is cleared.
export function resetMobileAnalyticsConsentCacheForTest(): void {
  consent = null;
}
