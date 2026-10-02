import * as Notifications from "expo-notifications";
import { getToken, setAutoInitEnabled } from "@react-native-firebase/messaging";
import { registerPushToken } from "../lib/api";
import { registerForPushNotificationsAsync, resolveNotificationDeepLink } from "../lib/push";

jest.mock("expo-device", () => ({ isDevice: true }));
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(async () => ({ status: "granted" })),
  requestPermissionsAsync: jest.fn(async () => ({ status: "granted" })),
}));
jest.mock("../lib/api", () => ({ registerPushToken: jest.fn(async () => undefined) }));

test("granted notification permission registers an FCM token", async () => {
  await registerForPushNotificationsAsync();
  expect(setAutoInitEnabled).toHaveBeenCalledWith(expect.anything(), true);
  expect(getToken).toHaveBeenCalled();
  expect(registerPushToken).toHaveBeenCalledWith("fcm-device-token", expect.stringMatching(/ios|android/));
});

test("denied permission leaves FCM initialization off and registers nothing", async () => {
  jest.mocked(Notifications.getPermissionsAsync).mockResolvedValueOnce({ status: "denied" } as never);
  jest.mocked(Notifications.requestPermissionsAsync).mockResolvedValueOnce({ status: "denied" } as never);
  jest.clearAllMocks();
  await registerForPushNotificationsAsync();
  expect(setAutoInitEnabled).toHaveBeenCalledWith(expect.anything(), false);
  expect(getToken).not.toHaveBeenCalled();
  expect(registerPushToken).not.toHaveBeenCalled();
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
