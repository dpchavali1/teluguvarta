import Link from "next/link";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { listStories } from "@/lib/api";

export const metadata = { title: "Latest stories" };
export const revalidate = 60;
export const dynamic = "force-dynamic";

export default async function LatestPage({ searchParams }: { searchParams: Promise<{ cursor?: string }> }) {
  const { cursor } = await searchParams;
  const { items, next_cursor } = await listStories({ cursor });
  return <>
    <PageHeader eyebrow="Feed" title="Latest stories">Everything we’ve published, newest first.</PageHeader>
    <StoryGrid stories={items} empty={<>No stories to show yet. <Link href="/topics">Browse topics</Link>.</>} />
    <nav className="pagination" aria-label="Story pages">
      {cursor && <Link className="button" href="/latest">Back to latest</Link>}
      {next_cursor && <Link className="button" href={`/latest?cursor=${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
    </nav>
  </>;
}
