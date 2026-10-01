import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, Button, Pressable, Text, View } from "react-native";
import { StoryList } from "../components/StoryList";
import { getSavedStories, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing } from "../theme/tokens";
import { useAppTheme } from "../theme/useAppTheme";

type SavedView = "saved" | "read";

export function SavedScreen() {
  const { put, savedIds, savedReady, readIds, readReady, clearReadHistory } = useStoryCache();
  const { colors, ui } = useAppTheme();
  // Plan M6: "Recently read" sits next to bookmarks; both resolve current data from the API.
  const [view, setView] = useState<SavedView>("saved");
  const ids = view === "saved" ? savedIds : readIds;
  const ready = view === "saved" ? savedReady : readReady;
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(0);
  const [revision, setRevision] = useState(0);
  useFocusEffect(useCallback(() => {
    let cancelled = false;
    if (!ready) return;
    setLoading(true);
    setError(null);
    getSavedStories(ids).then((items) => {
      if (cancelled) return;
      setStories(items);
      setMissing(ids.length - items.length);
      put(items);
    }).catch(() => {
      if (!cancelled) {
        setError(view === "saved"
          ? "Couldn't load saved stories. Your bookmarks are still saved."
          : "Couldn't load your reading history. Try again.");
      }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [put, ids, ready, view, revision]));

  const tabs = (
    <View accessibilityRole="radiogroup" style={{ flexDirection: "row", gap: spacing.xs, padding: spacing.md, paddingBottom: 0 }}>
      {([["saved", "Saved"], ["read", "Recently read"]] as const).map(([value, label]) => {
        const selected = view === value;
        return (
          <Pressable
            key={value}
            onPress={() => setView(value)}
            accessibilityRole="radio"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={label}
            style={{
              minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md, borderRadius: radius.md,
              borderWidth: 1, borderColor: ui.borderControl, backgroundColor: selected ? ui.actionPrimary : "transparent",
            }}
          >
            <Text style={{ fontWeight: "600", color: selected ? ui.actionPrimaryText : colors.text }}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );

  let body: React.ReactNode;
  if (loading) body = <ActivityIndicator accessibilityLabel={view === "saved" ? "Loading saved stories" : "Loading recently read stories"} color={colors.text} />;
  else if (error) body = <View style={{ padding: 24 }}><Text accessibilityRole="alert" style={{ color: colors.text }}>{error}</Text><Button title="Try again" onPress={() => setRevision((value) => value + 1)} /></View>;
  else if (view === "saved") {
    body = <>
      {missing > 0 && <Text style={{ padding: 16, color: colors.muted }}>{missing} saved stories are currently unavailable. Your bookmarks have been kept.</Text>}
      <StoryList stories={stories} emptyLabel="No saved stories to show. Save a story from the feed to find it here." onRefresh={() => setRevision((value) => value + 1)} refreshing={loading} />
    </>;
  } else {
    // Unpublished or retracted stories drop out of the list silently; their ids age out of the cap.
    body = <StoryList
      stories={stories}
      emptyLabel="Stories you open show up here. Your reading history stays on this phone."
      onRefresh={() => setRevision((value) => value + 1)}
      refreshing={loading}
      showRead={false}
      footer={readIds.length > 0 ? (
        <View style={{ padding: spacing.md, alignItems: "center" }}>
          <Pressable
            onPress={clearReadHistory}
            accessibilityRole="button"
            style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: ui.borderControl }}
          >
            <Text style={{ fontWeight: "600", color: colors.text }}>Clear reading history</Text>
          </Pressable>
        </View>
      ) : undefined}
    />;
  }

  return <View style={{ flex: 1 }}>{tabs}{body}</View>;
}
