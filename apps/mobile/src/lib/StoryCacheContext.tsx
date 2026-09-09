import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import type { StoryOut } from "./api";

// No `/v1/stories?ids=` bulk-lookup endpoint exists (out of scope for T15 —
// the public API surface is T14's, unchanged here), so the Saved screen
// can't ask the server "give me these N saved stories" directly. Instead,
// every screen that fetches stories (home, topic, search, story detail)
// feeds them into this in-memory cache; Saved then renders whichever saved
// ids happen to be cached. A saved story the user hasn't recently viewed
// elsewhere in the session simply won't render until it's seen again —
// documented as a known limitation in PROGRESS.md, not silently swallowed.
type StoryCacheContextValue = {
  get: (id: string) => StoryOut | undefined;
  put: (stories: StoryOut[]) => void;
  all: () => StoryOut[];
};

const StoryCacheContext = createContext<StoryCacheContextValue | null>(null);

export function StoryCacheProvider({ children }: { children: React.ReactNode }) {
  const mapRef = useRef(new Map<string, StoryOut>());
  const [, setVersion] = useState(0);

  const put = useCallback((stories: StoryOut[]) => {
    let changed = false;
    for (const story of stories) {
      if (mapRef.current.get(story.id) !== story) changed = true;
      mapRef.current.set(story.id, story);
    }
    if (changed) setVersion((v) => v + 1);
  }, []);

  const get = useCallback((id: string) => mapRef.current.get(id), []);
  const all = useCallback(() => Array.from(mapRef.current.values()), []);

  const value = useMemo(() => ({ get, put, all }), [get, put, all]);

  return <StoryCacheContext.Provider value={value}>{children}</StoryCacheContext.Provider>;
}

export function useStoryCache(): StoryCacheContextValue {
  const ctx = useContext(StoryCacheContext);
  if (!ctx) throw new Error("useStoryCache must be used within StoryCacheProvider");
  return ctx;
}
