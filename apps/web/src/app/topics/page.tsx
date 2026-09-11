import type { Metadata } from "next";
import Link from "next/link";

import { getConfig } from "@/lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Topics",
  description: "Browse every topic on Telugu Global.",
};

// Design-review fix: topic browsing previously had no entry point outside
// the home feed's topic rail — a reader who navigated to Search or Saved
// first had no way back to it except returning Home. This reuses the same
// full-catalog list sitemap.ts already fetches via getConfig().topics
// (not getHome()'s personalized/ranked subset).
export default async function TopicsPage() {
  const config = await getConfig();
  const topics = config.topics.filter((topic) => topic.active);

  return (
    <>
      <h1>Topics</h1>
      {topics.length === 0 ? (
        <p className="empty-state">No topics yet.</p>
      ) : (
        <ul className="story-list">
          {topics.map((topic) => (
            <li key={topic.slug}>
              <Link href={`/topic/${topic.slug}`} className="pill pill--topic">
                {topic.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
