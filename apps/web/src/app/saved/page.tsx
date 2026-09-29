"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SkeletonGrid } from "@/components/Skeleton";
import { PageHeader, StoryGrid } from "@/components/StoryGrid";
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
    <PageHeader eyebrow="Your library" title="Saved">Your bookmarks stay on this device. Stories are checked for the latest updates when you open this page.</PageHeader>
    {error ? <div className="callout" role="alert"><p>{error}</p><button className="button" onClick={() => setRevision((value) => value + 1)}>Try again</button></div>
      : stories === null ? <><p className="visually-hidden" role="status">Loading saved stories…</p><SkeletonGrid count={3} /></>
      : <>
        {missingCount > 0 && <p className="callout" role="status">{missingCount} saved {missingCount === 1 ? "story is" : "stories are"} currently unavailable. Your bookmarks have been kept.</p>}
        <StoryGrid stories={stories} empty={missingCount === 0 ? <>No saved stories yet. Tap the bookmark on any story to keep it here. <Link href="/">Find a story to save</Link>.</> : undefined} />
      </>}
  </>;
}
