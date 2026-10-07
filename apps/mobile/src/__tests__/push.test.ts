import * as Notifications from "expo-notifications";
import { getInitialNotification, getToken, onMessage, onNotificationOpenedApp, setAutoInitEnabled } from "@react-native-firebase/messaging";
import { Platform } from "react-native";
import { registerPushToken } from "../lib/api";
import {
  ensureAndroidAlertChannel,
  listenForForegroundMessages,
  listenForNotificationOpens,
  registerForPushNotificationsAsync,
  resolveNotificationDeepLink,
} from "../lib/push";

jest.mock("expo-device", () => ({ isDevice: true }));
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(async () => ({ status: "granted" })),
  requestPermissionsAsync: jest.fn(async () => ({ status: "granted" })),
  setNotificationChannelAsync: jest.fn(async () => null),
  scheduleNotificationAsync: jest.fn(async () => "local-id"),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  AndroidImportance: { HIGH: 4 },
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

describe("listenForNotificationOpens", () => {
  it("delivers a cold-start tap and background taps, and unsubscribes", async () => {
    const unsubscribe = jest.fn();
    let backgroundHandler: (m: { data?: Record<string, string> }) => void = () => undefined;
    jest.mocked(getInitialNotification).mockResolvedValueOnce({ data: { story_slug: "cold" } } as never);
    jest.mocked(onNotificationOpenedApp).mockImplementationOnce(((_m: unknown, handler: typeof backgroundHandler) => {
      backgroundHandler = handler;
      return unsubscribe;
    }) as never);
    const onOpen = jest.fn();
    const stop = listenForNotificationOpens(onOpen);
    await new Promise<void>((resolve) => setImmediate(() => resolve()));
    expect(onOpen).toHaveBeenCalledWith({ story_slug: "cold" });
    backgroundHandler({ data: { story_slug: "warm" } });
    expect(onOpen).toHaveBeenCalledWith({ story_slug: "warm" });
    stop();
    expect(unsubscribe).toHaveBeenCalled();
  });
});

describe("tracker deep link", () => {
  it("opens Trackers for TRACKER_UPDATE with no story", () => {
    expect(resolveNotificationDeepLink({ type: "TRACKER_UPDATE", story_slug: null })).toEqual({ screen: "Trackers" });
  });
});

describe("deep link types", () => {
  it("routes DIGEST to Home and STORY_UPDATE to its story", () => {
    expect(resolveNotificationDeepLink({ type: "DIGEST", story_slug: null })).toEqual({ screen: "Home" });
    expect(resolveNotificationDeepLink({ type: "STORY_UPDATE", story_slug: "fixed" })).toEqual({
      screen: "StoryDetail",
      slug: "fixed",
    });
  });
});

describe("android channel and foreground messages", () => {
  const originalOS = Platform.OS;
  afterEach(() => {
    Platform.OS = originalOS;
    jest.clearAllMocks();
  });

  it("creates a high-importance alerts channel on Android only", async () => {
    await ensureAndroidAlertChannel();
    expect(Notifications.setNotificationChannelAsync).not.toHaveBeenCalled();
    Platform.OS = "android";
    await ensureAndroidAlertChannel();
    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith("alerts", { name: "Alerts", importance: 4 });
  });

  it("shows a foreground FCM message locally, routes its tap, and unsubscribes", async () => {
    Platform.OS = "android";
    const unsubscribeMessages = jest.fn();
    const removeTap = jest.fn();
    let messageHandler: (m: unknown) => Promise<void> = async () => undefined;
    let tapHandler: (r: unknown) => void = () => undefined;
    jest.mocked(onMessage).mockImplementationOnce(((_m: unknown, handler: typeof messageHandler) => {
      messageHandler = handler;
      return unsubscribeMessages;
    }) as never);
    jest.mocked(Notifications.addNotificationResponseReceivedListener).mockImplementationOnce(((handler: typeof tapHandler) => {
      tapHandler = handler;
      return { remove: removeTap };
    }) as never);
    const onTap = jest.fn();
    const stop = listenForForegroundMessages(onTap);

    await messageHandler({ notification: { title: "Breaking", body: "Body" }, data: { type: "BREAKING_ALERT", story_slug: "s" } });
    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith({
      content: { title: "Breaking", body: "Body", data: { type: "BREAKING_ALERT", story_slug: "s", tte_foreground: "1" } },
      trigger: null,
    });

    tapHandler({ notification: { request: { content: { data: { story_slug: "other" } } } } }); // not ours
    expect(onTap).not.toHaveBeenCalled();
    tapHandler({ notification: { request: { content: { data: { type: "BREAKING_ALERT", story_slug: "s", tte_foreground: "1" } } } } });
    expect(onTap).toHaveBeenCalledWith({ type: "BREAKING_ALERT", story_slug: "s" });

    stop();
    expect(unsubscribeMessages).toHaveBeenCalled();
    expect(removeTap).toHaveBeenCalled();
  });

  it("does nothing on iOS", () => {
    listenForForegroundMessages(jest.fn())();
    expect(onMessage).not.toHaveBeenCalled();
  });
});
