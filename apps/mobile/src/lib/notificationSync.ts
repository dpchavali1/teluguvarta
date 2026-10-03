import { updatePreferences } from "./api";
import type { NotificationPreferences } from "./storage";

function parseHour(hhmm: string): number | null {
  const hour = Number.parseInt(hhmm.split(":")[0] ?? "", 10);
  return Number.isFinite(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

// Best-effort server sync (T17 — see src/lib/storage.ts's note that quiet
// hours/max-per-day were on-device-only until this ticket wired the real
// backend up). Local storage stays the source of truth for the UI; a failed
// sync here (offline, etc) never blocks or reverts the local save.
export function syncToServer(prefs: NotificationPreferences): Promise<void> {
  return updatePreferences({
    topic_slugs: prefs.disableAll ? [] : Object.entries(prefs.topics).filter(([, enabled]) => enabled).map(([slug]) => slug),
    breaking_alerts_enabled: !prefs.disableAll && prefs.breakingEnabled,
    daily_briefing_enabled: !prefs.disableAll && prefs.dailyBriefingEnabled,
    quiet_hours_start: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursStart) : null,
    quiet_hours_end: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursEnd) : null,
    max_alerts_per_day: prefs.maxPerDay,
  }).then(() => undefined);
}
