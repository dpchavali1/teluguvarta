import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  logEvent,
  resetAnalyticsData,
  setAnalyticsCollectionEnabled,
  setConsent,
} from "@react-native-firebase/analytics";

import { trackEvent } from "../lib/api";
import {
  clearMobileAnalyticsOnDeletion,
  getMobileAnalyticsConsent,
  initializeMobileAnalytics,
  resetMobileAnalyticsConsentCacheForTest,
  setMobileAnalyticsConsent,
} from "../lib/mobileAnalytics";
import { ANALYTICS_CONSENT_KEY, LOCAL_DATA_KEYS } from "../lib/storage";

beforeEach(async () => {
  await AsyncStorage.clear();
  resetMobileAnalyticsConsentCacheForTest();
  jest.clearAllMocks();
});

test("collection is on by default (ADR-051) and sends only safe event names", async () => {
  await initializeMobileAnalytics();
  expect(await getMobileAnalyticsConsent()).toBe(true);
  expect(setAnalyticsCollectionEnabled).toHaveBeenCalledWith(expect.anything(), true);
  await trackEvent("story_open", { story_id: "private-story" });
  expect(logEvent).toHaveBeenCalledWith(expect.anything(), "story_open");
});

test("an explicit stored opt-out is respected on launch", async () => {
  await AsyncStorage.setItem(ANALYTICS_CONSENT_KEY, "false");
  await initializeMobileAnalytics();
  expect(await getMobileAnalyticsConsent()).toBe(false);
  expect(setAnalyticsCollectionEnabled).toHaveBeenCalledWith(expect.anything(), false);
  await trackEvent("story_open");
  expect(logEvent).not.toHaveBeenCalled();
});

test("opt-in sends only safe event names, never caller properties", async () => {
  await setMobileAnalyticsConsent(true);
  expect(setConsent).toHaveBeenCalledWith(expect.anything(), {
    analytics_storage: true,
    ad_storage: false,
    ad_user_data: false,
    ad_personalization: false,
  });
  await trackEvent("search", { query: "visa status" });
  expect(logEvent).toHaveBeenCalledWith(expect.anything(), "search");
  expect(jest.mocked(logEvent).mock.calls[0]).toHaveLength(2);
  await trackEvent("account_delete_request", { user_id: "private-user" });
  expect(logEvent).toHaveBeenCalledTimes(1);
});

test("revocation prevents later events and deletion resets the app identifier", async () => {
  await setMobileAnalyticsConsent(true);
  await setMobileAnalyticsConsent(false);
  await trackEvent("story_open");
  expect(logEvent).not.toHaveBeenCalled();
  expect(await AsyncStorage.getItem(ANALYTICS_CONSENT_KEY)).toBe("false");
  expect(LOCAL_DATA_KEYS).toContain(ANALYTICS_CONSENT_KEY);
  await clearMobileAnalyticsOnDeletion();
  expect(resetAnalyticsData).toHaveBeenCalledTimes(1);
  expect(await AsyncStorage.getItem(ANALYTICS_CONSENT_KEY)).toBeNull();
});

test("failed native opt-in does not persist consent", async () => {
  jest.mocked(setAnalyticsCollectionEnabled).mockRejectedValueOnce(new Error("native unavailable"));
  await expect(setMobileAnalyticsConsent(true)).rejects.toThrow("native unavailable");
  expect(await getMobileAnalyticsConsent()).toBe(false);
  expect(await AsyncStorage.getItem(ANALYTICS_CONSENT_KEY)).toBe("false");
});
