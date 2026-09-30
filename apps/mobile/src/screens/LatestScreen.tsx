import React, { useCallback } from "react";

import { PagedStoryList } from "../components/PagedStoryList";
import { listStories } from "../lib/api";

// Review #14: Home is a bounded ranked set, so this is the way to every
// published story, newest first — the same `/v1/stories` list web's /latest uses.
export function LatestScreen() {
  const fetchPage = useCallback(async (cursor?: string) => {
    const page = await listStories({ cursor });
    return { stories: page.items, next_cursor: page.next_cursor };
  }, []);

  return (
    <PagedStoryList
      fetchPage={fetchPage}
      loadingLabel="Loading latest stories"
      errorLabel="Couldn't load the latest stories."
      emptyLabel="No stories yet."
    />
  );
}
