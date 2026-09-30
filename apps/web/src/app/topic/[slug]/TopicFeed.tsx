import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { ApiNotFoundError, getTopic } from "@/lib/api";

// Shared by /topic/[slug] and /topic/[slug]/older/[cursor]. The cursor lives
// in the path, not ?cursor=, because reading searchParams opts a page out of ISR.
export async function topicMetadata(slug: string): Promise<Metadata> {
  try {
    const { topic } = await getTopic(slug);
    return { title: topic.name, description: `Latest ${topic.name} stories on TTE.` };
  } catch (err) {
    if (err instanceof ApiNotFoundError) return {};
    throw err;
  }
}

export async function TopicFeed({ slug, cursor }: { slug: string; cursor?: string }) {
  let data;
  try {
    data = await getTopic(slug, cursor);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }

  return (
    <>
      <PageHeader eyebrow="Topic" title={data.topic.name}>The latest {data.topic.name} stories, summarized with a link to every source.</PageHeader>
      <StoryGrid stories={data.stories} empty={<>No published stories in this topic yet. See the <Link href="/latest">latest stories</Link> or <Link href="/topics">browse other topics</Link>.</>} />
      <nav className="pagination" aria-label="Story pages">
        {cursor && <Link className="button" href={`/topic/${slug}`}>Latest in this topic</Link>}
        {data.next_cursor && <Link className="button" href={`/topic/${slug}/older/${encodeURIComponent(data.next_cursor)}`}>Older stories →</Link>}
      </nav>
    </>
  );
}
