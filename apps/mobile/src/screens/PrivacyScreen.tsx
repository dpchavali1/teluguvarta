import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { trackEvent } from "../lib/api";

// Mirrors apps/web/src/app/account/delete/page.tsx: no account system
// exists yet (ADR-006 proposed, not accepted), so "delete account" is
// "clear everything this app stored on this device" — onboarding profile,
// notification preferences, and saved stories. NON_NEGOTIABLES #9: this
// must exist both in-app and on the public website; T14 already covers the
// website side.
export function PrivacyScreen() {
  const [cleared, setCleared] = useState(false);

  async function handleClear() {
    trackEvent("account_delete_request");
    await AsyncStorage.removeMany([
      "tg_onboarded_v1",
      "tg_profile_v1",
      "tg_notification_prefs_v1",
      "tg_saved_stories_v1",
    ]);
    setCleared(true);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Privacy & delete account</Text>
      <Text style={styles.body}>
        Telugu Global does not currently require or offer account creation in this app — every
        story is readable without signing in, and your onboarding preferences and saved stories
        live only on this device.
      </Text>
      <Text style={styles.body}>
        You can clear all data this app has stored on this device below. When account creation
        ships, this screen will also delete your account and its data, as required by our privacy
        commitments.
      </Text>
      <Pressable
        onPress={handleClear}
        accessibilityRole="button"
        accessibilityLabel="Clear all data on this device"
        style={styles.button}
      >
        <Text>Clear all data on this device</Text>
      </Pressable>
      {cleared && (
        <Text accessibilityLiveRegion="polite" style={styles.status}>
          All data cleared on this device.
        </Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  title: { fontSize: 18, fontWeight: "700" },
  body: { fontSize: 15, color: "#444" },
  button: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
    alignSelf: "flex-start",
  },
  status: { color: "#0a0" },
});
