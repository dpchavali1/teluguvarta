import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Linking, StyleSheet, Text, View } from "react-native";

import { StoryCard } from "../components/StoryCard";
import { getStory, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "StoryDetail">;

export function StoryDetailScreen({ route }: Props) {
  const { slug } = route.params;
  const cache = useStoryCache();
  const [story, setStory] = useState<StoryOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStory(slug)
      .then((result) => {
        if (cancelled) return;
        setStory(result);
        cache.put([result]);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this story.");
      });
    return () => {
      cancelled = true;
    };
  }, [slug, cache]);

  if (error) {
    return (
      <View style={styles.center}>
        <Text>{error}</Text>
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
      <StoryCard story={story} onOpen={() => {}} onOpenSource={(url) => Linking.openURL(url)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
