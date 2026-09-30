import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { FlatList, Linking, StyleSheet, Text, View } from "react-native";

import type { StoryOut } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";
import { spacing } from "../theme/tokens";
import { useAppTheme } from "../theme/useAppTheme";
import { StoryCard } from "./StoryCard";

export function StoryList({
  stories,
  emptyLabel = "No stories yet.",
  onRefresh,
  refreshing,
  footer,
}: {
  stories: StoryOut[];
  emptyLabel?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  footer?: React.ReactElement;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useAppTheme();

  return (
    <FlatList
      data={stories}
      keyExtractor={(story) => story.id}
      renderItem={({ item }) => (
        <StoryCard
          story={item}
          layout="compact"
          onOpen={() => navigation.navigate("StoryDetail", { slug: item.canonical_slug })}
          onOpenSource={(url) => Linking.openURL(url)}
        />
      )}
      onRefresh={onRefresh}
      refreshing={refreshing ?? false}
      ListFooterComponent={footer}
      ListEmptyComponent={
        <View style={styles.empty}>
          <Text style={[styles.emptyText, { color: colors.muted }]}>{emptyLabel}</Text>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  empty: { padding: spacing.xl, alignItems: "center" },
  emptyText: { textAlign: "center" },
});
