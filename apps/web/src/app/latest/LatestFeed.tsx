import Link from "next/link";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { duringBuild, listStories } from "@/lib/api";

// Shared by /latest and /latest/older/[cursor]. The cursor lives in the path,
// not ?cursor=, because reading searchParams opts a page out of ISR.
export async function LatestFeed({ cursor }: { cursor?: string }) {
  const { items, next_cursor } = await listStories({ cursor }).catch(duringBuild({ items: [], next_cursor: null }));
  return <>
    <PageHeader eyebrow="Feed" title="Latest stories">Everything we’ve published, newest first.</PageHeader>
    <StoryGrid stories={items} empty={<>No stories to show yet. <Link href="/topics">Browse topics</Link>.</>} />
    <nav className="pagination" aria-label="Story pages">
      {cursor && <Link className="button" href="/latest">Back to latest</Link>}
      {next_cursor && <Link className="button" href={`/latest/older/${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
    </nav>
  </>;
}
