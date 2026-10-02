import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

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
function syncToServer(prefs: NotificationPreferences): Promise<void> {
  return updatePreferences({
    topic_slugs: prefs.disableAll ? [] : Object.entries(prefs.topics).filter(([, enabled]) => enabled).map(([slug]) => slug),
    breaking_alerts_enabled: !prefs.disableAll && prefs.breakingEnabled,
    daily_briefing_enabled: !prefs.disableAll && prefs.dailyBriefingEnabled,
    quiet_hours_start: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursStart) : null,
    quiet_hours_end: prefs.quietHoursEnabled ? parseHour(prefs.quietHoursEnd) : null,
    max_alerts_per_day: prefs.maxPerDay,
  }).then(() => undefined);
}

export function NotificationsScreen() {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [syncError, setSyncError] = useState(false);
  const syncQueue = useRef<Promise<void>>(Promise.resolve());
  const revision = useRef(0);

  function sync(next: NotificationPreferences) {
    const current = ++revision.current;
    setSyncError(false);
    // Serialize writes so a slow earlier request cannot overwrite a newer
    // preference on the server. Failed writes do not block a later retry.
    syncQueue.current = syncQueue.current.catch(() => {}).then(() => syncToServer(next));
    syncQueue.current.then(
      () => { if (current === revision.current) setSyncError(false); },
      () => { if (current === revision.current) setSyncError(true); },
    );
  }

  useEffect(() => {
    let active = true;
    getNotificationPreferences().then((saved) => {
      if (!active) return;
      setPrefs(saved);
      sync(saved); // Reconcile changes made while offline on the next visit.
    });
    return () => { active = false; };
    // `sync` only uses component refs/state setters; run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    sync(next);
  }

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
      <Text style={styles.title} accessibilityRole="header">Choose your alerts</Text>
      <Text style={styles.intro}>Pick the updates you want. These settings are saved on this device and used for push alerts when delivery is available.</Text>
      {syncError ? <View style={styles.syncError} accessibilityRole="alert">
        <Text style={styles.syncErrorText}>Couldn&apos;t sync alert settings. Earlier alerts may still arrive until you retry.</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Retry syncing alert settings" onPress={() => sync(prefs)} style={styles.retryButton}>
          <Text style={styles.retryText}>Retry sync</Text>
        </Pressable>
      </View> : null}
      <NotificationPreferencesForm value={prefs ?? DEFAULT_NOTIFICATION_PREFERENCES} onChange={handleChange} />
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"]) {
  return StyleSheet.create({
    container: { padding: 16, backgroundColor: colors.bg },
    title: { fontSize: 24, fontWeight: "700", color: colors.text, marginBottom: 6 },
    intro: { fontSize: 15, lineHeight: 21, color: colors.muted, marginBottom: 20 },
    syncError: { backgroundColor: colors.dangerSoft, borderRadius: 12, padding: 12, marginBottom: 16, gap: 8 },
    syncErrorText: { color: colors.danger, fontSize: 14, lineHeight: 20 },
    retryButton: { minHeight: 44, alignSelf: "flex-start", justifyContent: "center", paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: colors.danger },
    retryText: { color: colors.danger, fontWeight: "700" },
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  });
}
