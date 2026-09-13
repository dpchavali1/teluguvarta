"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { StoryCard } from "@/components/StoryCard";
import { getSavedStories, type StoryOut } from "@/lib/api";
import { getSavedIds, SAVED_CHANGE_EVENT } from "@/lib/saved";

export default function SavedPage() {
  const [stories, setStories] = useState<StoryOut[] | null>(null);
  const [missingCount, setMissingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const refresh = () => setRevision((value) => value + 1);
    window.addEventListener(SAVED_CHANGE_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(SAVED_CHANGE_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const ids = getSavedIds();
    getSavedStories(ids).then((items) => {
      if (cancelled) return;
      setStories(items);
      setMissingCount(ids.length - items.length);
    }).catch(() => {
      if (!cancelled) setError("Couldn't load your saved stories. Your bookmarks are still saved.");
    });
    return () => { cancelled = true; };
  }, [revision]);

  return <>
    <h1>Saved</h1>
    <p>Your bookmarks stay on this device. Stories are checked for the latest updates when you open this page.</p>
    {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((value) => value + 1)}>Try again</button></div>
      : stories === null ? <p role="status">Loading saved stories…</p>
      : <>
        {missingCount > 0 && <p role="status">{missingCount} saved {missingCount === 1 ? "story is" : "stories are"} currently unavailable. Your bookmarks have been kept.</p>}
        {stories.length === 0 && missingCount === 0 && <p className="empty-state">No saved stories yet. <Link href="/">Find a story to save</Link>.</p>}
        <ul className="story-list">{stories.map((story) => <li key={story.id}><StoryCard story={story} /></li>)}</ul>
      </>}
  </>;
}
