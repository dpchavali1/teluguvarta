import Ionicons from "@expo/vector-icons/Ionicons";
import Constants from "expo-constants";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { PersonaState } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { PersonaPresetPicker } from "../components/PersonaPresetPicker";
import { siteUrl } from "../lib/api";
import { syncToServer } from "../lib/notificationSync";
import {
  getNotificationPreferences,
  getPersonaApplied,
  getProfile,
  savePersonaChange,
  toPersonaState,
} from "../lib/storage";
import type { ReadingStyle, TeluguFont, TextSize, ThemePreference } from "../lib/storage";
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
  const { textSize, setTextSize, teluguFont, setTeluguFont, readingStyle, setReadingStyle } = useTextSize();
  const [persona, setPersona] = useState<PersonaState | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const appliedCount = persona ? Object.values(persona.applied).filter(Boolean).length : 0;

  useEffect(() => {
    let active = true;
    Promise.all([getProfile(), getNotificationPreferences(), getPersonaApplied()]).then(([profile, prefs, applied]) => {
      if (active) setPersona(toPersonaState(profile, prefs, applied));
    });
    return () => {
      active = false;
    };
  }, []);

  function changePersona(next: PersonaState) {
    setPersona(next);
    savePersonaChange(next)
      .then((prefs) => syncToServer(prefs))
      .catch(() => {});
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {persona ? (
        <>
          <Text style={styles.groupLabel} accessibilityRole="header">QUICK SETUP</Text>
          <View style={styles.group}>
            <Pressable
              onPress={() => setQuickOpen((open) => !open)}
              accessibilityRole="button"
              accessibilityState={{ expanded: quickOpen }}
              accessibilityLabel="Quick setup"
              style={[styles.row, quickOpen && styles.rowDivider]}
            >
              <Text style={styles.rowLabel}>
                {appliedCount > 0 ? `${appliedCount} selected` : "Pick what fits you"}
              </Text>
              <Ionicons name={quickOpen ? "chevron-up" : "chevron-down"} size={18} style={styles.chevron} accessible={false} />
            </Pressable>
            {quickOpen ? <PersonaPresetPicker state={persona} onChange={changePersona} embedded /> : null}
          </View>
          {quickOpen ? (
            <Text style={styles.groupHint}>Each one only turns on its own topics and alerts, and unchecking it turns off just those. You can still change everything afterwards.</Text>
          ) : null}
        </>
      ) : null}
      <Text style={styles.groupLabel} accessibilityRole="header">NOTIFICATIONS</Text>
      <View style={styles.group}>
        <SettingsRow
          label="Alerts"
          onPress={() => navigation.navigate("Notifications")}
          last
          styles={styles}
        />
      </View>
      <Text style={styles.groupHint}>Choose what alerts you receive and when.</Text>
      <Text style={styles.groupLabel} accessibilityRole="header">READING & DISPLAY</Text>
      <View style={styles.group}>
        <SegmentedRow title="Appearance" options={THEME_OPTIONS} value={preference} onChange={setPreference} styles={styles} />
        <SegmentedRow title="Text size" options={TEXT_SIZE_OPTIONS} value={textSize} onChange={setTextSize} styles={styles} />
        <SegmentedRow title="Story length" options={READING_STYLE_OPTIONS} value={readingStyle} onChange={setReadingStyle} last styles={styles} />
      </View>
      <Text style={styles.groupHint}>Short trims feed cards to the headline and two lines; opening a story always shows everything. Your phone's text size still applies.</Text>
      <Text style={styles.groupLabel} accessibilityRole="header">
        TELUGU FONT
      </Text>
      <View style={styles.group} accessibilityRole="radiogroup" accessibilityLabel="Telugu font">
        {TELUGU_FONT_OPTIONS.map((option, i) => (
          <ThemeOptionRow
            key={option.value}
            label={option.label}
            selected={teluguFont === option.value}
            onPress={() => setTeluguFont(option.value)}
            last={i === TELUGU_FONT_OPTIONS.length - 1}
            styles={styles}
          />
        ))}
      </View>
      <Text style={styles.groupHint}>Used for Telugu story text. If a font can't load, your phone's font is used.</Text>
      <Text style={styles.groupLabel} accessibilityRole="header">YOUR READING</Text>
      <View style={styles.group}>
        <SettingsRow label="Your profile" onPress={() => navigation.navigate("Profile")} styles={styles} />
        <SettingsRow label="Language" onPress={() => navigation.navigate("Language")} styles={styles} />
        <SettingsRow label="Hidden topics" onPress={() => navigation.navigate("HiddenTopics")} styles={styles} />
        <SettingsRow label="Privacy & delete account" onPress={() => navigation.navigate("Privacy")} last styles={styles} />
      </View>
      <Text style={styles.groupLabel} accessibilityRole="header">ABOUT</Text>
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

const TELUGU_FONT_OPTIONS: { value: TeluguFont; label: string }[] = [
  { value: "system", label: "Phone default" },
  { value: "serif", label: "Noto Serif Telugu" },
  { value: "mandali", label: "Mandali" },
];

const READING_STYLE_OPTIONS: { value: ReadingStyle; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "short", label: "Short" },
];

function SegmentedRow<T extends string>({
  title,
  options,
  value,
  onChange,
  last,
  styles,
}: {
  title: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (next: T) => void;
  last?: boolean;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View style={[styles.segRow, !last && styles.rowDivider]}>
      <Text style={styles.segTitle}>{title}</Text>
      <View style={styles.segTrack} accessibilityRole="radiogroup" accessibilityLabel={title}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={option.value}
              onPress={() => onChange(option.value)}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={option.label}
              style={[styles.segItem, selected && styles.segItemSelected]}
            >
              <Text style={[styles.segText, selected && styles.segTextSelected]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

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
      {selected ? <Ionicons name="checkmark" size={20} style={styles.check} accessible={false} /> : null}
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
        <Ionicons name="open-outline" size={16} style={styles.chevron} accessible={false} />
      ) : (
        <Ionicons name="chevron-forward" size={18} style={styles.chevron} accessible={false} />
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
      borderRadius: radius.card,
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
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    rowLabel: { ...typography.body, flex: 1, color: colors.text },
    chevron: { fontSize: 18, color: ui.textTertiary },
    check: { color: colors.accent },
    segRow: { gap: spacing.xs, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
    segTitle: { ...typography.meta, textTransform: "none", color: colors.faint },
    segTrack: { flexDirection: "row", backgroundColor: ui.surfaceSubtle, borderRadius: 10, padding: 3 },
    segItem: { flex: 1, minHeight: 36, alignItems: "center", justifyContent: "center", borderRadius: 8, paddingHorizontal: 4 },
    segItemSelected: { backgroundColor: colors.surface, borderWidth: 1, borderColor: ui.borderSubtle },
    segText: { ...typography.meta, textTransform: "none", color: colors.faint, textAlign: "center" },
    segTextSelected: { color: colors.text, fontWeight: "600" },
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
