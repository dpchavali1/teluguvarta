"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getOnboardingProfile, type LifeStage } from "@/lib/onboarding";

// Design-review fix: the hero CTA always said "Personalize your feed →"
// even after a person had already onboarded, with no way to tell from the
// home page that a profile existed or to see/edit it without redoing the
// whole flow blind.
export function OnboardingCta() {
  const [lifeStages, setLifeStages] = useState<LifeStage[] | null>(null);

  useEffect(() => {
    setLifeStages(getOnboardingProfile().lifeStages);
  }, []);

  if (lifeStages === null) {
    // Not yet hydrated — render nothing rather than flash the wrong state.
    return (
      <p>
        <Link className="briefing-cta" href="/onboarding">Personalize</Link>
      </p>
    );
  }

  if (lifeStages.length === 0) {
    return (
      <p>
        <Link className="briefing-cta" href="/onboarding">Personalize</Link>
      </p>
    );
  }

  return (
    <p>
      <Link className="briefing-cta briefing-cta--edit" href="/onboarding">
        Edit preferences
      </Link>
    </p>
  );
}
