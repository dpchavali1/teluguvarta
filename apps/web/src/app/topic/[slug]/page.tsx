import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { StoryCard } from "@/components/StoryCard";
import { ApiNotFoundError, getTopic } from "@/lib/api";

export const revalidate = 60;
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ cursor?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const { topic } = await getTopic(slug);
    return { title: topic.name, description: `Latest ${topic.name} stories on TTE.` };
  } catch (err) {
    if (err instanceof ApiNotFoundError) return {};
    throw err;
  }
}

export default async function TopicPage({ params, searchParams }: Props) {
  const { slug } = await params;
  let data;
  try {
    data = await getTopic(slug, (await searchParams).cursor);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }

  return (
    <>
      <header className="listing-header">
        <p className="eyebrow">TTE · Topic</p>
        <h1>{data.topic.name}</h1>
      </header>
      {data.stories.length === 0 ? (
        <p className="empty-state">No published stories in this topic yet.</p>
      ) : (
        <ul className="story-grid">
          {data.stories.map((story) => (
            <li key={story.id}>
              <StoryCard story={story} display="brief" />
            </li>
          ))}
        </ul>
      )}
      <nav className="pagination" aria-label="Story pages">{data.next_cursor && <Link href={`/topic/${slug}?cursor=${encodeURIComponent(data.next_cursor)}`}>Older stories →</Link>}
        {(await searchParams).cursor && <Link href={`/topic/${slug}`}>Latest in this topic</Link>}</nav>
    </>
  );
}
