import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Button, Pressable, StyleSheet, Text, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { ApiNetworkError, getTopic, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Topic">;

export function TopicScreen({ route }: Props) {
  const { slug } = route.params;
  const { put } = useStoryCache();
  const requestId = useRef(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [moreLoading, setMoreLoading] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [retryKey, setRetryKey] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    requestId.current += 1;
    setMoreError(false);
    setMoreLoading(false);
    setLoading(true);
    setError(null);
    getTopic(slug)
      .then((result) => {
        if (cancelled) return;
        setStories(result.stories);
        setCursor(result.next_cursor ?? null);
        put(result.stories);
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
      requestId.current += 1;
    };
  }, [slug, put]);

  useEffect(() => load(), [load, retryKey]);

  async function loadMore() {
    if (!cursor || moreLoading) return;
    const current = requestId.current;
    setMoreLoading(true);
    setMoreError(false);
    try {
      const page = await getTopic(slug, cursor);
      if (current !== requestId.current) return;
      setStories((items) => [...new Map([...items, ...page.stories].map((story) => [story.id, story])).values()]);
      setCursor(page.next_cursor ?? null);
      put(page.stories);
    } catch { if (current === requestId.current) setMoreError(true); }
    finally { if (current === requestId.current) setMoreLoading(false); }
  }

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
        <Pressable onPress={() => setRetryKey((key) => key + 1)} accessibilityRole="button" accessibilityLabel="Retry" style={styles.retryButton}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return <StoryList stories={stories} emptyLabel="No stories in this topic yet." footer={<View style={{ padding: 16 }}>{moreError && <Text>Couldn’t load older stories. Try again.</Text>}{cursor && <Button title={moreLoading ? "Loading…" : "Older stories"} disabled={moreLoading} onPress={() => void loadMore()} />}</View>} />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  // Ink-filled button, matching apps/web's main button.
  retryButton: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: radius.pill,
    backgroundColor: colors.text,
  },
  retryButtonText: { color: colors.bg, fontWeight: "600" },
});
