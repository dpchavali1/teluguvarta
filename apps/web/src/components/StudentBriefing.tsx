"use client";

import { useEffect, useState } from "react";

import { StoryCard } from "@/components/StoryCard";
import { getStudentBriefing, type StoryOut } from "@/lib/api";
import { getOnboardingProfile, isStudentLifeStage } from "@/lib/onboarding";

// S1: renders on the home page only when the visitor explicitly selected
// International Student or Graduate/OPT during onboarding (never inferred).
// A client component so it can read the browser-only onboarding profile
// without turning the whole (SSR/ISR) home page into one — same bridge
// pattern as ./TrackEvent.tsx.
export function StudentBriefing() {
  const [stories, setStories] = useState<StoryOut[] | null>(null);

  useEffect(() => {
    const profile = getOnboardingProfile();
    if (!isStudentLifeStage(profile.lifeStage)) return;
    let cancelled = false;
    getStudentBriefing({
      segment: profile.lifeStage as string,
      residenceCountry: profile.residenceCountry,
      homeState: profile.homeState,
      homeCity: profile.homeCity,
    })
      .then((home) => {
        if (!cancelled) setStories(home.top_stories);
      })
      .catch(() => {
        if (!cancelled) setStories([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!stories || stories.length === 0) return null;

  return (
    <section className="student-briefing" aria-labelledby="student-briefing-heading">
      <h2 id="student-briefing-heading">Student Briefing</h2>
      <ul className="story-list">
        {stories.map((story) => (
          <li key={story.id}>
            <StoryCard story={story} />
          </li>
        ))}
      </ul>
    </section>
  );
}
