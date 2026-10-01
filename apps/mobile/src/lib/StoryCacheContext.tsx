import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { StoryOut } from "./api";
import { getSavedIds, toggleSaved as toggleSavedStorage } from "./storage";

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
};

const StoryCacheContext = createContext<StoryCacheContextValue | null>(null);

export function StoryCacheProvider({ children }: { children: React.ReactNode }) {
  const mapRef = useRef(new Map<string, StoryOut>());
  const loadedAtRef = useRef(new Map<string, number>());
  const savedIdsRef = useRef<Set<string>>(new Set());
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [savedReady, setSavedReady] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    getSavedIds().then((ids) => {
      savedIdsRef.current = new Set(ids);
      setSavedIds(ids);
      setSavedReady(true);
    });
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

  // `version` is otherwise unused here, but it must be a memo dependency:
  // get/put/all/isSaved/toggleSaved are stable useCallback references, so
  // without it `value`'s identity would never change and React's context
  // propagation would never notify subscribers (e.g. StoryCard's `saved`
  // read) that the underlying ref data changed.
  const value = useMemo(
    () => ({ get, getBySlug, remove, put, all, isSaved, toggleSaved, savedIds, savedReady }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [get, getBySlug, remove, put, all, isSaved, toggleSaved, version, savedIds, savedReady]
  );

  return <StoryCacheContext.Provider value={value}>{children}</StoryCacheContext.Provider>;
}

export function useStoryCache(): StoryCacheContextValue {
  const ctx = useContext(StoryCacheContext);
  if (!ctx) throw new Error("useStoryCache must be used within StoryCacheProvider");
  return ctx;
}
