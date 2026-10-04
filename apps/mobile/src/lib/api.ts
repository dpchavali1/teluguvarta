import { countryCode } from "@teluguvarta/domain";
import { Platform } from "react-native";
import type { components } from "@teluguvarta/contracts";

import { getClientToken } from "./identity";
import { trackMobileEvent } from "./mobileAnalytics";

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
export type TopicDetailResponse = { topic: TopicOut; stories: StoryOut[]; next_cursor?: string | null };
export type SearchResponse = Omit<components["schemas"]["SearchResponse"], "items"> & { items: StoryOut[] };
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

// Design-review fix: previously every failure (offline, DNS, timeout, or a
// real 5xx) surfaced as the same generic error text with no way for a
// screen to tell "you're offline" from "something's wrong on our end".
// React Native's `fetch` rejects with a TypeError for a network-layer
// failure (no connection, DNS, timeout) — a real HTTP response, even an
// error one, resolves rather than rejects — so that's the signal to key on.
export class ApiNetworkError extends Error {}

async function apiGet<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, apiUrl());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value);
  }
  let response: Response;
  try {
    response = await fetch(url.toString());
  } catch (err) {
    throw new ApiNetworkError(err instanceof Error ? err.message : "Network request failed");
  }
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
  // ADR-043: followed catalog place ids (explicit, at most 10).
  places?: string[];
};

// S1: mirrors apps/web/src/lib/api.ts::getHomeFor — the same `/v1/home`
// personalization T16 already ships, now actually fed the onboarding-
// collected profile (previously collected in storage.ts but never sent,
// see docs/tickets/S1.md gap). `studentBriefing: true` composes the
// "Student Briefing" filtered view over this same endpoint/ranking —
// never a separate content pipeline.
export async function getHome(params: HomeParams = {}): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home", {
    residence_country: countryCode(params.residenceCountry),
    home_state: params.homeRegion,
    home_city: params.homeCity,
    topics: params.topics && params.topics.length > 0 ? params.topics.join(",") : undefined,
    places: params.places && params.places.length > 0 ? params.places.join(",") : undefined,
    segment: params.segment,
    student_briefing: params.studentBriefing ? "true" : undefined,
  });
  return { top_stories: (raw.top_stories ?? []).map(normalizeStory), topics: raw.topics ?? [] };
}

export async function listStories(
  params: { topic?: string; country?: string; place?: string; cursor?: string; ids?: string; limit?: string } = {}
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

export async function getTopic(slug: string, cursor?: string): Promise<TopicDetailResponse> {
  const raw = await apiGet<components["schemas"]["TopicDetailResponse"]>(`/v1/topics/${encodeURIComponent(slug)}`, { cursor });
  return { topic: raw.topic, stories: (raw.stories ?? []).map(normalizeStory), next_cursor: raw.next_cursor };
}

export const SEARCH_RESULT_LIMIT = 20;

export async function search(q: string, cursor?: string): Promise<SearchResponse> {
  const raw = await apiGet<components["schemas"]["SearchResponse"]>("/v1/search", { q, cursor, limit: String(SEARCH_RESULT_LIMIT) });
  return { ...raw, items: (raw.items ?? []).map(normalizeStory) };
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
// already did. ADR-033 A: the combined deletion UI confirms this request
// before clearing local data/identity, retaining both on network failure.
export async function deleteAccount(): Promise<void> {
  await authedRequest("DELETE", "/v1/me/account");
}

// T18 expands this to the full §17 core-events list server-side
// (app/schemas.py::AnalyticsEventName) — derived from the generated
// contract rather than re-typed here so the two can't drift.
export type AnalyticsEventName = components["schemas"]["AnalyticsEventIn"]["event"];

export async function trackEvent(event: AnalyticsEventName, _properties: Record<string, unknown> = {}): Promise<void> {
  // ADR-039: mobile analytics is Firebase-only and separately opt-in.
  // Caller properties can contain search terms, story IDs, or notification
  // payloads, so they never leave this device.
  await trackMobileEvent(event);
}

// Exact bounded lookup preserves existing ID-only bookmarks across app restarts.
export async function getSavedStories(ids: string[]): Promise<StoryOut[]> {
  const unique = [...new Set(ids)];
  const found = new Map<string, StoryOut>();
  for (let offset = 0; offset < unique.length; offset += 100) {
    const page = await listStories({ ids: unique.slice(offset, offset + 100).join(","), limit: "100" });
    for (const story of page.items) found.set(story.id, story);
  }
  return unique.map((id) => found.get(id)).filter((story): story is StoryOut => Boolean(story));
}

// ADR-029: a private report only editors see; the text is optional.
export const REPORT_CATEGORIES = [
  { value: "FACTUAL_ERROR", label: "Something is wrong or out of date" },
  { value: "TRANSLATION", label: "Telugu translation problem" },
  { value: "BROKEN_LINK", label: "Source link doesn't work" },
  { value: "WRONG_IMAGE", label: "Wrong image" },
  { value: "OFFENSIVE", label: "Offensive or harmful" },
  { value: "OTHER", label: "Something else" },
] as const;
export type ReportCategory = (typeof REPORT_CATEGORIES)[number]["value"];

export async function reportIssue(
  storyId: string,
  report: { category: ReportCategory; description?: string; language?: Language },
): Promise<void> {
  const response = await fetch(new URL(`/v1/stories/${encodeURIComponent(storyId)}/reports`, apiUrl()).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...report,
      description: report.description || null,
      platform: Platform.OS === "ios" ? "ios" : "android",
    }),
  });
  if (response.status === 429) throw new Error("You've sent several reports in a short time. Please try again later.");
  if (!response.ok) throw new Error("Couldn't send your report. Please try again.");
}
