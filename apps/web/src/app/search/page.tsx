import type { Metadata } from "next";

import { StoryCard } from "@/components/StoryCard";
import { search } from "@/lib/api";

export const metadata: Metadata = { title: "Search" };

type Props = { searchParams: { q?: string } };

export default async function SearchPage({ searchParams }: Props) {
  const q = searchParams.q?.trim() ?? "";
  const results = q.length > 0 ? await search(q) : null;

  return (
    <>
      <h1>Search</h1>
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
            <ul className="story-list">
              {results.items.map((story) => (
                <li key={story.id}>
                  <StoryCard story={story} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
