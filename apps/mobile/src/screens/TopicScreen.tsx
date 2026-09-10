import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { ApiNetworkError, getTopic, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Topic">;

export function TopicScreen({ route }: Props) {
  const { slug } = route.params;
  const cache = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTopic(slug)
      .then((result) => {
        if (cancelled) return;
        setStories(result.stories);
        cache.put(result.stories);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : "Couldn't load this topic.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, cache]);

  useEffect(() => load(), [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading topic" />
      </View>
    );
  }

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

  return <StoryList stories={stories} emptyLabel="No stories in this topic yet." />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  retryButton: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: radius.pill,
    backgroundColor: colors.teal,
  },
  retryButtonText: { color: colors.accentContrast, fontWeight: "600" },
});
