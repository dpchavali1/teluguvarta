import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { TrackEvent } from "@/components/TrackEvent";
import { getConfig, search, type TopicOut } from "@/lib/api";

export const metadata: Metadata = { title: "Search" };

type Props = { searchParams: Promise<{ q?: string }> };

async function suggestedTopics(): Promise<TopicOut[]> {
  try {
    return (await getConfig()).topics.filter((topic) => topic.active && topic.story_count > 0).slice(0, 12);
  } catch {
    return [];
  }
}

export default async function SearchPage({ searchParams }: Props) {
  const q = (await searchParams).q?.trim() ?? "";
  const results = q.length > 0 ? await search(q) : null;
  const topics = results ? [] : await suggestedTopics();

  return (
    <>
      {results && <TrackEvent event="search" properties={{ query: q, result_count: results.items.length }} />}
      <PageHeader eyebrow="Search" title={results ? `Results for “${q}”` : "Search"} />
      <form className="search-form" role="search" action="/search" method="get">
        <label className="visually-hidden" htmlFor="search-q">Search stories</label>
        <span className="search-form__icon" aria-hidden="true"><Icon name="search" size={20} /></span>
        <input id="search-q" type="search" name="q" defaultValue={q} placeholder="Search stories" enterKeyHint="search" />
        <button className="button button--primary" type="submit">Search</button>
      </form>

      {results && (
        <section aria-live="polite">
          <p className="result-count">{results.items.length} {results.items.length === 1 ? "story" : "stories"}</p>
          <StoryGrid stories={results.items} empty={<>No stories match &ldquo;{q}&rdquo;. Try a broader word, or <Link href="/topics">browse topics</Link>.</>} />
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
