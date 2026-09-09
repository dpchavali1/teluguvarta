import AsyncStorage from "@react-native-async-storage/async-storage";
import type { components } from "@teluguvarta/contracts";

import { getClientToken, randomToken } from "./identity";

export type StoryVariantOut = components["schemas"]["StoryVariantOut"];
export type TopicOut = components["schemas"]["TopicOut"];
export type ShareMetaResponse = components["schemas"]["ShareMetaResponse"];
export type Language = "en" | "te";

// Mirrors apps/web/src/lib/api.ts's normalization — the generated types mark
// every `Field(default_factory=...)` collection as optional even though the
// API always serializes it. Kept as a separate copy rather than a shared
// package: apps/web's copy is SSR/fetch-cache-tuned (Next.js `next: {
// revalidate }`), this one is plain fetch for React Native — "where
// practical" share code (T15 scope note), and this isn't practical to share
// without an abstraction neither app actually needs yet.
type RawStoryOut = components["schemas"]["StoryOut"];
export type StoryOut = RawStoryOut & {
  topics: string[];
  countries: string[];
  variants: Partial<Record<Language, StoryVariantOut>>;
  sources: components["schemas"]["StorySourceOut"][];
};

function normalizeStory(raw: RawStoryOut): StoryOut {
  return {
    ...raw,
    topics: raw.topics ?? [],
    countries: raw.countries ?? [],
    variants: raw.variants ?? {},
    sources: raw.sources ?? [],
  };
}

export type HomeResponse = { top_stories: StoryOut[]; topics: TopicOut[] };
export type StoriesListResponse = { items: StoryOut[]; next_cursor: string | null | undefined };
export type TopicDetailResponse = { topic: TopicOut; stories: StoryOut[] };
export type SearchResponse = { query: string; items: StoryOut[] };
export type ConfigResponse = components["schemas"]["ConfigResponse"] & { topics: TopicOut[] };

export function apiUrl(): string {
  return process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
}

// Same canonical-URL construction as apps/web/src/lib/api.ts::storyUrl — both
// derive from the one public web origin, so a story shared from mobile opens
// the same T14 web page a browser share would (T15 acceptance criterion).
export function siteUrl(): string {
  return (process.env.EXPO_PUBLIC_WEB_URL ?? "http://localhost:3000").replace(/\/$/, "");
}

export function storyUrl(canonicalSlug: string): string {
  return `${siteUrl()}/story/${canonicalSlug}`;
}

export class ApiNotFoundError extends Error {}

async function apiGet<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, apiUrl());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value);
  }
  const response = await fetch(url.toString());
  if (response.status === 404) throw new ApiNotFoundError(path);
  if (!response.ok) throw new Error(`API ${path} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export type HomeParams = {
  residenceCountry?: string;
  homeRegion?: string;
  homeCity?: string;
  topics?: string[];
  segment?: string;
  studentBriefing?: boolean;
};

// S1: mirrors apps/web/src/lib/api.ts::getHomeFor — the same `/v1/home`
// personalization T16 already ships, now actually fed the onboarding-
// collected profile (previously collected in storage.ts but never sent,
// see docs/tickets/S1.md gap). `studentBriefing: true` composes the
// "Student Briefing" filtered view over this same endpoint/ranking —
// never a separate content pipeline.
export async function getHome(params: HomeParams = {}): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home", {
    residence_country: params.residenceCountry,
    home_state: params.homeRegion,
    home_city: params.homeCity,
    topics: params.topics && params.topics.length > 0 ? params.topics.join(",") : undefined,
    segment: params.segment,
    student_briefing: params.studentBriefing ? "true" : undefined,
  });
  return { top_stories: (raw.top_stories ?? []).map(normalizeStory), topics: raw.topics ?? [] };
}

export async function listStories(
  params: { topic?: string; country?: string; cursor?: string } = {}
): Promise<StoriesListResponse> {
  const raw = await apiGet<components["schemas"]["StoriesListResponse"]>("/v1/stories", params);
  return { items: raw.items.map(normalizeStory), next_cursor: raw.next_cursor };
}

export async function getStory(slug: string): Promise<StoryOut> {
  const raw = await apiGet<RawStoryOut>(`/v1/stories/${encodeURIComponent(slug)}`);
  return normalizeStory(raw);
}

export function getShareMeta(slug: string): Promise<ShareMetaResponse> {
  return apiGet<ShareMetaResponse>(`/v1/stories/${encodeURIComponent(slug)}/share-meta`);
}

export async function getTopic(slug: string): Promise<TopicDetailResponse> {
  const raw = await apiGet<components["schemas"]["TopicDetailResponse"]>(`/v1/topics/${encodeURIComponent(slug)}`);
  return { topic: raw.topic, stories: (raw.stories ?? []).map(normalizeStory) };
}

export async function search(q: string): Promise<SearchResponse> {
  const raw = await apiGet<components["schemas"]["SearchResponse"]>("/v1/search", { q });
  return { query: raw.query, items: (raw.items ?? []).map(normalizeStory) };
}

export async function getConfig(): Promise<ConfigResponse> {
  const raw = await apiGet<components["schemas"]["ConfigResponse"]>("/v1/config");
  return { ...raw, topics: raw.topics ?? [] };
}

// --- T17: push tokens, notification preferences, analytics events. Every
// call here is `Authorization: Bearer <client_token>` (ADR-006 anonymous
// identity, see ./identity.ts) — the same header T14/T15 never needed
// since preferences were on-device only until now. ---

async function authedRequest<T>(
  method: "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown
): Promise<T> {
  const token = await getClientToken();
  const response = await fetch(new URL(path, apiUrl()).toString(), {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`API ${path} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export type PreferencesUpdate = components["schemas"]["PreferencesUpdate"];
export type ProfileOut = components["schemas"]["ProfileOut"];

export function updatePreferences(body: PreferencesUpdate): Promise<ProfileOut> {
  return authedRequest<ProfileOut>("PATCH", "/v1/me/preferences", body);
}

export function registerPushToken(token: string, platform: "ios" | "android"): Promise<void> {
  return authedRequest("POST", "/v1/me/push-tokens", { token, platform }).then(() => undefined);
}

// T19 §16/§5.5 cross-system deletion: deletes the server-side `users` row
// (profile/push tokens/notification history cascade in Postgres — see
// apps/api/app/routers/me.py), not just the on-device clear PrivacyScreen
// already did. Best-effort: a network failure here must not block clearing
// on-device data, since that part always works with no server dependency.
export async function deleteAccount(): Promise<void> {
  await authedRequest("DELETE", "/v1/me/account");
}

// T18 expands this to the full §17 core-events list server-side
// (app/schemas.py::AnalyticsEventName) — derived from the generated
// contract rather than re-typed here so the two can't drift.
export type AnalyticsEventName = components["schemas"]["AnalyticsEventIn"]["event"];

const ANON_ID_KEY = "tg_analytics_anon_id_v1";
let cachedAnonId: string | null = null;

// A non-secret, per-device id used only to group analytics events in
// PostHog (which requires a `distinct_id` or silently rejects the event —
// see apps/api/app/analytics.py::_forward_to_posthog). Deliberately a
// separate key/value from identity.ts's `tg_client_token_v1` — that token
// is an auth credential and must never be sent to a third-party analytics
// sink.
//
// Resolved lazily and cached in-memory rather than awaited inline in
// `trackEvent`: awaiting an AsyncStorage round trip before the very first
// `fetch` delays app-launch events (app_open/feed_view) enough to break the
// E2E smoke test's cold-start assertions. Events fired before resolution
// completes just go out without `anon_id` — best-effort, same as a dropped
// event.
function primeAnonId(): void {
  if (cachedAnonId) return;
  AsyncStorage.getItem(ANON_ID_KEY)
    .then((existing) => {
      if (existing) {
        cachedAnonId = existing;
        return;
      }
      const id = randomToken();
      cachedAnonId = id;
      AsyncStorage.setItem(ANON_ID_KEY, id).catch(() => undefined);
    })
    .catch(() => undefined);
}

export async function trackEvent(event: AnalyticsEventName, properties: Record<string, unknown> = {}): Promise<void> {
  primeAnonId();
  try {
    const props = cachedAnonId ? { ...properties, anon_id: cachedAnonId } : properties;
    await fetch(new URL("/v1/events", apiUrl()).toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, properties: props }),
    });
  } catch {
    // Best-effort — a dropped analytics event must never break the flow
    // that triggered it (opening a story, sharing, etc).
  }
}
