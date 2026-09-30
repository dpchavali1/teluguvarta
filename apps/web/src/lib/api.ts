import { countryCode } from "@teluguvarta/domain";
import type { components } from "@teluguvarta/contracts";

export type StoryVariantOut = components["schemas"]["StoryVariantOut"];
export type TopicOut = components["schemas"]["TopicOut"];
export type ShareMetaResponse = components["schemas"]["ShareMetaResponse"];
export type Language = "en" | "te";

// The generated types mark every `Field(default_factory=...)` collection as
// optional, since FastAPI's OpenAPI output can't express "always present,
// defaults to empty" — but the API always serializes these fields. Normalize
// once here so every page/component can treat them as always-present.
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
export type SearchResponse = { query: string; items: StoryOut[] };
export type ConfigResponse = components["schemas"]["ConfigResponse"] & { topics: TopicOut[] };

export function apiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export function siteUrl(): string {
  return (process.env.NEXT_PUBLIC_WEB_URL ?? "http://localhost:3000").replace(/\/$/, "");
}

export function storyUrl(canonicalSlug: string): string {
  return `${siteUrl()}/story/${canonicalSlug}`;
}

class ApiNotFoundError extends Error {}

async function apiGet<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, apiUrl());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value);
  }
  // ISR: every public page revalidates on a short interval rather than
  // caching forever or opting out of caching entirely (§10 SSR/ISR).
  const response = await fetch(url, { next: { revalidate: 60 } });
  if (response.status === 404) throw new ApiNotFoundError(path);
  if (!response.ok) throw new Error(`API ${path} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export { ApiNotFoundError };

// Static routes (`/`, `/topics`, `/latest`) prerender during `next build`; an unreachable
// API there must not fail the deploy, so they render `fallback` and ISR fills
// them on the first revalidation. At runtime the error still throws, so ISR
// keeps serving the last good page instead of caching an empty one.
export function duringBuild<T>(fallback: T): (err: unknown) => T {
  return (err) => {
    if (process.env.NEXT_PHASE === "phase-production-build") return fallback;
    throw err;
  };
}

export type HomeParams = { residenceCountry?: string; homeState?: string; homeCity?: string; topics?: string[]; segment?: string };
export async function getHome(params: HomeParams = {}): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home", {
    residence_country: countryCode(params.residenceCountry), home_state: params.homeState,
    home_city: params.homeCity, topics: params.topics?.join(","), segment: params.segment,
  });
  return { top_stories: (raw.top_stories ?? []).map(normalizeStory), topics: raw.topics ?? [] };
}

// T20 pre-build validation gate: a personalized preview for one of the
// landing page's 3 example feeds, using the same T16 `/v1/home` ranking the
// real product uses — no separate demo/mock data path.
export async function getHomeFor(segment: string, topics: string[]): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home", {
    segment,
    topics: topics.join(","),
  });
  return { top_stories: (raw.top_stories ?? []).map(normalizeStory), topics: raw.topics ?? [] };
}

// S1: browser-side fetch (unlike the other functions here, which run
// server-side during SSR/ISR) — the "Student Briefing" module depends on
// the client-only onboarding profile in ./onboarding.ts, so it can only be
// requested once the page has hydrated. Composes the same `/v1/home`
// endpoint/ranking via `student_briefing=true` rather than a separate
// pipeline (docs/tickets/S1.md).
export async function getStudentBriefing(params: {
  segment: string;
  residenceCountry?: string;
  homeState?: string;
  homeCity?: string;
}): Promise<HomeResponse> {
  const url = new URL("/v1/home", apiUrl());
  url.searchParams.set("student_briefing", "true");
  url.searchParams.set("segment", params.segment);
  if (params.residenceCountry) url.searchParams.set("residence_country", countryCode(params.residenceCountry)!);
  if (params.homeState) url.searchParams.set("home_state", params.homeState);
  if (params.homeCity) url.searchParams.set("home_city", params.homeCity);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`API /v1/home failed: ${response.status}`);
  const raw = (await response.json()) as components["schemas"]["HomeResponse"];
  return { top_stories: (raw.top_stories ?? []).map(normalizeStory), topics: raw.topics ?? [] };
}

export async function listStories(
  params: { topic?: string; country?: string; cursor?: string; ids?: string; limit?: string } = {}
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

export async function search(q: string): Promise<SearchResponse> {
  const raw = await apiGet<components["schemas"]["SearchResponse"]>("/v1/search", { q });
  return { query: raw.query, items: (raw.items ?? []).map(normalizeStory) };
}

export async function getConfig(): Promise<ConfigResponse> {
  const raw = await apiGet<components["schemas"]["ConfigResponse"]>("/v1/config");
  return { ...raw, topics: raw.topics ?? [] };
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

export async function reportIssue(storyId: string, description = ""): Promise<void> {
  const response = await fetch(new URL("/v1/events", apiUrl()).toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event: "report_issue", properties: { story_id: storyId, description } }),
  });
  if (!response.ok) throw new Error("Couldn't send your report. Please try again.");
}
