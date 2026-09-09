import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";

import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getNotificationPreferences,
  setNotificationPreferences,
  type NotificationPreferences,
} from "../lib/storage";

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
