import React, { useState } from "react";
import { ActivityIndicator, StyleSheet, TextInput, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { search, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";

export function SearchScreen() {
  const cache = useStoryCache();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  async function runSearch(q: string) {
    setQuery(q);
    if (q.trim().length === 0) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    try {
      const result = await search(q.trim());
      setResults(result.items);
      cache.put(result.items);
      trackEvent("search", { query: q.trim(), result_count: result.items.length });
    } finally {
      setLoading(false);
      setSearched(true);
    }
  }

  return (
    <View style={styles.container}>
      <TextInput
        value={query}
        onChangeText={runSearch}
        placeholder="Search stories"
        accessibilityLabel="Search stories"
        accessibilityHint="Enter keywords to search published stories"
        style={styles.input}
        autoCorrect={false}
        returnKeyType="search"
      />
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator accessibilityLabel="Searching" />
        </View>
      ) : (
        <StoryList
          stories={results}
          emptyLabel={searched ? "No results found." : "Search for a story."}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  input: {
    minHeight: 44,
    margin: 12,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
