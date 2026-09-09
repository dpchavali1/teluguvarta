"use client";

import { useEffect } from "react";

import { track } from "@/lib/analytics";
import type { AnalyticsEvent } from "@teluguvarta/domain";

/**
 * Fires an analytics event once on mount — the bridge for firing a §17
 * event from a server-rendered page (home, story, search) without making
 * the whole page a client component.
 */
export function TrackEvent({ event, properties }: { event: AnalyticsEvent; properties?: Record<string, unknown> }) {
  useEffect(() => {
    track(event, properties);
    // Deliberately fires once per mount regardless of `properties` identity
    // changing — these are page-load events, not per-render ones.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event]);
  return null;
}
