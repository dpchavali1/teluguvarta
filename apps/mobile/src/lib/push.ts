import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import {
  getMessaging,
  getToken,
  onTokenRefresh,
  registerDeviceForRemoteMessages,
  setAutoInitEnabled,
} from "@react-native-firebase/messaging";
import { Platform } from "react-native";

import { registerPushToken } from "./api";

// ADR-039: register a native FCM token only after OS notification permission.
// The native build starts FCM auto-init off in firebase.json.
export async function registerForPushNotificationsAsync(): Promise<void> {
  if (!Device.isDevice) return; // simulators/emulators have no push token
  try {
    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== "granted") {
      const requested = await Notifications.requestPermissionsAsync();
      status = requested.status;
    }
    const messaging = getMessaging();
    if (status !== "granted") {
      await setAutoInitEnabled(messaging, false);
      return;
    }
    await setAutoInitEnabled(messaging, true);
    if (Platform.OS === "ios") await registerDeviceForRemoteMessages(messaging);
    const token = await getToken(messaging);
    const platform = Platform.OS === "ios" ? "ios" : "android";
    await registerPushToken(token, platform);
  } catch (error) {
    console.warn("[push] failed to register push token", error);
  }
}

export function listenForPushTokenRefresh(): () => void {
  try {
    return onTokenRefresh(getMessaging(), (token) => {
      const platform = Platform.OS === "ios" ? "ios" : "android";
      registerPushToken(token, platform).catch(() => undefined);
    });
  } catch {
    return () => undefined;
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
