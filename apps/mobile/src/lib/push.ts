import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import {
  getInitialNotification,
  getMessaging,
  getToken,
  onMessage,
  onNotificationOpenedApp,
  onTokenRefresh,
  registerDeviceForRemoteMessages,
  setAutoInitEnabled,
} from "@react-native-firebase/messaging";
import { Platform } from "react-native";

import { registerPushToken } from "./api";

// ADR-050: must match ANDROID_CHANNEL_ID in apps/api/app/push.py and the
// `defaultChannel` of the expo-notifications plugin in app.json.
export const ANDROID_CHANNEL_ID = "alerts";
const FOREGROUND_FLAG = "tte_foreground";

// Android otherwise has no channel for FCM notifications to land in, so
// they use a default low-importance one. Idempotent; call at startup.
export async function ensureAndroidAlertChannel(): Promise<void> {
  if (Platform.OS !== "android") return;
  try {
    await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
      name: "Alerts",
      importance: Notifications.AndroidImportance.HIGH,
    });
  } catch (error) {
    console.warn("[push] failed to create notification channel", error);
  }
}

// FCM does not display a notification while the Android app is open. Show it
// ourselves (an immediate local notification) and route its tap like a
// background tap. `onTap` receives the original FCM data.
export function listenForForegroundMessages(onTap: (data: NotificationDeepLinkData) => void): () => void {
  if (Platform.OS !== "android") return () => undefined;
  let stopMessages: () => void = () => undefined;
  let tapSub: { remove: () => void } | null = null;
  try {
    stopMessages = onMessage(getMessaging(), async (message) => {
      const title = message.notification?.title;
      const body = message.notification?.body;
      if (!title && !body) return;
      try {
        await Notifications.scheduleNotificationAsync({
          content: {
            title: title ?? undefined,
            body: body ?? undefined,
            data: { ...(message.data ?? {}), [FOREGROUND_FLAG]: "1" },
          },
          trigger: null,
        });
      } catch (error) {
        console.warn("[push] failed to show foreground notification", error);
      }
    });
    tapSub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as Record<string, unknown> | undefined;
      if (data?.[FOREGROUND_FLAG] !== "1") return;
      const { [FOREGROUND_FLAG]: _flag, ...rest } = data;
      onTap(rest as NotificationDeepLinkData);
    });
  } catch {
    // Firebase unavailable (e.g. a build without google-services): nothing to listen to.
  }
  return () => {
    stopMessages();
    tapSub?.remove();
  };
}

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

// Taps on FCM notifications reach JS through Firebase, not expo-notifications:
// onNotificationOpenedApp covers background, getInitialNotification a cold start.
export function listenForNotificationOpens(onOpen: (data: NotificationDeepLinkData) => void): () => void {
  try {
    const messaging = getMessaging();
    let active = true;
    getInitialNotification(messaging)
      .then((message) => {
        if (active && message) onOpen((message.data ?? {}) as NotificationDeepLinkData);
      })
      .catch(() => undefined);
    const unsubscribe = onNotificationOpenedApp(messaging, (message) =>
      onOpen((message.data ?? {}) as NotificationDeepLinkData)
    );
    return () => {
      active = false;
      unsubscribe();
    };
  } catch {
    return () => undefined;
  }
}

export type NotificationDeepLinkData = {
  type?: "DAILY_BRIEFING" | "TOPIC_ALERT" | "BREAKING_ALERT" | "TRACKER_UPDATE" | "DIGEST" | "STORY_UPDATE";
  story_slug?: string | null;
};

export type DeepLinkRoute = { screen: "StoryDetail"; slug: string } | { screen: "Trackers" } | { screen: "Home" };

// Pure — no navigation/fetch here — so it's unit-testable without a device.
// A missing/null slug (DAILY_BRIEFING, or a story that's since become
// unavailable per apps/api/app/jobs/notify.py's canonical_slug lookup)
// falls back to Home instead of erroring, per the ticket's deep-link
// acceptance criterion. DIGEST (no single story) opens Home; STORY_UPDATE
// opens the corrected story via its slug.
export function resolveNotificationDeepLink(data: NotificationDeepLinkData): DeepLinkRoute {
  if (data.story_slug) return { screen: "StoryDetail", slug: data.story_slug };
  if (data.type === "TRACKER_UPDATE") return { screen: "Trackers" };
  return { screen: "Home" };
}
