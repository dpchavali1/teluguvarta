import type { Metadata } from "next";

import { StoryCard } from "@/components/StoryCard";
import { TrackEvent } from "@/components/TrackEvent";
import { search } from "@/lib/api";

export const metadata: Metadata = { title: "Search" };

type Props = { searchParams: Promise<{ q?: string }> };

export default async function SearchPage({ searchParams }: Props) {
  const q = (await searchParams).q?.trim() ?? "";
  const results = q.length > 0 ? await search(q) : null;

  return (
    <>
      {results && <TrackEvent event="search" properties={{ query: q, result_count: results.items.length }} />}
      <header className="listing-header">
        <p className="eyebrow">TTE · Search</p>
        <h1>Search</h1>
      </header>
      <form className="search-form" role="search" action="/search" method="get">
        <label className="visually-hidden" htmlFor="search-q">Search stories</label>
        <input id="search-q" type="search" name="q" defaultValue={q} placeholder="Search headlines and summaries" />
        <button type="submit">Search</button>
      </form>

      {results && (
        <section aria-live="polite">
          {results.items.length === 0 ? (
            <p className="empty-state">No stories match &ldquo;{q}&rdquo;.</p>
          ) : (
            <ul className="story-grid">
              {results.items.map((story) => (
                <li key={story.id}>
                  <StoryCard story={story} display="brief" />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
