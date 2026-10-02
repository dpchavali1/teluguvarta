import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, AppState, ScrollView, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { StoryCard } from "../components/StoryCard";
import { ApiNetworkError, ApiNotFoundError, getStory, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "StoryDetail">;

function formatLoadedAt(ms: number): string {
  return new Date(ms).toLocaleString();
}

export function StoryDetailScreen({ route }: Props) {
  const { slug } = route.params;
  const { put, getBySlug, remove, markRead } = useStoryCache();
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [story, setStory] = useState<StoryOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Set while the screen shows a cached copy the API hasn't confirmed:
  // `refreshing` during the fetch, then a reason if the fetch failed.
  const [stale, setStale] = useState<{ loadedAt: number; reason: "refreshing" | "offline" | "failed" } | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const checkedAt = useRef(0);
  const inFlight = useRef(false);

  // Plan M6: a story counts as read once it's on screen (cached copy or API).
  const storyId = story?.id;
  useEffect(() => {
    if (storyId) markRead(storyId);
  }, [storyId, markRead]);

  const load = useCallback(() => {
    let cancelled = false;
    checkedAt.current = Date.now();
    inFlight.current = true;
    // Review R10: open from the copy the feed already loaded instead of a
    // blank spinner, then replace it with the API's current version.
    const cached = getBySlug(slug);
    setError(null);
    setStory(cached?.story ?? null);
    setStale(cached ? { loadedAt: cached.loadedAt, reason: "refreshing" } : null);
    getStory(slug)
      .then((result) => {
        if (cancelled) return;
        setStory(result);
        setStale(null);
        put([result]);
        trackEvent("story_open", { story_id: result.id });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiNotFoundError) {
          // Unpublished or retracted since it was cached: never keep showing it.
          if (cached) remove(cached.story.id);
          setStory(null);
          setStale(null);
          setError("This story is no longer available.");
          return;
        }
        const offline = err instanceof ApiNetworkError;
        if (cached) {
          setStale({ loadedAt: cached.loadedAt, reason: offline ? "offline" : "failed" });
          return;
        }
        setError(offline ? "You're offline. Check your connection." : "Couldn't load this story.");
      }).finally(() => { if (!cancelled) inFlight.current = false; });
    return () => {
      cancelled = true;
      inFlight.current = false;
    };
  }, [slug, put, getBySlug, remove]);

  useEffect(() => load(), [load, retryKey]);

  const refreshIfStale = useCallback(() => {
    if (checkedAt.current > 0 && !inFlight.current && Date.now() - checkedAt.current >= 5 * 60 * 1000) {
      setRetryKey((key) => key + 1);
    }
  }, []);
  useFocusEffect(refreshIfStale);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") refreshIfStale();
    });
    return () => subscription.remove();
  }, [refreshIfStale]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.message} accessibilityRole="alert">{error}</Text>
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
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: spacing.xl }} contentInsetAdjustmentBehavior="automatic" accessibilityLabel="Story content">
      {stale ? (
        <View style={styles.staleBanner} accessibilityLiveRegion="polite">
          <Text style={styles.staleText}>
            {stale.reason === "refreshing" ? "Checking for updates. " : stale.reason === "offline" ? "You're offline. " : "Couldn't refresh this story. "}
            Showing the copy loaded at {formatLoadedAt(stale.loadedAt)}; it may not include later corrections.
          </Text>
          {stale.reason !== "refreshing" && <Pressable
            onPress={() => setRetryKey((k) => k + 1)}
            accessibilityRole="button"
            accessibilityLabel="Retry loading the latest version"
            style={styles.staleRetry}
          >
            <Text style={styles.staleRetryText}>Retry</Text>
          </Pressable>}
        </View>
      ) : null}
      <StoryCard story={story} layout="detail" onOpenSource={(url) => Linking.openURL(url)} />
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md, backgroundColor: colors.bg },
    message: { color: colors.text, textAlign: "center", paddingHorizontal: spacing.lg },
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
    staleBanner: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: spacing.md,
      margin: spacing.md,
      padding: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    staleText: { flex: 1, minWidth: 180, color: colors.text },
    staleRetry: { minHeight: 44, minWidth: 44, justifyContent: "center", alignItems: "center" },
    staleRetryText: { color: colors.text, fontWeight: "600", textDecorationLine: "underline" },
  });
}
