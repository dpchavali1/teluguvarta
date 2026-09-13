import Link from "next/link";
import { StoryCard } from "@/components/StoryCard";
import { listStories } from "@/lib/api";
export const metadata = { title: "Latest stories" };
export const revalidate = 60;
export const dynamic = "force-dynamic";
export default async function LatestPage({ searchParams }: { searchParams: Promise<{ cursor?: string }> }) {
  const { cursor } = await searchParams;
  const { items, next_cursor } = await listStories({ cursor });
  return <>
    <h1>Latest stories</h1>
    {items.length === 0 && <p>No stories to show yet. <Link href="/topics">Browse topics</Link>.</p>}
    <ul className="story-list">{items.map((story) => <li key={story.id}><StoryCard story={story} /></li>)}</ul>
    <nav className="pagination" aria-label="Story pages">
      {next_cursor && <Link href={`/latest?cursor=${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
      {cursor && <Link href="/latest">Back to latest</Link>}
    </nav>
  </>;
}
