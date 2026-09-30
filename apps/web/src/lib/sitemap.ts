import type { MetadataRoute } from "next";

import type { StoriesListResponse, StoryOut } from "./api";

// Imported only as types, so node's type stripping can run this file directly
// in tests (tests/sitemap.test.mjs) without the `@/` alias or Next.

// Per-visitor utility pages (/saved, /search, /onboarding, /account/delete) are
// left out on purpose and disallowed in robots.ts: they have no content of
// their own to index.
export const STATIC_ROUTES = [
  "",
  "/latest",
  "/topics",
  "/about",
  "/privacy",
  "/terms",
  "/ai-disclosure",
  "/corrections",
  "/copyright-takedown",
];
export const NOT_INDEXED = ["/saved", "/search", "/onboarding", "/account/"];

const PAGE_SIZE = 100; // the API's max `limit` for /v1/stories
// One sitemap file holds at most 50,000 URLs. Stop short of that, leaving room
// for the static and topic entries; past it this needs a sitemap index.
export const MAX_STORIES = 49_000;

type FetchPage = (params: { limit: string; cursor?: string }) => Promise<StoriesListResponse>;

export async function allPublishedStories(fetchPage: FetchPage): Promise<StoryOut[]> {
  const stories: StoryOut[] = [];
  let cursor: string | undefined;
  do {
    const page = await fetchPage(cursor ? { limit: String(PAGE_SIZE), cursor } : { limit: String(PAGE_SIZE) });
    stories.push(...page.items);
    cursor = page.next_cursor ?? undefined;
  } while (cursor && stories.length < MAX_STORIES);
  return stories.slice(0, MAX_STORIES);
}

export function sitemapEntries(base: string, stories: StoryOut[]): MetadataRoute.Sitemap {
  // Home and Latest change whenever a story does.
  const newest = latestOf(stories.map((s) => s.updated_at));
  const entries: MetadataRoute.Sitemap = STATIC_ROUTES.map((path) =>
    newest && (path === "" || path === "/latest") ? { url: `${base}${path}`, lastModified: newest } : { url: `${base}${path}` }
  );

  // Only topics with at least one published story (an empty topic page is thin
  // content to a crawler), dated by their newest story.
  const topicUpdated = new Map<string, string>();
  for (const story of stories) {
    for (const slug of story.topics) {
      topicUpdated.set(slug, latestOf([topicUpdated.get(slug), story.updated_at])!);
    }
  }
  for (const [slug, updated] of [...topicUpdated].sort(([a], [b]) => a.localeCompare(b))) {
    entries.push({ url: `${base}/topic/${slug}`, lastModified: updated });
  }

  for (const story of stories) {
    entries.push({ url: `${base}/story/${story.canonical_slug}`, lastModified: story.updated_at });
  }
  return entries;
}

function latestOf(dates: (string | undefined)[]): string | undefined {
  let best: string | undefined;
  for (const d of dates) {
    if (d && (!best || Date.parse(d) > Date.parse(best))) best = d;
  }
  return best;
}
