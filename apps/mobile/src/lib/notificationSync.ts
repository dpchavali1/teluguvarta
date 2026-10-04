import { updatePreferences } from "./api";
import { getFollowedExams, getFollowedPlaces, getFollowedVisa, getNotificationPreferences, getSavedIds, type NotificationPreferences } from "./storage";

function parseHour(hhmm: string): number | null {
  const hour = Number.parseInt(hhmm.split(":")[0] ?? "", 10);
  return Number.isFinite(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

// Best-effort server sync (T17 — see src/lib/storage.ts's note that quiet
// hours/max-per-day were on-device-only until this ticket wired the real
// backend up). Local storage stays the source of truth for the UI; a failed
// sync here (offline, etc) never blocks or reverts the local save.
export async function syncToServer(prefs: NotificationPreferences): Promise<void> {
  // "Disable all" also clears the lists the server alerts from (ADR-042).
  const off = prefs.disableAll;
  const topicSlugs = off ? [] : Object.entries(prefs.topics).filter(([, enabled]) => enabled).map(([slug]) => slug);
  const savedIds = off ? [] : (await getSavedIds()).slice(-200);
  const followedPlaces = off ? [] : await getFollowedPlaces();
  const followedVisa = off ? [] : await getFollowedVisa();
  const followedExams = off ? [] : await getFollowedExams();
  await updatePreferences({
    topic_slugs: topicSlugs,
    topic_urgency: Object.fromEntries(topicSlugs.map((slug) => [slug, prefs.topicUrgency[slug] ?? "INSTANT"])),
    keywords: off ? [] : prefs.keywords,
    saved_story_ids: savedIds,
    follow_places: followedPlaces.map((p) => ({ place_id: p.placeId, alerts: p.alerts })),
    follow_visa: followedVisa,
    follow_exams: followedExams,
    breaking_alerts_enabled: !off && prefs.breakingEnabled,
    daily_briefing_enabled: !off && prefs.dailyBriefingEnabled,
    digest_morning_hour: off ? null : prefs.digestMorningHour,
    digest_evening_hour: off ? null : prefs.digestEveningHour,
    home_tz: prefs.homeTz,
    residence_tz: prefs.residenceTz,
    quiet_hours_start: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursStart) : null,
    quiet_hours_end: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursEnd) : null,
    max_alerts_per_day: prefs.maxPerDay,
  });
}

// After a save/unsave: re-send so the server knows which saved stories to
// alert about. Best-effort; local storage stays the source of truth.
export function syncSavedStories(): void {
  getNotificationPreferences().then(syncToServer).catch(() => {});
}
