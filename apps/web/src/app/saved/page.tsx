"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SkeletonGrid } from "@/components/Skeleton";
import { SavedOrganizer } from "@/components/SavedOrganizer";
import { StoryCard } from "@/components/StoryCard";
import { PageHeader } from "@/components/StoryGrid";
import { getSavedStories, type StoryOut } from "@/lib/api";
import { getSavedIds, SAVED_CHANGE_EVENT } from "@/lib/saved";
import { readExtras, SAVED_EXTRAS_CHANGE_EVENT, writeExtras } from "@/lib/savedExtras";
import {
  MAX_COLLECTION_NAME, addCollection, deleteCollection, idsInCollection, type SavedExtras,
} from "@teluguvarta/domain/savedExtras.ts";

export default function SavedPage() {
  const [stories, setStories] = useState<StoryOut[] | null>(null);
  const [missingCount, setMissingCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [extras, setExtras] = useState<SavedExtras>(() => readExtras());
  const [filter, setFilter] = useState<string | null>(null);
  const [newList, setNewList] = useState("");
  const [extrasError, setExtrasError] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setExtras(readExtras());
    sync();
    window.addEventListener(SAVED_EXTRAS_CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(SAVED_EXTRAS_CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  function update(next: SavedExtras) {
    try { writeExtras(next); setExtrasError(null); }
    catch { setExtrasError("That change couldn’t be kept. Check that browser storage is available."); }
  }

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
    let ids: string[];
    try { ids = getSavedIds(true); }
    catch {
      setError("Your bookmarks couldn’t be read from this browser. Check that browser storage is available, then try again.");
      return;
    }
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
      : stories === null ? <><p className="visually-hidden" role="status">Loading saved stories…</p><SkeletonGrid count={1} /></>
      : <>
        {missingCount > 0 && <p className="callout" role="status">{missingCount} saved {missingCount === 1 ? "story is" : "stories are"} currently unavailable. Your bookmarks have been kept. <Link href="/latest">Browse latest stories</Link>.</p>}
        <SavedLists extras={extras} filter={filter} setFilter={setFilter} newList={newList} setNewList={setNewList} update={update} error={extrasError} />
        <SavedGrid stories={stories} extras={extras} filter={filter} update={update} empty={missingCount === 0 ? <>No saved stories yet. Tap the bookmark on any story to keep it here. <Link href="/">Find a story to save</Link>.</> : <>No saved stories are available right now. <Link href="/latest">Browse latest stories</Link>.</>} />
      </>}
  </>;
}

function SavedLists({ extras, filter, setFilter, newList, setNewList, update, error }: {
  extras: SavedExtras; filter: string | null; setFilter: (id: string | null) => void;
  newList: string; setNewList: (value: string) => void; update: (next: SavedExtras) => void; error: string | null;
}) {
  function create(event: React.FormEvent) {
    event.preventDefault();
    const next = addCollection(extras, newList, crypto.randomUUID());
    if (next !== extras) update(next);
    setNewList("");
  }
  const active = extras.collections.find((c) => c.id === filter);
  return <section aria-label="Lists">
    <ul className="chip-list">
      <li><button type="button" className="chip" aria-pressed={filter === null} onClick={() => setFilter(null)}>All</button></li>
      {extras.collections.map((c) => (
        <li key={c.id}><button type="button" className="chip" aria-pressed={filter === c.id} onClick={() => setFilter(c.id)}>{c.name}</button></li>
      ))}
    </ul>
    <form onSubmit={create}>
      <label htmlFor="new-list">New list</label>{" "}
      <input id="new-list" type="text" value={newList} maxLength={MAX_COLLECTION_NAME} onChange={(event) => setNewList(event.target.value)} />{" "}
      <button type="submit" className="button button--small" disabled={!newList.trim()}>Create list</button>
    </form>
    {active ? <p><button type="button" className="button button--small" onClick={() => { update(deleteCollection(extras, active.id)); setFilter(null); }}>Delete list “{active.name}”</button> Stories stay saved.</p> : null}
    {error ? <p role="alert">{error}</p> : null}
  </section>;
}

function SavedGrid({ stories, extras, filter, update, empty }: {
  stories: StoryOut[]; extras: SavedExtras; filter: string | null; update: (next: SavedExtras) => void; empty: React.ReactNode;
}) {
  const visible = filter ? stories.filter((s) => idsInCollection(extras, stories.map((x) => x.id), filter).includes(s.id)) : stories;
  if (visible.length === 0) return <div className="empty-state">{filter ? "No saved stories in this list yet. Use Organize on a saved story to add it." : empty}</div>;
  return <ul className="story-grid">
    {visible.map((story) => (
      <li key={story.id}>
        <StoryCard story={story} display="brief" />
        <SavedOrganizer storyId={story.id} extras={extras} onChange={update} />
      </li>
    ))}
  </ul>;
}
