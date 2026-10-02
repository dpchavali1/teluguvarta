import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { deleteAccount, trackEvent } from "../lib/api";
import { useHiddenTopics } from "../lib/HiddenTopicsContext";
import { resetClientToken } from "../lib/identity";
import { LOCAL_DATA_KEYS } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { useTextSize } from "../theme/TextSizeContext";
import { useThemePreference } from "../theme/ThemePreferenceContext";
import { spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

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
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const [cleared, setCleared] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const serverDeleted = useRef(false);
  const { resetPreference: resetThemePreference } = useThemePreference();
  const { resetTextSize } = useTextSize();
  const { resetHiddenTopics } = useHiddenTopics();
  const { resetLocalData } = useStoryCache();

  async function handleClear() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setCleared(false);
    trackEvent("account_delete_request");
    try {
      // ADR-033 A: retain the identity and choices if server deletion fails.
      if (!serverDeleted.current) {
        await deleteAccount();
        serverDeleted.current = true;
      }
      await AsyncStorage.removeMany(LOCAL_DATA_KEYS);
      await resetClientToken(true);
      resetThemePreference();
      resetTextSize();
      resetHiddenTopics();
      resetLocalData();
      // A later deletion must confirm the identity then in use. Only a failed
      // cleanup retains confirmation so it can finish the same operation.
      serverDeleted.current = false;
      setCleared(true);
    } catch {
      setError(serverDeleted.current
        ? "Account deleted, but some data on this device couldn’t be cleared. Try again to finish clearing it."
        : "Couldn’t delete your account. Your data and identity have been kept so you can retry. Check your connection and try again.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
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
        disabled={busy}
        accessibilityState={{ disabled: busy, busy }}
        style={styles.button}
      >
        <Text style={styles.buttonText}>{busy ? "Deleting…" : "Delete account and clear data"}</Text>
      </Pressable>
      <Text style={styles.body}>If server deletion fails, your data stays on this phone so you can try again.</Text>
      {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
      {cleared && (
        <Text accessibilityLiveRegion="polite" style={styles.status}>
          Account deleted and data cleared on this device.
        </Text>
      )}
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flexGrow: 1, padding: spacing.lg, gap: spacing.md, backgroundColor: colors.bg },
    title: { ...typography.headline, color: colors.text },
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
    buttonText: { color: ui.danger, fontWeight: "600" },
    status: { color: ui.success },
    error: { color: ui.danger },
  });
}
