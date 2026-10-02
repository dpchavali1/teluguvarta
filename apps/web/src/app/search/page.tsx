import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { TrackEvent } from "@/components/TrackEvent";
import { getConfig, search, SEARCH_RESULT_LIMIT, type SearchResponse, type TopicOut } from "@/lib/api";

export const metadata: Metadata = { title: "Search" };

type Props = { searchParams: Promise<{ q?: string; cursor?: string }> };

async function suggestedTopics(): Promise<TopicOut[]> {
  try {
    return (await getConfig()).topics.filter((topic) => topic.active && topic.story_count > 0).slice(0, 12);
  } catch {
    return [];
  }
}

export default async function SearchPage({ searchParams }: Props) {
  const params = await searchParams;
  const q = params.q?.trim() ?? "";
  const cursor = params.cursor;
  const firstPageUrl = `/search?${new URLSearchParams({ q })}`;
  let results: SearchResponse | null = null;
  let failed = false;
  if (q) {
    try { results = await search(q, cursor); }
    catch { failed = true; }
  }
  const topics = results?.items.length ? [] : await suggestedTopics();

  return (
    <>
      {results && <TrackEvent event="search" properties={{ query: q, result_count: results.items.length }} />}
      <PageHeader eyebrow="Search" title={q ? `Results for “${q}”` : "Search"} />
      <form className="search-form" role="search" action="/search" method="get">
        <label className="visually-hidden" htmlFor="search-q">Search stories</label>
        <span className="search-form__icon" aria-hidden="true"><Icon name="search" size={20} /></span>
        <input id="search-q" type="search" name="q" defaultValue={q} maxLength={200} placeholder="Search stories" enterKeyHint="search" />
        <button className="button button--primary" type="submit">Search</button>
      </form>

      {failed && <div className="callout" role="alert">
        <p>Search couldn’t load. Your search is still in the field above.</p>
        <form action="/search" method="get"><input type="hidden" name="q" value={q} />{cursor !== undefined && <input type="hidden" name="cursor" value={cursor} />}<button className="button" type="submit">Try again</button></form>
        {cursor !== undefined && <Link href={firstPageUrl}>Back to first results</Link>}
        <Link href="/topics">Browse topics</Link>
      </div>}

      {results && (
        <section aria-live="polite">
          <p className="result-count">Showing {results.items.length} {results.items.length === 1 ? "story" : "stories"} on this page · Newest first{results.next_cursor === undefined && results.items.length === SEARCH_RESULT_LIMIT ? ` · Up to ${SEARCH_RESULT_LIMIT} matches shown. Narrow your search to find more.` : ""}</p>
          <StoryGrid stories={results.items} empty={cursor !== undefined ? <>No more stories on this page. <Link href={firstPageUrl}>Back to first results</Link>.</> : <>No stories match &ldquo;{q}&rdquo;. Try a broader word, or <Link href="/topics">browse topics</Link>.</>} />
          {(results.next_cursor || (cursor !== undefined && results.items.length > 0)) && <nav className="pagination" aria-label="Search result pages">
            {cursor !== undefined && results.items.length > 0 && <Link className="button" href={firstPageUrl}>Back to first results</Link>}
            {results.next_cursor && <Link className="button button--primary" href={`/search?${new URLSearchParams({ q, cursor: results.next_cursor })}`}>More results</Link>}
          </nav>}
        </section>
      )}

      {topics.length > 0 && (
        <section className="explore" aria-labelledby="suggested-title">
          <h2 id="suggested-title" className="rail-title">Or browse a topic</h2>
          <ul className="chip-list">
            {topics.map((topic) => (
              <li key={topic.slug}><Link className="chip" href={`/topic/${topic.slug}`}>{topic.name}</Link></li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
