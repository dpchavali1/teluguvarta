import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { ApiNetworkError, search, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing, ui } from "../theme/tokens";

const DEBOUNCE_MS = 350;

export function SearchScreen() {
  const { put } = useStoryCache();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const requestId = useRef(0);

  const runSearch = useCallback(
    async (q: string) => {
      const current = ++requestId.current;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (q.trim().length === 0) {
        setResults([]);
        setSearched(false);
        setLoading(false);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const result = await search(q.trim());
        if (current !== requestId.current) return;
        setResults(result.items);
        put(result.items);
        trackEvent("search", { query: q.trim(), result_count: result.items.length });
      } catch (err) {
        if (current !== requestId.current) return;
        setResults([]);
        setError(err instanceof ApiNetworkError ? "You're offline. Check your connection." : "Search failed.");
      } finally {
        if (current === requestId.current) {
          setLoading(false);
          setSearched(true);
        }
      }
    },
    [put]
  );

  function onChangeText(q: string) {
    setQuery(q);
    requestId.current += 1;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { void runSearch(q); return; }
    debounceRef.current = setTimeout(() => runSearch(q), DEBOUNCE_MS);
  }

  useEffect(() => {
    return () => {
      requestId.current += 1;
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
        onSubmitEditing={() => void runSearch(query)}
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
    borderColor: ui.borderControl,
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
