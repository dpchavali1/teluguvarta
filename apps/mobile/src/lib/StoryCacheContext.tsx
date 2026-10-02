import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { StoryOut } from "./api";
import { getReadIds, getSavedIds, READ_HISTORY_LIMIT, setReadIds, toggleSaved as toggleSavedStorage } from "./storage";

// Cached content accelerates reading; Saved always resolves current data from the API.
// Memory only: nothing here survives an app restart. Persisted offline reading
// needs expiry and correction/retraction rules decided in an ADR first (review R10).
type StoryCacheContextValue = {
  savedIds: string[];
  savedReady: boolean;
  get: (id: string) => StoryOut | undefined;
  // Story detail opens from the cached copy while it refreshes, and falls
  // back to it (labelled with `loadedAt`) when the refresh fails offline.
  getBySlug: (canonicalSlug: string) => { story: StoryOut; loadedAt: number } | undefined;
  // Drops a story the API no longer serves (404: unpublished or retracted),
  // so a stale copy is never shown for it again.
  remove: (id: string) => void;
  put: (stories: StoryOut[]) => void;
  all: () => StoryOut[];
  // Design-review fix: every StoryCard previously read+parsed the whole
  // saved-ids array from AsyncStorage on its own, once per mount and again
  // on every toggle — N redundant storage reads per screen. Loaded once
  // here and shared; toggling updates the in-memory set and re-renders
  // subscribers without a fresh read.
  isSaved: (id: string) => boolean;
  toggleSaved: (id: string) => Promise<boolean>;
  // Plan M6: stories opened on this device, newest first (capped).
  readIds: string[];
  readReady: boolean;
  isRead: (id: string) => boolean;
  markRead: (id: string) => void;
  clearReadHistory: () => void;
  /** Forget saved and read ids in memory after "clear data" removed them from storage. */
  resetLocalData: () => void;
};

const StoryCacheContext = createContext<StoryCacheContextValue | null>(null);

export function StoryCacheProvider({ children }: { children: React.ReactNode }) {
  const mapRef = useRef(new Map<string, StoryOut>());
  const loadedAtRef = useRef(new Map<string, number>());
  const savedIdsRef = useRef<Set<string>>(new Set());
  const localGeneration = useRef(0);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [savedReady, setSavedReady] = useState(false);
  const [version, setVersion] = useState(0);
  const [readIds, setReadState] = useState<string[]>([]);
  const [readReady, setReadReady] = useState(false);

  useEffect(() => {
    let active = true;
    const generation = localGeneration.current;
    getSavedIds().then((ids) => {
      if (!active || localGeneration.current !== generation) return;
      savedIdsRef.current = new Set(ids);
      setSavedIds(ids);
      setSavedReady(true);
    });
    getReadIds().then((ids) => {
      if (!active || localGeneration.current !== generation) return;
      // A story opened before the read finished stays on top.
      setReadState((current) => [...new Set([...current, ...ids])].slice(0, READ_HISTORY_LIMIT));
      setReadReady(true);
    });
    return () => { active = false; };
  }, []);

  const put = useCallback((stories: StoryOut[]) => {
    let changed = false;
    const now = Date.now();
    for (const story of stories) {
      if (mapRef.current.get(story.id) !== story) changed = true;
      mapRef.current.set(story.id, story);
      loadedAtRef.current.set(story.id, now);
    }
    if (changed) setVersion((v) => v + 1);
  }, []);

  const remove = useCallback((id: string) => {
    loadedAtRef.current.delete(id);
    if (mapRef.current.delete(id)) setVersion((v) => v + 1);
  }, []);

  const get = useCallback((id: string) => mapRef.current.get(id), []);
  const getBySlug = useCallback((canonicalSlug: string) => {
    for (const story of mapRef.current.values()) {
      if (story.canonical_slug === canonicalSlug) {
        return { story, loadedAt: loadedAtRef.current.get(story.id) ?? Date.now() };
      }
    }
    return undefined;
  }, []);
  const all = useCallback(() => Array.from(mapRef.current.values()), []);
  const isSaved = useCallback((id: string) => savedIdsRef.current.has(id), []);
  const toggleSaved = useCallback(async (id: string) => {
    const next = await toggleSavedStorage(id);
    if (next) savedIdsRef.current.add(id);
    else savedIdsRef.current.delete(id);
    setSavedIds([...savedIdsRef.current]);
    return next;
  }, []);

  const readSet = useMemo(() => new Set(readIds), [readIds]);
  const isRead = useCallback((id: string) => readSet.has(id), [readSet]);
  const markRead = useCallback((id: string) => {
    setReadState((current) => {
      if (current[0] === id) return current;
      const next = [id, ...current.filter((other) => other !== id)].slice(0, READ_HISTORY_LIMIT);
      setReadIds(next);
      return next;
    });
  }, []);
  const clearReadHistory = useCallback(() => {
    setReadState([]);
    setReadIds([]);
  }, []);
  const resetLocalData = useCallback(() => {
    localGeneration.current += 1;
    mapRef.current.clear();
    loadedAtRef.current.clear();
    setVersion((value) => value + 1);
    setSavedReady(true);
    setReadReady(true);
    savedIdsRef.current = new Set();
    setSavedIds([]);
    setReadState([]);
  }, []);

  // `version` is otherwise unused here, but it must be a memo dependency:
  // get/put/all/isSaved/toggleSaved are stable useCallback references, so
  // without it `value`'s identity would never change and React's context
  // propagation would never notify subscribers (e.g. StoryCard's `saved`
  // read) that the underlying ref data changed.
  const value = useMemo(
    () => ({
      get, getBySlug, remove, put, all, isSaved, toggleSaved, savedIds, savedReady,
      readIds, readReady, isRead, markRead, clearReadHistory, resetLocalData,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [get, getBySlug, remove, put, all, isSaved, toggleSaved, version, savedIds, savedReady,
      readIds, readReady, isRead, markRead, clearReadHistory, resetLocalData]
  );

  return <StoryCacheContext.Provider value={value}>{children}</StoryCacheContext.Provider>;
}

export function useStoryCache(): StoryCacheContextValue {
  const ctx = useContext(StoryCacheContext);
  if (!ctx) throw new Error("useStoryCache must be used within StoryCacheProvider");
  return ctx;
}
