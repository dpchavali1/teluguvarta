import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { ApiNetworkError, getConfig, type TopicOut } from "../lib/api";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";
import type { RootStackParamList } from "../navigation/types";

// ADR-014 TopicControl: topic browsing previously had no entry point
// outside Home's topic chip row — a reader who navigated to Search/Saved/
// Settings first had no way back to it except returning Home, and a later
// fix only got it as far as a row buried in Settings. It's now the Topics
// tab itself (see MainTabs.tsx), an unmistakable first-class destination
// rather than a fifth-tab overflow item. Lists the full catalog via
// getConfig(), not getHome()'s personalized/ranked subset.
export function TopicsIndexScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [topics, setTopics] = useState<TopicOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    setError(null);
    getConfig()
      .then((config) => {
        if (!cancelled) setTopics(config.topics.filter((topic) => topic.active));
      })
      .catch((err) => {
        if (cancelled) return;
        setTopics(null);
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : "Couldn't load topics.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => load(), [load]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text>{error}</Text>
        <Pressable onPress={load} accessibilityRole="button" accessibilityLabel="Retry" style={styles.retryButton}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  if (topics === null) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading topics" />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      data={topics}
      keyExtractor={(topic) => topic.slug}
      ListEmptyComponent={
        <View style={styles.center}>
          <Text>No topics yet.</Text>
        </View>
      }
      renderItem={({ item: topic }) => (
        <Pressable
          onPress={() => navigation.navigate("Topic", { slug: topic.slug, name: topic.name })}
          accessibilityRole="button"
          accessibilityLabel={`Browse topic: ${topic.name}`}
          style={styles.row}
        >
          <Text style={styles.rowLabel}>{topic.name}</Text>
          <Text style={styles.chevron}>{"›"}</Text>
        </Pressable>
      )}
    />
  );
}

function createStyles(colors: AppTheme["colors"]) {
  return StyleSheet.create({
    list: { backgroundColor: colors.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
    row: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.md,
      borderBottomWidth: 1,
      borderColor: colors.border,
    },
    rowLabel: { ...typography.body, color: colors.text },
    chevron: { fontSize: 18, color: colors.faint },
    // Ink-filled button, matching apps/web's main button.
    retryButton: {
      minHeight: 44,
      minWidth: 44,
      paddingHorizontal: spacing.lg,
      justifyContent: "center",
      alignItems: "center",
      borderRadius: radius.pill,
      borderCurve: "continuous",
      backgroundColor: colors.text,
    },
    retryButtonText: { color: colors.bg, fontWeight: "600" },
  });
}
