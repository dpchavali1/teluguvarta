import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { ApiNetworkError, search, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing } from "../theme/tokens";

const DEBOUNCE_MS = 350;

export function SearchScreen() {
  const cache = useStoryCache();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = useCallback(
    async (q: string) => {
      if (q.trim().length === 0) {
        setResults([]);
        setSearched(false);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await search(q.trim());
        setResults(result.items);
        cache.put(result.items);
        trackEvent("search", { query: q.trim(), result_count: result.items.length });
      } catch (err) {
        setResults([]);
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : "Search failed.");
      } finally {
        setLoading(false);
        setSearched(true);
      }
    },
    [cache]
  );

  function onChangeText(q: string) {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    // Design-review fix: previously fired a network request on every
    // keystroke with no debounce.
    debounceRef.current = setTimeout(() => runSearch(q), DEBOUNCE_MS);
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <View style={styles.container}>
      <TextInput
        value={query}
        onChangeText={onChangeText}
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
      ) : error ? (
        <View style={styles.center}>
          <Text>{error}</Text>
          <Pressable
            onPress={() => runSearch(query)}
            accessibilityRole="button"
            accessibilityLabel="Retry"
            style={styles.retryButton}
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
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
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  // Ink-filled button, matching apps/web's main button.
  retryButton: {
    minHeight: 44,
    minWidth: 44,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: radius.pill,
    backgroundColor: colors.text,
  },
  retryButtonText: { color: colors.bg, fontWeight: "600" },
});
