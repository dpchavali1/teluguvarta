"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { track } from "@/lib/analytics";
import { LIFE_STAGES, getOnboardingProfile, setOnboardingProfile, type LifeStage } from "@/lib/onboarding";

// S1: web's onboarding — apps/mobile already has this flow (OnboardingScreen),
// web didn't (docs/tickets/S1.md gap). Deliberately short: life-stage plus a
// few optional location fields, no student sub-questions beyond what
// personalizes the feed (no university name / immigration-document fields —
// NON_NEGOTIABLES: don't collect what isn't needed). Fully skippable per S1's
// acceptance criteria.
export default function OnboardingPage() {
  const router = useRouter();
  const [lifeStages, setLifeStages] = useState<LifeStage[]>([]);
  const [residenceCountry, setResidenceCountry] = useState("");
  const [homeState, setHomeState] = useState("");
  const [homeCity, setHomeCity] = useState("");

  // Loaded client-side only (not as a useState initializer) to avoid an
  // SSR/hydration mismatch — the server always renders the empty/skip
  // defaults, then this fills in any profile already saved on the device.
  useEffect(() => {
    const existing = getOnboardingProfile();
    setLifeStages(existing.lifeStages);
    setResidenceCountry(existing.residenceCountry ?? "");
    setHomeState(existing.homeState ?? "");
    setHomeCity(existing.homeCity ?? "");
  }, []);

  function toggleLifeStage(stage: LifeStage) {
    setLifeStages((current) =>
      current.includes(stage) ? current.filter((s) => s !== stage) : [...current, stage],
    );
  }

  function save(finalLifeStages: LifeStage[]) {
    setOnboardingProfile({
      ...getOnboardingProfile(),
      lifeStages: finalLifeStages,
      residenceCountry: residenceCountry.trim() || undefined,
      homeState: homeState.trim() || undefined,
      homeCity: homeCity.trim() || undefined,
    });
    // A person can select more than one life stage (ADR-005 addendum);
    // report the full set rather than silently dropping every stage but
    // one — same convention as apps/mobile/src/screens/OnboardingScreen.tsx.
    track("onboarding_complete", {
      life_stages: finalLifeStages.length > 0 ? finalLifeStages.join(",") : "skipped",
      life_stage_count: finalLifeStages.length,
    });
    router.push("/");
  }

  return (
    <div className="onboarding">
      <h1>Tell us about yourself</h1>
      <p>
        This personalizes your feed and, for students, adds a Student Briefing section. Every
        question here is optional — Telugu Global works fully without answering any of them.
      </p>

      <fieldset className="onboarding__fieldset">
        <legend>Which best describes you?</legend>
        <p className="onboarding__hint">Select every option that applies — you&apos;re not just one thing.</p>
        {LIFE_STAGES.map((stage) => (
          <label key={stage.value} className="onboarding__radio">
            <input
              type="checkbox"
              name="lifeStage"
              value={stage.value}
              checked={lifeStages.includes(stage.value)}
              onChange={() => toggleLifeStage(stage.value)}
            />
            {stage.label}
          </label>
        ))}
      </fieldset>

      <div className="onboarding__field">
        <label htmlFor="residenceCountry">Where do you live now? (optional)</label>
        <input
          id="residenceCountry"
          type="text"
          value={residenceCountry}
          onChange={(event) => setResidenceCountry(event.target.value)}
          placeholder="e.g. United States"
        />
      </div>

      <div className="onboarding__field">
        <label htmlFor="homeState">Home state in India? (optional)</label>
        <input
          id="homeState"
          type="text"
          value={homeState}
          onChange={(event) => setHomeState(event.target.value)}
          placeholder="e.g. Telangana"
        />
      </div>

      <div className="onboarding__field">
        <label htmlFor="homeCity">Home city/district? (optional)</label>
        <input
          id="homeCity"
          type="text"
          value={homeCity}
          onChange={(event) => setHomeCity(event.target.value)}
          placeholder="e.g. Hyderabad"
        />
      </div>

      <div className="onboarding__actions">
        <button type="button" onClick={() => save(lifeStages)}>
          Save and continue
        </button>
        <button type="button" className="onboarding__skip" onClick={() => save([])}>
          Skip for now
        </button>
      </div>
    </div>
  );
}
