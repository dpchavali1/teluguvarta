import Link from "next/link";

import { StoryCard } from "@/components/StoryCard";
import { TrackEvent } from "@/components/TrackEvent";
import { getHome } from "@/lib/api";

export const revalidate = 60;

export default async function HomePage() {
  const { top_stories: topStories, topics } = await getHome();

  return (
    <>
      <TrackEvent event="feed_view" properties={{ story_count: topStories.length }} />
      <section className="page-hero">
        <h1>Telugu Global</h1>
        <p>The latest stories for the global Telugu diaspora — original summaries, always linked to the source.</p>
      </section>

      {topics.length > 0 && (
        <nav aria-label="Topics">
          <ul style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", listStyle: "none", padding: 0, marginBottom: "2rem" }}>
            {topics.map((topic) => (
              <li key={topic.slug}>
                <Link className="pill" href={`/topic/${topic.slug}`}>
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
          {topStories.map((story) => (
            <li key={story.id}>
              <StoryCard story={story} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
