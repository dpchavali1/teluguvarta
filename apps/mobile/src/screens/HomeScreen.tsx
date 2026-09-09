import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { StoryCard } from "../components/StoryCard";
import { getHome, trackEvent, type StoryOut, type TopicOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import type { RootStackParamList } from "../navigation/types";

export function HomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const cache = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const home = await getHome();
      setStories(home.top_stories);
      setTopics(home.topics);
      cache.put(home.top_stories);
      trackEvent("feed_view", { story_count: home.top_stories.length });
    } catch {
      setError("Couldn't load the feed. Pull down to try again.");
    } finally {
      setLoading(false);
    }
  }, [cache]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && stories.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading stories" />
      </View>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      accessibilityLabel="Home feed"
    >
      {error && <Text style={styles.error}>{error}</Text>}
      {topics.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.topicRow}>
          {topics.map((topic) => (
            <Pressable
              key={topic.slug}
              onPress={() => navigation.navigate("Topic", { slug: topic.slug, name: topic.name })}
              accessibilityRole="button"
              accessibilityLabel={`Browse topic: ${topic.name}`}
              style={styles.topicChip}
            >
              <Text>{topic.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
      {stories.map((story) => (
        <StoryCard
          key={story.id}
          story={story}
          onOpen={() => navigation.navigate("StoryDetail", { slug: story.canonical_slug })}
          onOpenSource={(url) => Linking.openURL(url)}
        />
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { paddingBottom: 24 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  error: { color: "#b00", padding: 16 },
  topicRow: { paddingVertical: 8, paddingHorizontal: 12 },
  topicChip: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 14,
    marginRight: 8,
    borderRadius: 16,
    backgroundColor: "#f0f0f0",
  },
});
