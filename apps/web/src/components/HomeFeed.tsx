"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "./Icon";
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
  const rail = supporting.slice(0, 4);
  const rest = supporting.slice(4);
  return <section className="feed" aria-label="Latest stories">
    {error && <p className="callout" role="status">Your preferences couldn’t be applied. Showing the latest stories. <button className="button button--small" onClick={() => setRevision((value) => value + 1)}>Try again</button></p>}
    {!lead ? <div className="empty-state">No stories published yet. <Link href="/topics">Browse topics</Link> or check back soon.</div>
      : <>
        <div className="front-grid">
          <div className="front-grid__lead"><StoryCard story={lead} headingLevel="h2" display="lead" /></div>
          {rail.length > 0 && (
            <div className="front-grid__side">
              <h2 className="rail-title">Top stories</h2>
              <ol className="front-grid__rail">{rail.map((story) => <li key={story.id}><StoryCard story={story} headingLevel="h3" display="brief" /></li>)}</ol>
            </div>
          )}
        </div>
        {rest.length > 0 && <>
          <div className="section-head">
            <h2>More stories</h2>
            <Link className="section-head__more" href="/latest">View all <Icon name="arrowRight" size={16} /></Link>
          </div>
          <ul className="story-grid">{rest.map((story) => <li key={story.id}><StoryCard story={story} headingLevel="h3" display="brief" /></li>)}</ul>
        </>}
      </>}
    <p className="feed-more"><Link className="button" href="/latest">View all stories <Icon name="arrowRight" size={16} /></Link></p>
  </section>;
}
