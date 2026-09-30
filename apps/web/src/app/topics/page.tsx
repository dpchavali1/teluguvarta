import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { PageHeader } from "@/components/StoryGrid";
import { duringBuild, getConfig, type TopicOut } from "@/lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Topics",
  description: "Browse every topic on TTE — The Telugu Edit.",
};

// Design-review fix: topic browsing previously had no entry point outside
// the home feed's topic rail — a reader who navigated to Search or Saved
// first had no way back to it except returning Home. This is the full
// catalog from getConfig().topics (not getHome()'s personalized subset).
// Review #11: topics with stories come first, with counts; the rest stay
// listed (the full taxonomy is still discoverable) but say they're empty.
export default async function TopicsPage() {
  const topics = (await getConfig().then((config) => config.topics).catch(duringBuild([])))
    .filter((topic) => topic.active);
  const populated = topics.filter((topic) => topic.story_count > 0);
  const empty = topics.filter((topic) => topic.story_count === 0);

  return (
    <>
      <PageHeader eyebrow="Browse" title="Topics">Follow the subjects that matter to you — immigration, money, jobs, community and news from home.</PageHeader>
      {topics.length === 0 ? (
        <div className="empty-state">No topics yet.</div>
      ) : (
        <>
          {populated.length > 0 ? (
            <TopicGrid topics={populated} />
          ) : (
            <div className="empty-state">No topic has stories yet. See the <Link href="/latest">latest stories</Link>.</div>
          )}
          {empty.length > 0 && (
            <section className="topics-empty" aria-labelledby="topics-empty-title">
              <div className="section-head">
                <h2 id="topics-empty-title">No stories yet</h2>
              </div>
              <TopicGrid topics={empty} />
            </section>
          )}
        </>
      )}
    </>
  );
}

function TopicGrid({ topics }: { topics: TopicOut[] }) {
  return (
    <ul className="topic-grid">
      {topics.map((topic) => (
        <li key={topic.slug}>
          <Link href={`/topic/${topic.slug}`} className="topic-tile">
            <span className="topic-tile__initial" aria-hidden="true">{topic.name.charAt(0)}</span>
            <span className="topic-tile__name">
              {topic.name}
              {topic.story_count > 0 && (
                <span className="topic-tile__count">{topic.story_count === 1 ? "1 story" : `${topic.story_count} stories`}</span>
              )}
            </span>
            <Icon name="arrowRight" size={18} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
