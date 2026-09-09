import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getNotificationPreferences,
  getOnboarded,
  setNotificationPreferences,
  setOnboarded,
  type NotificationPreferences,
} from "../lib/storage";

// T15 acceptance criterion: "notification preference toggles persist and are
// independently controllable" — topic toggles, breaking/daily-briefing,
// quiet hours, max/day, and disable-all (which must never gate browsing,
// only push delivery — enforced by construction: nothing in this module
// reads `disableAll` anywhere near feed/story fetching).
test("notification preferences persist independently across each field", async () => {
  expect(await getNotificationPreferences()).toEqual(DEFAULT_NOTIFICATION_PREFERENCES);

  const next: NotificationPreferences = {
    topics: { immigration: false, sports: true },
    breakingEnabled: false,
    dailyBriefingEnabled: true,
    quietHoursEnabled: true,
    quietHoursStart: "23:00",
    quietHoursEnd: "06:00",
    maxPerDay: 2,
    disableAll: false,
  };
  await setNotificationPreferences(next);

  expect(await getNotificationPreferences()).toEqual(next);
});

test("disable-all can be toggled independently without touching other fields", async () => {
  const base: NotificationPreferences = {
    ...DEFAULT_NOTIFICATION_PREFERENCES,
    topics: { immigration: true },
    maxPerDay: 3,
  };
  await setNotificationPreferences(base);

  const disabled: NotificationPreferences = { ...base, disableAll: true };
  await setNotificationPreferences(disabled);

  const stored = await getNotificationPreferences();
  expect(stored.disableAll).toBe(true);
  expect(stored.topics).toEqual({ immigration: true });
  expect(stored.maxPerDay).toBe(3);
});

test("onboarded flag defaults to false and persists once set", async () => {
  expect(await getOnboarded()).toBe(false);
  await setOnboarded(true);
  expect(await getOnboarded()).toBe(true);
});
