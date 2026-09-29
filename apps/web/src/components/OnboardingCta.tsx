"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";
import { getOnboardingProfile } from "@/lib/onboarding";

// Design-review fix: the hero CTA always said "Personalize your feed →"
// even after a person had already onboarded, with no way to tell from the
// home page that a profile existed or to see/edit it without redoing the
// whole flow blind. Until hydration we can't know, so the first paint uses
// the not-yet-personalized copy (the common case for a first visit).
export function OnboardingCta() {
  const [onboarded, setOnboarded] = useState(false);

  useEffect(() => {
    setOnboarded(getOnboardingProfile().lifeStages.length > 0);
  }, []);

  return (
    <div className="personalize-card">
      <span className="personalize-card__icon" aria-hidden="true"><Icon name="sparkle" size={20} /></span>
      <div>
        <p className="personalize-card__title">{onboarded ? "Your feed is personalized" : "Make it yours"}</p>
        <p className="personalize-card__text">{onboarded ? "Update where you live and what you follow." : "Pick where you live and the topics you follow. No account needed."}</p>
      </div>
      <Link className={`button button--primary briefing-cta${onboarded ? " briefing-cta--edit" : ""}`} href="/onboarding">
        {onboarded ? "Edit preferences" : "Personalize"}
      </Link>
    </div>
  );
}
