import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { FlatList, Linking, StyleSheet, Text, View } from "react-native";

import type { StoryOut } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";
import { StoryCard } from "./StoryCard";

export function StoryList({
  stories,
  emptyLabel = "No stories yet.",
  onRefresh,
  refreshing,
}: {
  stories: StoryOut[];
  emptyLabel?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <FlatList
      data={stories}
      keyExtractor={(story) => story.id}
      renderItem={({ item }) => (
        <StoryCard
          story={item}
          onOpen={() => navigation.navigate("StoryDetail", { slug: item.canonical_slug })}
          onOpenSource={(url) => Linking.openURL(url)}
        />
      )}
      onRefresh={onRefresh}
      refreshing={refreshing ?? false}
      ListEmptyComponent={
        <View style={styles.empty}>
          <Text>{emptyLabel}</Text>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  empty: { padding: 24, alignItems: "center" },
});
