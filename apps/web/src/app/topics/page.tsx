import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { PageHeader } from "@/components/StoryGrid";
import { getConfig } from "@/lib/api";

export const revalidate = 3600;
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Topics",
  description: "Browse every topic on TTE — The Telugu Edit.",
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
      <PageHeader eyebrow="Browse" title="Topics">Follow the subjects that matter to you — immigration, money, jobs, community and news from home.</PageHeader>
      {topics.length === 0 ? (
        <div className="empty-state">No topics yet.</div>
      ) : (
        <ul className="topic-grid">
          {topics.map((topic) => (
            <li key={topic.slug}>
              <Link href={`/topic/${topic.slug}`} className="topic-tile">
                <span className="topic-tile__initial" aria-hidden="true">{topic.name.charAt(0)}</span>
                <span className="topic-tile__name">{topic.name}</span>
                <Icon name="arrowRight" size={18} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
