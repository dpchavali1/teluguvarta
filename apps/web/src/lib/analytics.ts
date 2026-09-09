"use client";

import { ANALYTICS_EVENTS, type AnalyticsEvent } from "@teluguvarta/domain";

import { apiUrl } from "@/lib/api";

/**
 * T18 §17 core analytics events. Posts to the same `POST /v1/events`
 * endpoint apps/mobile's `trackEvent` already uses (T17) — `app/analytics.py`
 * is the one place that forwards to PostHog (or just logs, if unset), so
 * neither app needs its own PostHog key/SDK. Events are also buffered
 * in-memory here so the E2E smoke test can assert against them without a
 * live API.
 */

const recorded: { event: AnalyticsEvent; properties: Record<string, unknown> }[] = [];

export function getRecordedEvents() {
  return recorded;
}

export function resetRecordedEvents() {
  recorded.length = 0;
}

const ANON_ID_KEY = "tg_analytics_anon_id_v1";

// A non-secret, per-browser id used only to group analytics events in
// PostHog (which requires a `distinct_id` or silently rejects the event —
// see apps/api/app/analytics.py::_forward_to_posthog). Deliberately separate
// from any auth/session token — this is not an identity mechanism. Reads
// localStorage synchronously (unlike apps/mobile's AsyncStorage-backed
// version) so it's safe to call inline in `track` with no extra async hop
// before the `fetch` — an added hop before the very first event delays
// app-launch tracking enough to break cold-start-timing tests on mobile.
function getOrCreateAnonId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const existing = window.localStorage.getItem(ANON_ID_KEY);
    if (existing) return existing;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(ANON_ID_KEY, id);
    return id;
  } catch {
    return undefined;
  }
}

export function track(event: AnalyticsEvent, properties: Record<string, unknown> = {}): void {
  recorded.push({ event, properties });
  if (typeof window === "undefined") return;

  const anonId = getOrCreateAnonId();
  fetch(`${apiUrl()}/v1/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event, properties: anonId ? { ...properties, anon_id: anonId } : properties }),
  }).catch(() => {
    // Best-effort — a dropped analytics event must never break the flow
    // that triggered it (opening a story, sharing, etc), same rule as
    // apps/mobile/src/lib/api.ts's trackEvent.
  });
}

export { ANALYTICS_EVENTS };
