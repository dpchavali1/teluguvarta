"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StoryCard } from "./StoryCard";
import { getHome, type StoryOut } from "@/lib/api";
import { getOnboardingProfile, primaryLifeStageSegment } from "@/lib/onboarding";
import { track } from "@/lib/analytics";

export function HomeFeed({ initialStories }: { initialStories: StoryOut[] }) {
  const [stories, setStories] = useState(initialStories);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const profile = getOnboardingProfile();
    const segment = primaryLifeStageSegment(profile.lifeStages) ?? undefined;
    const personalized = Boolean(segment || profile.residenceCountry || profile.homeState || profile.homeCity || profile.topics?.length);
    setError(false);
    if (!personalized) { track("feed_view", { story_count: initialStories.length }); return; }
    getHome({ ...profile, segment }).then((home) => {
      if (cancelled) return;
      setStories(home.top_stories);
      track("feed_view", { story_count: home.top_stories.length, personalized: true });
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [initialStories, revision]);
  const [lead, ...supporting] = stories;
  const rail = supporting.slice(0, 5);
  const rest = supporting.slice(5);
  return <section aria-label="Latest stories">
    {error && <p role="status">Your preferences couldn’t be applied. Showing the latest stories. <button onClick={() => setRevision((value) => value + 1)}>Try again</button></p>}
    {!lead ? <p className="empty-state">No stories published yet. <Link href="/topics">Browse topics</Link> or check back soon.</p>
      : <>
        <div className="front-grid">
          <div className="front-grid__lead"><StoryCard story={lead} headingLevel="h2" display="lead" /></div>
          {rail.length > 0 && (
            <ul className="front-grid__rail">{rail.map((story) => <li key={story.id}><StoryCard story={story} display="brief" /></li>)}</ul>
          )}
        </div>
        {rest.length > 0 && <>
          <div className="section-rule"><span>More stories</span></div>
          <ul className="story-grid">{rest.map((story) => <li key={story.id}><StoryCard story={story} display="brief" /></li>)}</ul>
        </>}
      </>}
    <p><Link href="/latest">Browse all stories →</Link></p>
  </section>;
}
