import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, Button, Text, View } from "react-native";
import { StoryList } from "../components/StoryList";
import { getSavedStories, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";

export function SavedScreen() {
  const { put, savedIds, savedReady } = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(0);
  const [revision, setRevision] = useState(0);
  useFocusEffect(useCallback(() => {
    let cancelled = false;
    if (!savedReady) return;
    setLoading(true);
    setError(null);
    getSavedStories(savedIds).then((items) => {
      if (cancelled) return;
      setStories(items);
      setMissing(savedIds.length - items.length);
      put(items);
    }).catch(() => {
      if (!cancelled) setError("Couldn't load saved stories. Your bookmarks are still saved.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [put, savedIds, savedReady, revision]));

  if (loading) return <ActivityIndicator accessibilityLabel="Loading saved stories" />;
  if (error) return <View style={{ padding: 24 }}><Text accessibilityRole="alert">{error}</Text><Button title="Try again" onPress={() => setRevision((value) => value + 1)} /></View>;
  return <View style={{ flex: 1 }}>
    {missing > 0 && <Text style={{ padding: 16 }}>{missing} saved stories are currently unavailable. Your bookmarks have been kept.</Text>}
    <StoryList stories={stories} emptyLabel="No saved stories to show. Save a story from the feed to find it here." onRefresh={() => setRevision((value) => value + 1)} refreshing={loading} />
  </View>;
}
