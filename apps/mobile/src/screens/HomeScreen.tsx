import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { StoryCard } from "../components/StoryCard";
import { ApiNetworkError, getHome, trackEvent, type StoryOut, type TopicOut } from "../lib/api";
import { getProfile, isStudentSegment, primaryLifeStageSegment } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing } from "../theme/tokens";
import type { RootStackParamList } from "../navigation/types";

export function HomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const cache = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [briefingStories, setBriefingStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const profile = await getProfile();
      const homeParams = {
        residenceCountry: profile.residenceCountry,
        homeRegion: profile.homeRegion,
        homeCity: profile.homeCity,
        topics: profile.interestTopicSlugs,
        segment: primaryLifeStageSegment(profile.lifeStages),
      };
      const home = await getHome(homeParams);
      setStories(home.top_stories);
      setTopics(home.topics);
      cache.put(home.top_stories);
      trackEvent("feed_view", { story_count: home.top_stories.length });

      // S1: "Student Briefing" — explicit-preference-only (never inferred
      // from behavior), only fetched when the user selected this life stage
      // during onboarding (any of the selected life stages, now that more
      // than one can be picked — see docs/tickets/S1.md). Same feed/ranking
      // endpoint, `student_briefing` composes the topic filter server-side.
      if (isStudentSegment(profile.lifeStages)) {
        const briefing = await getHome({ ...homeParams, studentBriefing: true });
        setBriefingStories(briefing.top_stories);
        cache.put(briefing.top_stories);
      } else {
        setBriefingStories([]);
      }
    } catch (err) {
      setError(
        err instanceof ApiNetworkError
          ? "You're offline. Pull down to try again once you're back online."
          : "Couldn't load the feed. Pull down to try again."
      );
    } finally {
      setLoading(false);
    }
  }, [cache]);

  useEffect(() => {
    load();
  }, [load]);

  // The error copy tells the user to pull down to retry, so that gesture has
  // to actually exist — without it the error state is unrecoverable short of
  // restarting the app.
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  if (loading && stories.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator accessibilityLabel="Loading stories" />
      </View>
    );
  }

  // Design-review fix: this was a ScrollView + .map() over every story —
  // the one screen mounting every card at once, unlike every other list
  // screen (Search/Saved/Topic), which use FlatList via StoryList. Topics
  // and the Student Briefing are small/bounded, so they stay in the
  // header; only the main feed (unbounded, highest-traffic) needs
  // virtualization.
  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={styles.container}
      accessibilityLabel="Home feed"
      data={stories}
      keyExtractor={(story) => story.id}
      renderItem={({ item }) => (
        <StoryCard
          story={item}
          onOpen={() => navigation.navigate("StoryDetail", { slug: item.canonical_slug })}
          onOpenSource={(url) => Linking.openURL(url)}
        />
      )}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          tintColor={colors.teal}
          colors={[colors.teal]}
          accessibilityLabel="Refresh the feed"
        />
      }
      ListHeaderComponent={
        <>
          {error && <Text style={styles.error}>{error}</Text>}
          {topics.length > 0 && (
            <FlatList
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.topicRow}
              data={topics}
              keyExtractor={(topic) => topic.slug}
              renderItem={({ item: topic }) => (
                <Pressable
                  onPress={() => navigation.navigate("Topic", { slug: topic.slug, name: topic.name })}
                  accessibilityRole="button"
                  accessibilityLabel={`Browse topic: ${topic.name}`}
                  style={styles.topicChip}
                >
                  <Text style={styles.topicChipText}>{topic.name}</Text>
                </Pressable>
              )}
            />
          )}
          {briefingStories.length > 0 && (
            <View style={styles.briefing} accessibilityLabel="Student Briefing">
              <Text style={styles.briefingTitle}>Student Briefing</Text>
              <Text style={styles.briefingSubtitle}>
                Shown because you selected a student life stage during setup.
              </Text>
              {briefingStories.map((story) => (
                <StoryCard
                  key={story.id}
                  story={story}
                  onOpen={() => navigation.navigate("StoryDetail", { slug: story.canonical_slug })}
                  onOpenSource={(url) => Linking.openURL(url)}
                />
              ))}
            </View>
          )}
        </>
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { backgroundColor: colors.bg },
  container: { paddingBottom: 24, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  error: { color: colors.danger, padding: spacing.lg },
  topicRow: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md },
  topicChip: {
    minHeight: 40,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    marginRight: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.tealSoft,
  },
  topicChipText: { color: colors.teal, fontWeight: "600", fontSize: 13 },
  briefing: {
    marginBottom: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  briefingTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  briefingSubtitle: {
    fontSize: 13,
    color: colors.muted,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
});
