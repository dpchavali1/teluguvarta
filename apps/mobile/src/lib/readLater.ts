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
