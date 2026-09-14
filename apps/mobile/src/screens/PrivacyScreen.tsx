import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { deleteAccount, trackEvent } from "../lib/api";
import { resetClientToken } from "../lib/identity";
import { spacing, typography, ui } from "../theme/tokens";

// T19 §16/§5.5: "delete account" now does two things — deletes the
// server-side `users` row this device's identity created since T17 (real
// account state: profile/push tokens/notification history — see
// apps/api/app/routers/me.py, cascades in Postgres) *and* clears everything
// this app stored on-device (onboarding profile, notification preferences,
// saved stories). NON_NEGOTIABLES #9: this must exist both in-app and on
// the public website; apps/web has no account/server-state concept at all
// (it never sends a client token), so its account/delete page is still
// on-device-only by design, not a gap.
export function PrivacyScreen() {
  const [cleared, setCleared] = useState(false);

  async function handleClear() {
    trackEvent("account_delete_request");
    try {
      await deleteAccount();
    } catch {
      // Best-effort: a network/server failure must not block clearing
      // on-device data below, which has no server dependency.
    }
    await resetClientToken();
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
        TTE does not require signing in — every story is readable without an account.
        This app does keep a device-scoped identity for notification preferences and push
        delivery, and your onboarding preferences and saved stories live on this device.
      </Text>
      <Text style={styles.body}>
        Deleting your account below removes that identity and everything tied to it (preferences,
        push tokens, notification history) from our servers, and clears all data this app has
        stored on this device.
      </Text>
      <Pressable
        onPress={handleClear}
        accessibilityRole="button"
        accessibilityLabel="Delete account and clear all data on this device"
        style={styles.button}
      >
        <Text>Delete account and clear data</Text>
      </Pressable>
      {cleared && (
        <Text accessibilityLiveRegion="polite" style={styles.status}>
          Account deleted and data cleared on this device.
        </Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.lg, gap: spacing.md },
  title: { ...typography.headline },
  body: { ...typography.body, color: ui.textSecondary },
  button: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 16,
    borderRadius: 8,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.danger,
    alignSelf: "flex-start",
  },
  status: { color: ui.success },
});
