import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { applyMutes } from "@teluguvarta/domain";

import type { StoryOut } from "./api";
import { getHiddenSources, getHiddenTopics, setHiddenSources, setHiddenTopics } from "./storage";

// Plan M5 "Show less of this": topics the reader hid from a card. Kept on the
// device only and filtered client-side. Home and Latest respect it; Topic,
// Search and Saved don't, because there the reader asked for those stories.

interface HiddenTopicsValue {
  hiddenTopics: string[];
  hideTopic: (slug: string) => void;
  showTopic: (slug: string) => void;
  /** P05 "Mute source": source domains hidden from Home and Latest. */
  hiddenSources: string[];
  hideSource: (domain: string) => void;
  showSource: (domain: string) => void;
  /** Empty the lists without writing storage (after "clear data"). */
  resetHiddenTopics: () => void;
}

const HiddenTopicsContext = createContext<HiddenTopicsValue>({
  hiddenTopics: [],
  hideTopic: () => {},
  showTopic: () => {},
  hiddenSources: [],
  hideSource: () => {},
  showSource: () => {},
  resetHiddenTopics: () => {},
});

export function HiddenTopicsProvider({ children }: { children: ReactNode }) {
  const [hiddenTopics, setState] = useState<string[]>([]);
  const [hiddenSources, setSources] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    getHiddenSources().then((stored) => {
      if (active) setSources((current) => [...new Set([...stored, ...current])]);
    });
    return () => {
      active = false;
    };
  }, []);

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
  const updateSources = useCallback((change: (current: string[]) => string[]) => {
    setSources((current) => {
      const next = change(current);
      setHiddenSources(next);
      return next;
    });
  }, []);
  const hideSource = useCallback(
    (domain: string) => updateSources((current) => (current.includes(domain) ? current : [...current, domain])),
    [updateSources],
  );
  const showSource = useCallback((domain: string) => updateSources((current) => current.filter((d) => d !== domain)), [updateSources]);
  const resetHiddenTopics = useCallback(() => {
    setState([]);
    setSources([]);
  }, []);

  const value = useMemo(
    () => ({ hiddenTopics, hideTopic, showTopic, hiddenSources, hideSource, showSource, resetHiddenTopics }),
    [hiddenTopics, hideTopic, showTopic, hiddenSources, hideSource, showSource, resetHiddenTopics],
  );
  return <HiddenTopicsContext.Provider value={value}>{children}</HiddenTopicsContext.Provider>;
}

export function useHiddenTopics(): HiddenTopicsValue {
  return useContext(HiddenTopicsContext);
}

/** Stories not tagged with a hidden topic; breaking/immigration/legal/financial ones always stay (ADR-040). */
export function withoutHiddenTopics(stories: StoryOut[], hiddenTopics: string[], hiddenSources: string[] = []): StoryOut[] {
  if (hiddenTopics.length === 0 && hiddenSources.length === 0) return stories;
  return applyMutes(stories, hiddenTopics, hiddenSources);
}
