import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";

import { StoryList } from "../components/StoryList";
import type { StoryOut } from "../lib/api";
import { useStoryCache } from "../lib/StoryCacheContext";
import { getSavedIds } from "../lib/storage";

export function SavedScreen() {
  const cache = useStoryCache();
  const [savedStories, setSavedStories] = useState<StoryOut[]>([]);

  // Refresh on focus (not just mount) so a save/unsave made on another
  // screen is reflected immediately when the user switches to this tab.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getSavedIds().then((ids) => {
        if (cancelled) return;
        const stories = ids.map((id) => cache.get(id)).filter((s): s is StoryOut => Boolean(s));
        setSavedStories(stories);
      });
      return () => {
        cancelled = true;
      };
    }, [cache])
  );

  return (
    <StoryList
      stories={savedStories}
      emptyLabel="Nothing saved yet. Save a story from the feed to find it here."
    />
  );
}
