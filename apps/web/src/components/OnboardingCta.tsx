"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";
import { getOnboardingProfile } from "@/lib/onboarding";

// Keep personalization reachable without competing with the first story.
// The profile lives on this device; first paint uses the first-visit label.
export function OnboardingCta() {
  const [onboarded, setOnboarded] = useState(false);

  useEffect(() => {
    setOnboarded(getOnboardingProfile().lifeStages.length > 0);
  }, []);

  return (
    <div className="edition-preferences">
      <Link className="edition-preferences__link" href="/onboarding">
        {onboarded ? "Edit preferences" : "Personalize your feed"}
        <Icon name="arrowRight" size={16} />
      </Link>
      <span className="edition-preferences__hint">
        {onboarded ? "Your feed is personalized" : "No account needed"}
      </span>
    </div>
  );
}
