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
export type TopicDetailResponse = { topic: TopicOut; stories: StoryOut[] };
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

export async function getHome(): Promise<HomeResponse> {
  const raw = await apiGet<components["schemas"]["HomeResponse"]>("/v1/home");
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

// T20 pre-build validation gate: landing-page signup, called from the
// browser (a mutation, not the SSR fetch path above).
export async function submitPilotSignup(body: {
  email: string;
  segment?: string;
  example_feed?: string;
}): Promise<void> {
  const response = await fetch(new URL("/v1/pilot-signups", apiUrl()), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(errorBody?.error?.message ?? "Signup failed");
  }
}
