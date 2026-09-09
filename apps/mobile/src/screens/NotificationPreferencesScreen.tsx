import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";

import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import { updatePreferences } from "../lib/api";
import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getNotificationPreferences,
  setNotificationPreferences,
  type NotificationPreferences,
} from "../lib/storage";

function parseHour(hhmm: string): number | null {
  const hour = Number.parseInt(hhmm.split(":")[0] ?? "", 10);
  return Number.isFinite(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

// Best-effort server sync (T17 — see src/lib/storage.ts's note that quiet
// hours/max-per-day were on-device-only until this ticket wired the real
// backend up). Local storage stays the source of truth for the UI; a failed
// sync here (offline, etc) never blocks or reverts the local save.
function syncToServer(prefs: NotificationPreferences): void {
  updatePreferences({
    topic_slugs: prefs.disableAll ? [] : Object.entries(prefs.topics).filter(([, enabled]) => enabled).map(([slug]) => slug),
    breaking_alerts_enabled: !prefs.disableAll && prefs.breakingEnabled,
    daily_briefing_enabled: !prefs.disableAll && prefs.dailyBriefingEnabled,
    quiet_hours_start: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursStart) : null,
    quiet_hours_end: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursEnd) : null,
    max_alerts_per_day: prefs.maxPerDay,
  }).catch(() => {
    // ignore — see comment above
  });
}

export function NotificationPreferencesScreen() {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);

  useEffect(() => {
    getNotificationPreferences().then(setPrefs);
  }, []);

  if (!prefs) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading preferences" />
      </View>
    );
  }

  function handleChange(next: NotificationPreferences) {
    setPrefs(next);
    setNotificationPreferences(next);
    syncToServer(next);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <NotificationPreferencesForm value={prefs ?? DEFAULT_NOTIFICATION_PREFERENCES} onChange={handleChange} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
