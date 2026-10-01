import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { StoryOut } from "./api";
import { getHiddenTopics, setHiddenTopics } from "./storage";

// Plan M5 "Show less of this": topics the reader hid from a card. Kept on the
// device only and filtered client-side. Home and Latest respect it; Topic,
// Search and Saved don't, because there the reader asked for those stories.

interface HiddenTopicsValue {
  hiddenTopics: string[];
  hideTopic: (slug: string) => void;
  showTopic: (slug: string) => void;
  /** Empty the list without writing storage (after "clear data"). */
  resetHiddenTopics: () => void;
}

const HiddenTopicsContext = createContext<HiddenTopicsValue>({
  hiddenTopics: [],
  hideTopic: () => {},
  showTopic: () => {},
  resetHiddenTopics: () => {},
});

export function HiddenTopicsProvider({ children }: { children: ReactNode }) {
  const [hiddenTopics, setState] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    getHiddenTopics().then((stored) => {
      // A hide made before the read finished wins over an empty stored list.
      if (active) setState((current) => [...new Set([...stored, ...current])]);
    });
    return () => {
      active = false;
    };
  }, []);

  const update = useCallback((change: (current: string[]) => string[]) => {
    setState((current) => {
      const next = change(current);
      setHiddenTopics(next);
      return next;
    });
  }, []);

  const hideTopic = useCallback(
    (slug: string) => update((current) => (current.includes(slug) ? current : [...current, slug])),
    [update],
  );
  const showTopic = useCallback((slug: string) => update((current) => current.filter((s) => s !== slug)), [update]);
  const resetHiddenTopics = useCallback(() => setState([]), []);

  const value = useMemo(
    () => ({ hiddenTopics, hideTopic, showTopic, resetHiddenTopics }),
    [hiddenTopics, hideTopic, showTopic, resetHiddenTopics],
  );
  return <HiddenTopicsContext.Provider value={value}>{children}</HiddenTopicsContext.Provider>;
}

export function useHiddenTopics(): HiddenTopicsValue {
  return useContext(HiddenTopicsContext);
}

/** Stories not tagged with any hidden topic. Returns the same array when nothing is hidden. */
export function withoutHiddenTopics(stories: StoryOut[], hiddenTopics: string[]): StoryOut[] {
  if (hiddenTopics.length === 0) return stories;
  return stories.filter((story) => !story.topics.some((slug) => hiddenTopics.includes(slug)));
}
