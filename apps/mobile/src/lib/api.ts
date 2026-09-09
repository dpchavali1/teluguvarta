import type { components } from "@teluguvarta/contracts";

import { getClientToken } from "./identity";

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

export async function getHome(): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home");
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
  method: "POST" | "PATCH",
  path: string,
  body: unknown
): Promise<T> {
  const token = await getClientToken();
  const response = await fetch(new URL(path, apiUrl()).toString(), {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
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

export type AnalyticsEventName = "story_share" | "notification_received" | "notification_open";

export async function trackEvent(event: AnalyticsEventName, properties: Record<string, unknown> = {}): Promise<void> {
  try {
    await fetch(new URL("/v1/events", apiUrl()).toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, properties }),
    });
  } catch {
    // Best-effort — a dropped analytics event must never break the flow
    // that triggered it (opening a story, sharing, etc).
  }
}
