import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";

import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import { trackEvent, updatePreferences } from "../lib/api";
import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getNotificationPreferences,
  setNotificationPreferences,
  type NotificationPreferences,
} from "../lib/storage";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

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
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
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
    // "opt in" is specifically re-enabling the master switch after having
    // turned it off — not every individual topic/breaking/daily toggle,
    // most of which start (and often stay) on by default.
    if (prefs?.disableAll && !next.disableAll) {
      trackEvent("notification_opt_in");
    }
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

function createStyles(colors: AppTheme["colors"]) {
  return StyleSheet.create({
    container: { padding: 16, backgroundColor: colors.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  });
}
