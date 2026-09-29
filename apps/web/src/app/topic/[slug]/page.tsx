import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
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
  const { cursor } = await searchParams;
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
      <StoryGrid stories={data.stories} empty={<>No published stories in this topic yet. <Link href="/topics">Browse other topics</Link>.</>} />
      <nav className="pagination" aria-label="Story pages">
        {cursor && <Link className="button" href={`/topic/${slug}`}>Latest in this topic</Link>}
        {data.next_cursor && <Link className="button" href={`/topic/${slug}?cursor=${encodeURIComponent(data.next_cursor)}`}>Older stories →</Link>}
      </nav>
    </>
  );
}
