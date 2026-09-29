import Link from "next/link";

import { HomeFeed } from "@/components/HomeFeed";
import { Icon } from "@/components/Icon";
import { OnboardingCta } from "@/components/OnboardingCta";
import { StudentBriefing } from "@/components/StudentBriefing";
import { EditionDate } from "@/components/EditionDate";
import { getHome } from "@/lib/api";

export const revalidate = 60;
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const { top_stories: topStories, topics } = await getHome();

  return (
    <div className="home">
      <section className="edition" aria-labelledby="briefing-title">
        <div className="edition__text">
          <p className="eyebrow"><EditionDate /></p>
          <h1 id="briefing-title">What matters today</h1>
          <p className="edition__lede">Clear, sourced updates for Telugu life here and back home.</p>
        </div>
        <OnboardingCta />
      </section>

      <HomeFeed initialStories={topStories} />
      <StudentBriefing />

      {topics.length > 0 && (
        <section className="explore" aria-labelledby="explore-title">
          <div className="section-head">
            <h2 id="explore-title">Explore topics</h2>
            <Link className="section-head__more" href="/topics">All topics <Icon name="arrowRight" size={16} /></Link>
          </div>
          <ul className="chip-list">
            {topics.map((topic) => (
              <li key={topic.slug}>
                <Link className="chip" href={`/topic/${topic.slug}`}>{topic.name}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
