import { pushProjectId, resolveNotificationDeepLink } from "../lib/push";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: null, easConfig: { projectId: "eas-project" } },
}));

test("EAS project ID is available to push registration outside expoConfig.extra", () => {
  expect(pushProjectId()).toBe("eas-project");
});

// T17 deep-link acceptance criterion: opening a notification goes to its
// story; if there's no story or it's since become unavailable (the backend
// resolves the slug at send time in apps/api/app/jobs/notify.py and sends
// `null` when it can't), the client falls back to Home instead of erroring.
test("resolves a story notification to the StoryDetail route", () => {
  expect(resolveNotificationDeepLink({ type: "TOPIC_ALERT", story_slug: "some-story" })).toEqual({
    screen: "StoryDetail",
    slug: "some-story",
  });
});

test("falls back to Home for a daily briefing (no story)", () => {
  expect(resolveNotificationDeepLink({ type: "DAILY_BRIEFING", story_slug: null })).toEqual({ screen: "Home" });
});

test("falls back to Home when the story is unavailable/retracted", () => {
  expect(resolveNotificationDeepLink({ type: "BREAKING_ALERT", story_slug: undefined })).toEqual({ screen: "Home" });
});
