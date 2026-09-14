import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { RootStackParamList } from "../navigation/types";
import { colors, radius, spacing, typography, ui } from "../theme/tokens";

export function SettingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <View style={styles.container}>
      <Text style={styles.groupLabel}>GENERAL</Text>
      <View style={styles.group}>
        <SettingsRow label="Browse topics" onPress={() => navigation.navigate("TopicsIndex")} />
        <SettingsRow
          label="Notification preferences"
          onPress={() => navigation.navigate("NotificationPreferences")}
          last
        />
      </View>
      <Text style={styles.groupLabel}>ACCOUNT</Text>
      <View style={styles.group}>
        <SettingsRow label="Language" onPress={() => navigation.navigate("Language")} />
        <SettingsRow label="Privacy & delete account" onPress={() => navigation.navigate("Privacy")} last />
      </View>
    </View>
  );
}

function SettingsRow({ label, onPress, last }: { label: string; onPress: () => void; last?: boolean }) {
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

const styles = StyleSheet.create({
  container: { padding: spacing.md },
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
  rowLabel: { ...typography.body },
  chevron: { fontSize: 18, color: ui.textTertiary },
});
