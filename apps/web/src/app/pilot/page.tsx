import type { Metadata } from "next";

import { StoryCard } from "@/components/StoryCard";
import { PilotSignupForm } from "@/components/PilotSignupForm";
import { getHomeFor } from "@/lib/api";

export const metadata: Metadata = { title: "Join the pilot" };
export const revalidate = 60;

// T20 pre-build validation gate (docs/BUILD_ORDER.md): the "landing page +
// 3 example personalized feeds" this page exists to run the gate with.
// Each example uses the real T16 `/v1/home` ranking for a segment/topic mix
// representative of the target USA Telugu NRI audience — not mock data.
const EXAMPLE_FEEDS: { key: string; segment: string; title: string; blurb: string; topics: string[] }[] = [
  {
    key: "professional",
    segment: "professional",
    title: "H1B / working professional",
    blurb: "Visa, jobs, and money news that affects your work status and finances in the US.",
    topics: ["immigration", "jobs", "money"],
  },
  {
    key: "international_student",
    segment: "international_student",
    title: "International student",
    blurb: "OPT/CPT, campus community, and education news alongside home-state updates.",
    topics: ["education", "immigration", "community"],
  },
  {
    key: "family_parent",
    segment: "family_parent",
    title: "Parent / family back home",
    blurb: "News from Andhra Pradesh and Telangana, plus property and family-relevant stories.",
    topics: ["andhra-pradesh", "telangana", "parents", "property"],
  },
];

export default async function PilotLandingPage() {
  const feeds = await Promise.all(
    EXAMPLE_FEEDS.map(async (feed) => ({
      ...feed,
      stories: (await getHomeFor(feed.segment, feed.topics)).top_stories.slice(0, 3),
    }))
  );

  return (
    <div className="pilot-landing">
      <section className="pilot-landing__hero">
        <h1>A Telugu news feed built for life in the US</h1>
        <p>
          Telugu Global is a bilingual (English/Telugu) briefing for the US Telugu NRI
          community — immigration, jobs, money, and news from Andhra Pradesh and
          Telangana, personalized to your situation. We&rsquo;re running a small pilot
          before opening this up publicly. Pick the example below closest to you, see
          what your feed would look like, and join the pilot list.
        </p>
      </section>

      {feeds.map((feed) => (
        <section key={feed.key} className="pilot-landing__feed" aria-labelledby={`feed-${feed.key}`}>
          <h2 id={`feed-${feed.key}`}>{feed.title}</h2>
          <p>{feed.blurb}</p>
          {feed.stories.length === 0 ? (
            <p className="empty-state">No published stories in this preview yet.</p>
          ) : (
            <ul className="story-list">
              {feed.stories.map((story) => (
                <li key={story.id}>
                  <StoryCard story={story} />
                </li>
              ))}
            </ul>
          )}
          <PilotSignupForm segment={feed.segment} exampleFeed={feed.key} />
        </section>
      ))}
    </div>
  );
}
