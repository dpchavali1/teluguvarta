import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getNotificationPreferences,
  getOnboarded,
  isStudentSegment,
  primaryLifeStageSegment,
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

// S1: onboarding's SCREAMING_SNAKE `LifeStage` must map to apps/api's
// lowercase `Segment` (app/schemas.py) exactly, and only the two student
// life stages count as "student" for the Student Briefing module.
//
// ADR-005 addendum (2026-09-09): a person can select more than one life
// stage; `primaryLifeStageSegment` resolves that list to the single value
// the API's `segment` param/why-matters cache actually key on — the first
// one selected, since this is the value most likely to reflect what the
// user picked first/cares most about.
test("primaryLifeStageSegment uses the first selected life stage", () => {
  expect(primaryLifeStageSegment(["INTERNATIONAL_STUDENT"])).toBe("international_student");
  expect(primaryLifeStageSegment(["GRADUATE_OPT"])).toBe("graduate_opt");
  expect(primaryLifeStageSegment(["PROFESSIONAL"])).toBe("professional");
  expect(primaryLifeStageSegment(["FAMILY_PARENT"])).toBe("family_parent");
  expect(primaryLifeStageSegment(["OTHER"])).toBe("other");
  expect(primaryLifeStageSegment([])).toBe("general");
  // Professional + Family/Parent: professional was selected first, so it's
  // the primary segment — but both still count for isStudentSegment below.
  expect(primaryLifeStageSegment(["PROFESSIONAL", "FAMILY_PARENT"])).toBe("professional");
});

test("isStudentSegment is true if any selected life stage is International Student or Graduate/OPT", () => {
  expect(isStudentSegment(["INTERNATIONAL_STUDENT"])).toBe(true);
  expect(isStudentSegment(["GRADUATE_OPT"])).toBe(true);
  expect(isStudentSegment(["PROFESSIONAL"])).toBe(false);
  expect(isStudentSegment(["FAMILY_PARENT"])).toBe(false);
  expect(isStudentSegment(["OTHER"])).toBe(false);
  expect(isStudentSegment([])).toBe(false);
  expect(isStudentSegment(["PROFESSIONAL", "GRADUATE_OPT"])).toBe(true);
});
