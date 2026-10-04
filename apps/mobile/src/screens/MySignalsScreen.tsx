import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { topicLabel } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useHiddenTopics } from "../lib/HiddenTopicsContext";
import { getFollowedPlaces, getProfile } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import type { RootStackParamList } from "../navigation/types";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// P05 / ADR-040: everything that shapes My Edit, in one place. All signals are
// explicit choices stored on this device; nothing is inferred from reading.
export function MySignalsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { hiddenTopics, showTopic, hiddenSources, showSource } = useHiddenTopics();
  const { savedIds } = useStoryCache();
  const [followedTopics, setFollowedTopics] = useState<string[]>([]);
  const [places, setPlaces] = useState<string[]>([]);

  useEffect(() => {
    void getProfile().then((p) => setFollowedTopics(p.interestTopicSlugs));
    void getFollowedPlaces().then((list) => setPlaces(list.map((p) => p.placeId)));
  }, []);

  const none = "None";
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        My Edit uses only the choices below. Breaking, immigration, legal and financial news is never hidden by a mute.
      </Text>
      <Group title="Followed topics" styles={styles}>
        <Text style={styles.value}>{followedTopics.length ? followedTopics.map(topicLabel).join(", ") : none}</Text>
        <Link label="Change topics" onPress={() => navigation.navigate("Main", { screen: "Topics" })} styles={styles} />
      </Group>
      <Group title="Followed places" styles={styles}>
        <Text style={styles.value}>{places.length ? places.join(", ") : none}</Text>
        <Link label="Change places" onPress={() => navigation.navigate("Places")} styles={styles} />
      </Group>
      <Group title="Hidden topics (Show less)" styles={styles}>
        <Text style={styles.value}>{hiddenTopics.length ? hiddenTopics.map(topicLabel).join(", ") : none}</Text>
        {hiddenTopics.length > 0 && (
          <Link label="Reset hidden topics" onPress={() => [...hiddenTopics].forEach(showTopic)} styles={styles} />
        )}
      </Group>
      <Group title="Muted sources" styles={styles}>
        <Text style={styles.value}>{hiddenSources.length ? hiddenSources.join(", ") : none}</Text>
        {hiddenSources.length > 0 && (
          <Link label="Reset muted sources" onPress={() => [...hiddenSources].forEach(showSource)} styles={styles} />
        )}
      </Group>
      <Group title="Saved stories" styles={styles}>
        <Text style={styles.value}>{savedIds.length} saved</Text>
        <Link label="Open Saved" onPress={() => navigation.navigate("Main", { screen: "Saved" })} styles={styles} />
      </Group>
    </ScrollView>
  );
}

function Group({ title, children, styles }: { title: string; children: React.ReactNode; styles: ReturnType<typeof createStyles> }) {
  return (
    <View style={styles.group}>
      <Text style={styles.title} accessibilityRole="header">{title}</Text>
      {children}
    </View>
  );
}

function Link({ label, onPress, styles }: { label: string; onPress: () => void; styles: ReturnType<typeof createStyles> }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={styles.button}>
      <Text style={styles.buttonText}>{label}</Text>
    </Pressable>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xl },
    intro: { ...typography.body, color: ui.textSecondary },
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      padding: spacing.md,
      gap: spacing.sm,
    },
    title: { ...typography.body, color: colors.text, fontWeight: "600" },
    value: { ...typography.body, color: ui.textSecondary },
    button: { alignSelf: "flex-start", paddingVertical: spacing.sm },
    buttonText: { ...typography.body, color: colors.text, textDecorationLine: "underline" },
  });
}
