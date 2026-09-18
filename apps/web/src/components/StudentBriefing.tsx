"use client";

import { useEffect, useState } from "react";

import { StoryCard } from "@/components/StoryCard";
import { getStudentBriefing, type StoryOut } from "@/lib/api";
import { getOnboardingProfile, isStudentLifeStage, primaryLifeStageSegment } from "@/lib/onboarding";

// S1: renders on the home page only when the visitor explicitly selected
// International Student or Graduate/OPT during onboarding (never inferred).
// A client component so it can read the browser-only onboarding profile
// without turning the whole (SSR/ISR) home page into one — same bridge
// pattern as ./TrackEvent.tsx.
export function StudentBriefing() {
  const [stories, setStories] = useState<StoryOut[] | null>(null);

  useEffect(() => {
    const profile = getOnboardingProfile();
    if (!isStudentLifeStage(profile.lifeStages)) return;
    // Student-briefing eligibility checks every selected life stage, but the
    // API's `segment` param is single-valued — use the primary (first
    // selected) stage, same rule as the personalized home feed's segment
    // would use (see apps/mobile/src/lib/storage.ts::primaryLifeStageSegment).
    const segment = primaryLifeStageSegment(profile.lifeStages);
    if (!segment) return;
    let cancelled = false;
    getStudentBriefing({
      segment,
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
      <ul className="story-grid">
        {stories.map((story) => (
          <li key={story.id}>
            <StoryCard story={story} display="brief" />
          </li>
        ))}
      </ul>
    </section>
  );
}
