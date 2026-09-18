import Link from "next/link";
import type { Metadata } from "next";

import { StoryCard } from "@/components/StoryCard";
import { listStories } from "@/lib/api";

export const revalidate = 60;
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ code: string }>; searchParams: Promise<{ cursor?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const code = (await params).code.toUpperCase();
  return { title: `${code} news`, description: `Latest stories about ${code} on TTE.` };
}

export default async function CountryPage({ params, searchParams }: Props) {
  const code = (await params).code.toUpperCase();
  const { items, next_cursor } = await listStories({ country: code, cursor: (await searchParams).cursor });

  return (
    <>
      <header className="listing-header">
        <p className="eyebrow">TTE · Country</p>
        <h1>{code} news</h1>
      </header>
      {items.length === 0 ? (
        <p className="empty-state">No published stories about {code} yet.</p>
      ) : (
        <ul className="story-grid">
          {items.map((story) => (
            <li key={story.id}>
              <StoryCard story={story} display="brief" />
            </li>
          ))}
        </ul>
      )}
      <nav className="pagination" aria-label="Story pages">{next_cursor && <Link href={`/country/${code}?cursor=${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
        {(await searchParams).cursor && <Link href={`/country/${code}`}>Latest in this country</Link>}</nav>
    </>
  );
}
