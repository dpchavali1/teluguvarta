import { topicLabel } from "@teluguvarta/domain";
import React, { useMemo } from "react";
import { AccessibilityInfo, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useHiddenTopics } from "../lib/HiddenTopicsContext";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// Plan M5: undo for "Show less". Lists the topics hidden from Home and Latest.
export function HiddenTopicsScreen() {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { hiddenTopics, showTopic } = useHiddenTopics();

  function handleShow(slug: string) {
    showTopic(slug);
    AccessibilityInfo.announceForAccessibility(`Stories about ${topicLabel(slug)} will show again.`);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        {hiddenTopics.length === 0
          ? "No hidden topics. Tap “Show less” on a story in Home or Latest to hide its topic there."
          : "Stories from these topics are left out of Home and Latest. Topic pages, Search and Saved still show them."}
      </Text>
      {hiddenTopics.length > 0 && (
        <View style={styles.group}>
          {hiddenTopics.map((slug, i) => (
            <View key={slug} style={[styles.row, i < hiddenTopics.length - 1 && styles.rowDivider]}>
              <Text style={styles.rowLabel}>{topicLabel(slug)}</Text>
              <Pressable
                onPress={() => handleShow(slug)}
                accessibilityRole="button"
                accessibilityLabel={`Show stories about ${topicLabel(slug)} again`}
                style={styles.button}
              >
                <Text style={styles.buttonText}>Show again</Text>
              </Pressable>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xl },
    intro: { ...typography.body, color: ui.textSecondary },
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      overflow: "hidden",
    },
    row: {
      minHeight: 56,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    rowLabel: { ...typography.body, color: colors.text, flexShrink: 1 },
    button: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    buttonText: { color: colors.text, fontWeight: "600" },
  });
}
