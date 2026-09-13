import Link from "next/link";


import { OnboardingCta } from "@/components/OnboardingCta";
import { HomeFeed } from "@/components/HomeFeed";
import { StudentBriefing } from "@/components/StudentBriefing";

import { getHome } from "@/lib/api";

export const revalidate = 60;
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const { top_stories: topStories, topics } = await getHome();

  return (
    <>
      <section className="briefing-header" aria-labelledby="briefing-title">
        <div>
          <p className="briefing-kicker">TTE · THE TELUGU EDIT</p>
          <h1 id="briefing-title">Today’s briefing</h1>
          <p>Clear updates for life here and back home.</p>
        </div>
        <OnboardingCta />
      </section>

      {topics.length > 0 && (
        <nav aria-label="Topics" className="topic-rail">
          <ul className="topic-rail__list">
            {topics.slice(0, 5).map((topic) => (
              <li key={topic.slug}>
                <Link className="pill pill--topic" href={`/topic/${topic.slug}`}>
                  {topic.name}
                </Link>
              </li>
            ))}
            <li><Link className="pill pill--topic" href="/topics">All topics →</Link></li>
          </ul>
        </nav>
      )}

      <HomeFeed initialStories={topStories} />
      <StudentBriefing />
    </>
  );
}
