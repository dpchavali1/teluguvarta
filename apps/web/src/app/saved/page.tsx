"use client";

import { useEffect, useState } from "react";

import { StoryCard } from "@/components/StoryCard";
import { apiUrl, type StoryOut } from "@/lib/api";
import { getSavedIds } from "@/lib/saved";

export default function SavedPage() {
  const [stories, setStories] = useState<StoryOut[] | null>(null);
  const [missingCount, setMissingCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const ids = getSavedIds();
      if (ids.length === 0) {
        if (!cancelled) {
          setStories([]);
          setMissingCount(0);
        }
        return;
      }
      // Saved IDs are opaque story ids with no dedicated "fetch by id"
      // endpoint on the public API (§13 only exposes `GET /stories/{slug}`);
      // the feed is small enough in V1 to filter it client-side rather than
      // adding a new endpoint for this one page. A saved story that has
      // aged out of this window is still reported (missingCount) instead
      // of silently disappearing as if it had never been saved.
      const response = await fetch(new URL("/v1/stories?limit=100", apiUrl()));
      const data = (await response.json()) as { items: StoryOut[] };
      if (cancelled) return;
      const matched = data.items.filter((s) => ids.includes(s.id));
      setStories(matched);
      setMissingCount(ids.length - matched.length);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h1>Saved</h1>
      <p>Stories you save are stored on this device only.</p>
      {stories === null ? (
        <p className="empty-state">Loading…</p>
      ) : stories.length === 0 && missingCount === 0 ? (
        <p className="empty-state">You haven&rsquo;t saved any stories yet.</p>
      ) : (
        <>
          {missingCount > 0 && (
            <p className="empty-state">
              {missingCount} saved {missingCount === 1 ? "story is" : "stories are"} older than what&rsquo;s
              shown here and can&rsquo;t be displayed.
            </p>
          )}
          {stories.length > 0 && (
            <ul className="story-list">
              {stories.map((story) => (
                <li key={story.id}>
                  <StoryCard story={story} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}
