import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { ApiNetworkError, type StoryOut } from "../lib/api";
import { useHiddenTopics, withoutHiddenTopics } from "../lib/HiddenTopicsContext";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";
import { StoryList } from "./StoryList";

export type StoryPage = { stories: StoryOut[]; next_cursor?: string | null };

// Shared by Topic and Latest: first page, retry, "Older stories" by cursor.
// `fetchPage` must be stable (useCallback) — a new identity reloads page one.
export function PagedStoryList({
  fetchPage,
  loadingLabel,
  errorLabel,
  emptyLabel,
  respectHiddenTopics = false,
}: {
  fetchPage: (cursor?: string) => Promise<StoryPage>;
  loadingLabel: string;
  errorLabel: string;
  emptyLabel: string;
  /** Leave out stories from topics the reader hid, and offer "Show less" (Latest, not Topic). */
  respectHiddenTopics?: boolean;
}) {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { put } = useStoryCache();
  const { hiddenTopics, hiddenSources } = useHiddenTopics();
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
    fetchPage()
      .then((result) => {
        if (cancelled) return;
        setStories(result.stories);
        setCursor(result.next_cursor ?? null);
        put(result.stories);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : errorLabel);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      requestId.current += 1;
    };
  }, [fetchPage, errorLabel, put]);

  useEffect(() => load(), [load, retryKey]);

  async function loadMore() {
    if (!cursor || moreLoading) return;
    const current = requestId.current;
    setMoreLoading(true);
    setMoreError(false);
    try {
      const page = await fetchPage(cursor);
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
        <ActivityIndicator accessibilityLabel={loadingLabel} color={colors.text} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.message} accessibilityRole="alert">{error}</Text>
        <Pressable onPress={() => setRetryKey((key) => key + 1)} accessibilityRole="button" accessibilityLabel="Retry" style={styles.button}>
          <Text style={styles.buttonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  const footer = (
    <View style={styles.footer}>
      {moreError && <Text style={styles.message} accessibilityRole="alert">Couldn’t load older stories. Try again.</Text>}
      {cursor && (
        <Pressable
          onPress={() => void loadMore()}
          disabled={moreLoading}
          accessibilityRole="button"
          accessibilityState={{ disabled: moreLoading, busy: moreLoading }}
          style={styles.button}
        >
          <Text style={styles.buttonText}>{moreLoading ? "Loading…" : "Older stories"}</Text>
        </Pressable>
      )}
    </View>
  );

  const visible = respectHiddenTopics ? withoutHiddenTopics(stories, hiddenTopics, hiddenSources) : stories;
  return (
    <StoryList
      stories={visible}
      emptyLabel={visible.length < stories.length ? HIDDEN_ALL_LABEL : emptyLabel}
      footer={footer}
      allowHideTopic={respectHiddenTopics}
    />
  );
}

export const HIDDEN_ALL_LABEL = "These stories are all from topics or sources you've hidden. Show them again in Settings → My Edit signals.";

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md, padding: spacing.lg },
    message: { color: colors.text, textAlign: "center" },
    footer: { padding: spacing.md, gap: spacing.sm, alignItems: "center" },
    // Primary action uses the paired light/dark indigo control role.
    button: {
      minHeight: 44,
      minWidth: 44,
      paddingHorizontal: spacing.lg,
      justifyContent: "center",
      alignItems: "center",
      borderRadius: radius.pill,
      borderCurve: "continuous",
      backgroundColor: ui.actionPrimary,
    },
    buttonText: { color: ui.actionPrimaryText, fontWeight: "600" },
  });
}
