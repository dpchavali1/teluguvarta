import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { StoryCard } from "../components/StoryCard";
import { ApiNetworkError, getStory, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "StoryDetail">;

export function StoryDetailScreen({ route }: Props) {
  const { slug } = route.params;
  const cache = useStoryCache();
  const [story, setStory] = useState<StoryOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setError(null);
    getStory(slug)
      .then((result) => {
        if (cancelled) return;
        setStory(result);
        cache.put([result]);
        trackEvent("story_open", { story_id: result.id });
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : "Couldn't load this story.");
      });
    return () => {
      cancelled = true;
    };
  }, [slug, cache]);

  useEffect(() => load(), [load, retryKey]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text>{error}</Text>
        <Pressable
          onPress={() => setRetryKey((k) => k + 1)}
          accessibilityRole="button"
          accessibilityLabel="Retry"
          style={styles.retryButton}
        >
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  if (!story) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading story" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StoryCard story={story} onOpenSource={(url) => Linking.openURL(url)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
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
