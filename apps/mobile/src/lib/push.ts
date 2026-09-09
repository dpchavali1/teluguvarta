import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { registerPushToken } from "./api";

// T17 §10.1: register this device with the backend so `notification_dispatch`
// (apps/api/app/jobs/notify.py) has somewhere to deliver to. Every failure
// mode here (no physical device, permission denied, no EAS project
// configured yet) degrades to "push just doesn't work on this build"
// instead of crashing the app — matches the on-device-storage try/catch
// posture already used throughout src/lib/storage.ts.
export async function registerForPushNotificationsAsync(): Promise<void> {
  if (!Device.isDevice) return; // simulators/emulators have no push token

  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== "granted") {
    const requested = await Notifications.requestPermissionsAsync();
    status = requested.status;
  }
  if (status !== "granted") return;

  const projectId = Constants.expoConfig?.extra?.eas?.projectId;
  if (!projectId) {
    // No EAS project configured yet (see app.json) — expected until this
    // app is set up with `eas init`; registration is a no-op until then.
    console.warn("[push] skipping push-token registration: no EAS projectId configured");
    return;
  }

  try {
    const { data: expoPushToken } = await Notifications.getExpoPushTokenAsync({ projectId });
    const platform = Platform.OS === "ios" ? "ios" : "android";
    await registerPushToken(expoPushToken, platform);
  } catch (error) {
    console.warn("[push] failed to register push token", error);
  }
}

export type NotificationDeepLinkData = {
  type?: "DAILY_BRIEFING" | "TOPIC_ALERT" | "BREAKING_ALERT";
  story_slug?: string | null;
};

export type DeepLinkRoute = { screen: "StoryDetail"; slug: string } | { screen: "Home" };

// Pure — no navigation/fetch here — so it's unit-testable without a device.
// A missing/null slug (DAILY_BRIEFING, or a story that's since become
// unavailable per apps/api/app/jobs/notify.py's canonical_slug lookup)
// falls back to Home instead of erroring, per the ticket's deep-link
// acceptance criterion.
export function resolveNotificationDeepLink(data: NotificationDeepLinkData): DeepLinkRoute {
  if (data.story_slug) return { screen: "StoryDetail", slug: data.story_slug };
  return { screen: "Home" };
}
