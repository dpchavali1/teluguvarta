"use client";

import { ReadingControls } from "@/components/ReadingControls";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { applyPreset, countryCode, PERSONA_PRESETS, removePreset, type PersonaPresetId, type PersonaState } from "@teluguvarta/domain";
import { getConfig, type TopicOut } from "@/lib/api";
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
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [topicsError, setTopicsError] = useState(false);
  const [lifeStages, setLifeStages] = useState<LifeStage[]>([]);
  const [residenceCountry, setResidenceCountry] = useState("");
  const [homeState, setHomeState] = useState("");
  const [homeCity, setHomeCity] = useState("");
  const [applied, setApplied] = useState<PersonaState["applied"]>({});

  // Loaded client-side only (not as a useState initializer) to avoid an
  // SSR/hydration mismatch — the server always renders the empty/skip
  // defaults, then this fills in any profile already saved on the device.
  useEffect(() => {
    const existing = getOnboardingProfile();
    setLifeStages(existing.lifeStages);
    setSelectedTopics(existing.topics ?? []);
    getConfig().then((config) => setTopics(config.topics)).catch(() => setTopicsError(true));
    setResidenceCountry(existing.residenceCountry ?? "");
    setHomeState(existing.homeState ?? "");
    setHomeCity(existing.homeCity ?? "");
    setApplied(existing.personaApplied ?? {});
  }, []);

  // The domain presets use mobile's SCREAMING_SNAKE life stages; web stores
  // the API's lowercase values. Web has no push alerts, so alert fields stay
  // empty and unused.
  function togglePreset(id: PersonaPresetId) {
    const before: PersonaState = {
      interests: selectedTopics,
      lifeStages: lifeStages.map((s) => s.toUpperCase()),
      alertTopics: {},
      quietHoursEnabled: false,
      quietHoursStart: "22:00",
      quietHoursEnd: "07:00",
      applied,
    };
    const after = applied[id] ? removePreset(before, id) : applyPreset(before, id);
    setSelectedTopics(after.interests);
    setLifeStages(after.lifeStages.map((s) => s.toLowerCase() as LifeStage));
    setApplied(after.applied);
  }

  function toggleLifeStage(stage: LifeStage) {
    setLifeStages((current) =>
      current.includes(stage) ? current.filter((s) => s !== stage) : [...current, stage],
    );
  }

  function save(finalLifeStages: LifeStage[]) {
    setOnboardingProfile({
      ...getOnboardingProfile(),
      lifeStages: finalLifeStages,
      residenceCountry: countryCode(residenceCountry),
      topics: selectedTopics,
      homeState: homeState.trim() || undefined,
      homeCity: homeCity.trim() || undefined,
      personaApplied: applied,
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
        question here is optional — TTE works fully without answering any of them.
      </p>

      <ReadingControls />

      <fieldset className="onboarding__fieldset">
        <legend>Quick setup (optional)</legend>
        <p className="onboarding__hint">Pick any that fit. Each only selects its own topics, and unchecking it removes just those. You can change everything below afterwards.</p>
        {PERSONA_PRESETS.map((preset) => (
          <label key={preset.id} className="onboarding__radio">
            <input type="checkbox" checked={Boolean(applied[preset.id])} onChange={() => togglePreset(preset.id)} />
            {preset.label}
          </label>
        ))}
      </fieldset>

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

      <fieldset className="onboarding__fieldset"><legend>Topics you follow (optional)</legend>
        {topicsError && <p>Topics couldn’t load. You can continue and choose them later.</p>}
        {topics.map((topic) => <label key={topic.slug} className="onboarding__radio"><input type="checkbox" checked={selectedTopics.includes(topic.slug)} onChange={() => setSelectedTopics((current) => current.includes(topic.slug) ? current.filter((slug) => slug !== topic.slug) : [...current, topic.slug])} />{topic.name}</label>)}
      </fieldset>
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
