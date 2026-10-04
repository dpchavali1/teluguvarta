import * as Notifications from "expo-notifications";

// P06 / ADR-044: a local "read later" notification. No server involvement;
// returns null when the OS permission is not granted.
export async function scheduleReadLater(storySlug: string, headline: string, at: number): Promise<string | null> {
  try {
    const existing = await Notifications.getPermissionsAsync();
    const status = existing.status === "granted" ? "granted" : (await Notifications.requestPermissionsAsync()).status;
    if (status !== "granted") return null;
    return await Notifications.scheduleNotificationAsync({
      content: { title: "Read later", body: headline, data: { story_slug: storySlug } },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: new Date(at) },
    });
  } catch {
    return null;
  }
}

export async function cancelReadLater(notificationId: string): Promise<void> {
  try {
    await Notifications.cancelScheduledNotificationAsync(notificationId);
  } catch {
    // Already fired or cancelled.
  }
}

// Taps on read-later reminders reach JS through expo-notifications (FCM pushes
// come through Firebase, see `listenForNotificationOpens`). Push triggers are
// ignored here so a push is never opened twice. getLastNotificationResponseAsync
// covers a cold start; `handled` stops the same tap being applied twice.
export function listenForReadLaterOpens(onOpen: (data: { story_slug?: string | null }) => void): () => void {
  const handled = new Set<string>();
  const handle = (response: Notifications.NotificationResponse | null | undefined) => {
    if (!response) return;
    const request = response.notification.request;
    const trigger = request.trigger as { type?: string } | null;
    if (trigger?.type === "push" || handled.has(request.identifier)) return;
    const data = request.content.data as { story_slug?: unknown; tte_foreground?: unknown } | undefined;
    if (data?.tte_foreground === "1") return; // a foreground push; push.ts routes it
    const slug = data?.story_slug;
    if (typeof slug !== "string" || !slug) return;
    handled.add(request.identifier);
    onOpen({ story_slug: slug });
  };
  let active = true;
  try {
    Notifications.getLastNotificationResponseAsync()
      .then((response) => {
        if (active) handle(response);
      })
      .catch(() => undefined);
    const sub = Notifications.addNotificationResponseReceivedListener(handle);
    return () => {
      active = false;
      sub.remove();
    };
  } catch {
    return () => undefined;
  }
}
