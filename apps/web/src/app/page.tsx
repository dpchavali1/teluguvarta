import Link from "next/link";
import type { CSSProperties } from "react";

import { StoryCard } from "@/components/StoryCard";
import { StudentBriefing } from "@/components/StudentBriefing";
import { TrackEvent } from "@/components/TrackEvent";
import { getHome } from "@/lib/api";

export const revalidate = 60;

export default async function HomePage() {
  const { top_stories: topStories, topics } = await getHome();

  return (
    <>
      <TrackEvent event="feed_view" properties={{ story_count: topStories.length }} />
      <section className="page-hero">
        <div className="page-hero__glow" aria-hidden="true" />
        <h1>Telugu Global</h1>
        <p>The latest stories for the global Telugu diaspora — original summaries, always linked to the source.</p>
        <p>
          <Link className="page-hero__cta" href="/onboarding">Personalize your feed →</Link>
        </p>
      </section>

      <StudentBriefing />

      {topics.length > 0 && (
        <nav aria-label="Topics" className="topic-rail">
          <ul className="topic-rail__list">
            {topics.map((topic) => (
              <li key={topic.slug}>
                <Link className="pill pill--topic" href={`/topic/${topic.slug}`}>
                  {topic.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {topStories.length === 0 ? (
        <p className="empty-state">No stories have been published yet — check back soon.</p>
      ) : (
        <ul className="story-list">
          {topStories.map((story, i) => (
            <li key={story.id} style={{ "--i": i } as CSSProperties}>
              <StoryCard story={story} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
