import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { getTopic, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Topic">;

export function TopicScreen({ route }: Props) {
  const { slug } = route.params;
  const cache = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getTopic(slug)
      .then((result) => {
        if (cancelled) return;
        setStories(result.stories);
        cache.put(result.stories);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this topic.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, cache]);

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
      </View>
    );
  }

  return <StoryList stories={stories} emptyLabel="No stories in this topic yet." />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
