import Ionicons from "@expo/vector-icons/Ionicons";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { ThemePreference } from "../lib/storage";
import type { RootStackParamList } from "../navigation/types";
import { useThemePreference } from "../theme/ThemePreferenceContext";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

export function SettingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { preference, setPreference } = useThemePreference();

  return (
    <View style={styles.container}>
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
      <Text style={styles.groupLabel}>ACCOUNT</Text>
      <View style={styles.group}>
        <SettingsRow label="Language" onPress={() => navigation.navigate("Language")} styles={styles} />
        <SettingsRow label="Privacy & delete account" onPress={() => navigation.navigate("Privacy")} last styles={styles} />
      </View>
    </View>
  );
}

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "Use phone setting" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
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
  last,
  styles,
}: {
  label: string;
  onPress: () => void;
  last?: boolean;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={[styles.row, !last && styles.rowDivider]}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, padding: spacing.md, backgroundColor: colors.bg },
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
  });
}
