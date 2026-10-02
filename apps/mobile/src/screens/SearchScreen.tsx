import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/types";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { StoryList } from "../components/StoryList";
import { ApiNetworkError, search, SEARCH_RESULT_LIMIT, trackEvent, type StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

const DEBOUNCE_MS = 350;

export function SearchScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const { put } = useStoryCache();
  const [query, setQuery] = useState("");
  const [resultQuery, setResultQuery] = useState("");
  const [results, setResults] = useState<StoryOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null | undefined>(undefined);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const paging = useRef(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const requestId = useRef(0);

  const runSearch = useCallback(
    async (q: string) => {
      const current = ++requestId.current;
      paging.current = false;
      setLoadingMore(false);
      setPageError(null);
      setNextCursor(undefined);
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
      setResultQuery(q.trim());
      try {
        const result = await search(q.trim());
        if (current !== requestId.current) return;
        setResults(result.items);
        setNextCursor(result.next_cursor);
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

  async function loadMore() {
    if (!nextCursor || paging.current || loading) return;
    const current = requestId.current;
    paging.current = true;
    setLoadingMore(true);
    setPageError(null);
    try {
      const page = await search(resultQuery, nextCursor);
      if (current !== requestId.current) return;
      setResults((previous) => [...new Map([...previous, ...page.items].map((story) => [story.id, story])).values()]);
      setNextCursor(page.next_cursor);
      put(page.items);
    } catch (err) {
      if (current !== requestId.current) return;
      setPageError(err instanceof ApiNetworkError ? "You're offline. Earlier results are still here." : "Couldn't load more results. Earlier results are still here.");
    } finally {
      if (current === requestId.current) {
        paging.current = false;
        setLoadingMore(false);
      }
    }
  }

  function onChangeText(q: string) {
    setQuery(q);
    requestId.current += 1;
    paging.current = false;
    setLoadingMore(false);
    setPageError(null);
    setNextCursor(undefined);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { void runSearch(q); return; }
    setLoading(true);
    setSearched(false);
    setError(null);
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
      <View style={styles.searchRow}>
      <TextInput
        value={query}
        maxLength={200}
        onChangeText={onChangeText}
        placeholder="Search stories"
        placeholderTextColor={ui.textTertiary}
        accessibilityLabel="Search stories"
        accessibilityHint="Enter keywords to search published stories"
        style={styles.input}
        autoCorrect={false}
        returnKeyType="search"
        onSubmitEditing={() => void runSearch(query)}
      />
      {query.length > 0 && <Pressable onPress={() => onChangeText("")} accessibilityRole="button" accessibilityLabel="Clear search" style={styles.clearButton}><Text style={styles.retryButtonText}>Clear</Text></Pressable>}
      </View>
      {searched && !loading && !error && <Text style={styles.resultCount} accessibilityLiveRegion="polite">
        Showing {results.length} {results.length === 1 ? "story" : "stories"} · Newest first{nextCursor === undefined && results.length === SEARCH_RESULT_LIMIT ? ` · Up to ${SEARCH_RESULT_LIMIT} matches shown. Narrow your search to find more.` : ""}
      </Text>}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator accessibilityLabel="Searching" />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.message} accessibilityRole="alert">{error}</Text>
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
          emptyLabel={searched ? `No stories match “${resultQuery}”. Try a broader word or browse topics.` : "Search for a story."}
          footer={results.length === 0 ? <Pressable onPress={() => navigation.navigate("Main", { screen: "Topics" })} accessibilityRole="button" style={styles.browseButton}><Text style={styles.message}>Browse topics</Text></Pressable> : nextCursor ? <View style={styles.pageFooter}>
            {pageError && <Text style={styles.message} accessibilityRole="alert">{pageError}</Text>}
            {loadingMore && <ActivityIndicator accessibilityLabel="Loading more results" />}
            <Pressable onPress={() => void loadMore()} disabled={loadingMore} accessibilityRole="button" accessibilityState={{ disabled: loadingMore, busy: loadingMore }} style={styles.retryButton}>
              <Text style={styles.retryButtonText}>{pageError ? "Retry more results" : "More results"}</Text>
            </Pressable>
          </View> : undefined}
        />
      )}
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    message: { color: colors.text, textAlign: "center", paddingHorizontal: spacing.lg },
    searchRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, margin: spacing.md },
    clearButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.sm, borderRadius: radius.md, backgroundColor: colors.text },
    browseButton: { minHeight: 44, justifyContent: "center", alignSelf: "center" },
    resultCount: { color: colors.muted, paddingHorizontal: spacing.md, paddingBottom: spacing.sm },
    pageFooter: { padding: spacing.lg, gap: spacing.md, alignItems: "center" },
    input: {
      flex: 1,
      minHeight: 44,
      paddingHorizontal: 12,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
      color: colors.text,
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
      borderCurve: "continuous",
      backgroundColor: colors.text,
    },
    retryButtonText: { color: colors.bg, fontWeight: "600" },
  });
}
