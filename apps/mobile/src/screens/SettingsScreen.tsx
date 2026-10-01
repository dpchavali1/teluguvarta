import Ionicons from "@expo/vector-icons/Ionicons";
import Constants from "expo-constants";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useMemo } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { siteUrl } from "../lib/api";
import type { TextSize, ThemePreference } from "../lib/storage";
import type { RootStackParamList } from "../navigation/types";
import { useTextSize } from "../theme/TextSizeContext";
import { useThemePreference } from "../theme/ThemePreferenceContext";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

export function SettingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { preference, setPreference } = useThemePreference();
  const { textSize, setTextSize } = useTextSize();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.groupLabel}>GENERAL</Text>
      <View style={styles.group}>
        {/* Topics is now its own tab (ADR-014 TopicControl) — this group is
            the notifications-related rows that don't warrant a tab. */}
        <SettingsRow label="Notifications" onPress={() => navigation.navigate("Notifications")} styles={styles} />
        <SettingsRow
          label="Notification preferences"
          onPress={() => navigation.navigate("NotificationPreferences")}
          last
          styles={styles}
        />
      </View>
      <Text style={styles.groupLabel} accessibilityRole="header">
        APPEARANCE
      </Text>
      <View style={styles.group} accessibilityRole="radiogroup">
        {THEME_OPTIONS.map((option, i) => (
          <ThemeOptionRow
            key={option.value}
            label={option.label}
            selected={preference === option.value}
            onPress={() => setPreference(option.value)}
            last={i === THEME_OPTIONS.length - 1}
            styles={styles}
          />
        ))}
      </View>
      <Text style={styles.groupLabel} accessibilityRole="header">
        TEXT SIZE
      </Text>
      <View style={styles.group} accessibilityRole="radiogroup">
        {TEXT_SIZE_OPTIONS.map((option, i) => (
          <ThemeOptionRow
            key={option.value}
            label={option.label}
            selected={textSize === option.value}
            onPress={() => setTextSize(option.value)}
            last={i === TEXT_SIZE_OPTIONS.length - 1}
            styles={styles}
          />
        ))}
      </View>
      <Text style={styles.groupHint}>Story headlines and text. Your phone's text size still applies.</Text>
      <Text style={styles.groupLabel}>ACCOUNT</Text>
      <View style={styles.group}>
        <SettingsRow label="Your profile" onPress={() => navigation.navigate("Profile")} styles={styles} />
        <SettingsRow label="Language" onPress={() => navigation.navigate("Language")} styles={styles} />
        <SettingsRow label="Hidden topics" onPress={() => navigation.navigate("HiddenTopics")} styles={styles} />
        <SettingsRow label="Privacy & delete account" onPress={() => navigation.navigate("Privacy")} last styles={styles} />
      </View>
      <Text style={styles.groupLabel}>ABOUT</Text>
      <View style={styles.group}>
        {/* The web site is the one copy of these pages; the app opens them in
            the browser rather than keeping its own text that could drift. */}
        {ABOUT_LINKS.map((link, i) => (
          <SettingsRow
            key={link.path}
            label={link.label}
            onPress={() => openWebPage(link.path)}
            external
            last={i === ABOUT_LINKS.length - 1}
            styles={styles}
          />
        ))}
      </View>
      <Text style={styles.version} accessibilityLabel={`App ${appVersionLabel()}`}>
        {appVersionLabel()}
      </Text>
    </ScrollView>
  );
}

const ABOUT_LINKS = [
  { path: "/about", label: "About The Telugu Edit" },
  { path: "/ai-disclosure", label: "How we use AI" },
  { path: "/privacy", label: "Privacy policy" },
  { path: "/terms", label: "Terms of use" },
];

function openWebPage(path: string) {
  // No browser / malformed URL: nothing useful to show, so don't crash Settings.
  Linking.openURL(`${siteUrl()}${path}`).catch(() => {});
}

/** "Version 0.0.1 (12)" — the build number only when the config sets one. */
export function appVersionLabel(): string {
  const config = Constants.expoConfig;
  const version = config?.version ?? "unknown";
  const build = config?.android?.versionCode ?? config?.ios?.buildNumber;
  return build ? `Version ${version} (${build})` : `Version ${version}`;
}

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "Use phone setting" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const TEXT_SIZE_OPTIONS: { value: TextSize; label: string }[] = [
  { value: "small", label: "Small" },
  { value: "default", label: "Default" },
  { value: "large", label: "Large" },
  { value: "xlarge", label: "Extra large" },
];

function ThemeOptionRow({
  label,
  selected,
  onPress,
  last,
  styles,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  last?: boolean;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      accessibilityLabel={label}
      style={[styles.row, !last && styles.rowDivider]}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      {selected ? <Ionicons name="checkmark" size={20} style={styles.check} /> : null}
    </Pressable>
  );
}

function SettingsRow({
  label,
  onPress,
  external,
  last,
  styles,
}: {
  label: string;
  onPress: () => void;
  external?: boolean;
  last?: boolean;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={external ? "link" : "button"}
      accessibilityLabel={label}
      accessibilityHint={external ? "Opens in your browser" : undefined}
      style={[styles.row, !last && styles.rowDivider]}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      {external ? (
        <Ionicons name="open-outline" size={16} style={styles.chevron} />
      ) : (
        <Text style={styles.chevron}>›</Text>
      )}
    </Pressable>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { padding: spacing.md, paddingBottom: spacing.xl },
    // Grouped-list pattern: a rounded container per group (not per row) with
    // hairline dividers between rows — replaces the old flat stack of
    // individually-bordered rows.
    groupLabel: {
      ...typography.meta,
      textTransform: "uppercase",
      letterSpacing: 1.2,
      color: colors.faint,
      paddingHorizontal: spacing.sm,
      paddingBottom: spacing.xs,
      paddingTop: spacing.md,
    },
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      overflow: "hidden",
    },
    row: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: spacing.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    rowLabel: { ...typography.body, color: colors.text },
    chevron: { fontSize: 18, color: ui.textTertiary },
    check: { color: colors.accent },
    groupHint: {
      ...typography.meta,
      textTransform: "none",
      color: ui.textTertiary,
      paddingHorizontal: spacing.sm,
      paddingTop: spacing.xs,
    },
    version: { ...typography.meta, color: colors.faint, textAlign: "center", paddingTop: spacing.lg },
  });
}
