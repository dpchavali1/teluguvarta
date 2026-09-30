import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  FlatList,
  Linking,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { StoryCard } from "../components/StoryCard";
import { ApiNetworkError, getHome, trackEvent, type StoryOut, type TopicOut } from "../lib/api";
import { getProfile, isStudentSegment, primaryLifeStageSegment } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";
import type { RootStackParamList } from "../navigation/types";

// Review #14: Home loaded only on mount and pull-to-refresh, so a feed left
// open overnight stayed stale. Returning to the tab or the app reloads it,
// but at most once per this interval.
export const HOME_STALE_MS = 5 * 60 * 1000;

export function HomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { put } = useStoryCache();
  const [stories, setStories] = useState<StoryOut[]>([]);
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [briefingStories, setBriefingStories] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestId = useRef(0);
  const loadedAt = useRef<number | null>(null);

  const load = useCallback(async () => {
    const current = ++requestId.current;
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
      if (current !== requestId.current) return;
      loadedAt.current = Date.now();
      setStories(home.top_stories);
      // Chips lead to content; the Topics tab lists the empty ones too.
      setTopics(home.topics.filter((topic) => topic.story_count > 0));
      put(home.top_stories);
      trackEvent("feed_view", { story_count: home.top_stories.length });

      // S1: "Student Briefing" — explicit-preference-only (never inferred
      // from behavior), only fetched when the user selected this life stage
      // during onboarding (any of the selected life stages, now that more
      // than one can be picked — see docs/tickets/S1.md). Same feed/ranking
      // endpoint, `student_briefing` composes the topic filter server-side.
      if (isStudentSegment(profile.lifeStages)) {
        const briefing = await getHome({ ...homeParams, studentBriefing: true });
        if (current !== requestId.current) return;
        setBriefingStories(briefing.top_stories);
        put(briefing.top_stories);
      } else {
        setBriefingStories([]);
      }
    } catch (err) {
      if (current !== requestId.current) return;
      setError(
        err instanceof ApiNetworkError
          ? "You're offline. Pull down to try again once you're back online."
          : "Couldn't load the feed. Pull down to try again."
      );
    } finally {
      if (current === requestId.current) setLoading(false);
    }
  }, [put]);

  useEffect(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]);

  // Only after a successful load: the mount effect covers the first one, and
  // a failed load is retried by pull-to-refresh, as its error copy says.
  const refreshIfStale = useCallback(() => {
    if (loadedAt.current !== null && Date.now() - loadedAt.current >= HOME_STALE_MS) void load();
  }, [load]);

  useFocusEffect(refreshIfStale);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") refreshIfStale();
    });
    return () => subscription.remove();
  }, [refreshIfStale]);

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
      renderItem={({ item, index }) => (
        <>
          {index === 1 && <Text style={styles.sectionLabel}>MORE STORIES</Text>}
          <StoryCard
            story={item}
            layout={index === 0 ? "hero" : "compact"}
            onOpen={() => navigation.navigate("StoryDetail", { slug: item.canonical_slug })}
            onOpenSource={(url) => Linking.openURL(url)}
          />
        </>
      )}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          tintColor={colors.text}
          colors={[colors.text]}
          accessibilityLabel="Refresh the feed"
        />
      }
      ListEmptyComponent={!loading && !error ? <Text style={styles.empty}>No stories yet. Browse topics or pull down to refresh.</Text> : null}
      // Home is a bounded ranked set; Latest pages through everything.
      ListFooterComponent={
        <Pressable
          onPress={() => navigation.navigate("Latest")}
          accessibilityRole="button"
          accessibilityHint="Opens every published story, newest first"
          style={styles.latestLink}
        >
          <Text style={styles.latestLinkText}>All latest stories</Text>
        </Pressable>
      }
      ListHeaderComponent={
        <>
          <View style={styles.welcome} accessibilityLabel="Your daily briefing">
            <Text style={styles.welcomeEyebrow}>TODAY</Text>
            <Text style={styles.welcomeTitle}>What matters today</Text>
            <Text style={styles.welcomeCopy}>Clear updates for life here and back home.</Text>
          </View>
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

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
  list: { backgroundColor: colors.bg },
  container: { paddingBottom: 24, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  error: { color: ui.danger, padding: spacing.lg },
  empty: { color: colors.muted, padding: spacing.lg },
  latestLink: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    borderRadius: radius.pill,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: colors.border,
  },
  latestLinkText: { ...typography.meta, textTransform: "none", color: colors.text },
  welcome: {
    margin: spacing.md,
    marginBottom: spacing.sm,
    paddingVertical: spacing.sm,
  },
  welcomeEyebrow: { ...typography.meta, color: ui.actionText, textTransform: "uppercase" },
  welcomeTitle: { ...typography.display, color: colors.text, marginTop: spacing.xs },
  welcomeCopy: { ...typography.body, color: colors.muted, marginTop: spacing.xs },
  topicRow: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md },
  // Matches web's .pill--topic: transparent, ink text, no fill at rest.
  topicChip: {
    minHeight: 40,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    marginRight: spacing.sm,
    borderRadius: radius.pill,
    borderCurve: "continuous",
    backgroundColor: ui.actionPrimarySoft,
  },
  topicChipText: { ...typography.meta, textTransform: "none", color: colors.text },
  briefing: {
    marginBottom: spacing.md,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  briefingTitle: {
    ...typography.headline,
    color: colors.text,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  briefingSubtitle: {
    ...typography.meta,
    textTransform: "none",
    color: colors.muted,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  // Section rhythm: a thin rule + tracked small-caps label ahead of the
  // "briefs" grid, mirroring the same lead+briefs split on web/admin.
  sectionLabel: {
    ...typography.meta,
    textTransform: "uppercase",
    letterSpacing: 1.2,
    color: colors.faint,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  });
}
