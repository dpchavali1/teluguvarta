// Runs with node's built-in test runner and type stripping: `pnpm --filter @teluguvarta/web test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import { allPublishedStories, MAX_STORIES, NOT_INDEXED, sitemapEntries } from "../src/lib/sitemap.ts";

const story = (n, topics = [], updated = `2026-09-${String((n % 28) + 1).padStart(2, "0")}T00:00:00Z`) => ({
  canonical_slug: `story-${n}`,
  topics,
  updated_at: updated,
});

function pagedApi(total) {
  const all = Array.from({ length: total }, (_, i) => story(i));
  const calls = [];
  const fetchPage = async ({ limit, cursor }) => {
    calls.push(cursor);
    const offset = cursor ? Number(cursor) : 0;
    const end = offset + Number(limit);
    return { items: all.slice(offset, end), next_cursor: end < total ? String(end) : null };
  };
  return { fetchPage, calls };
}

test("follows next_cursor past the first page", async () => {
  const { fetchPage, calls } = pagedApi(250);
  const stories = await allPublishedStories(fetchPage);
  assert.equal(stories.length, 250);
  assert.deepEqual(calls, [undefined, "100", "200"]);
  const urls = sitemapEntries("https://x", stories).map((e) => e.url);
  assert.ok(urls.includes("https://x/story/story-0"));
  assert.ok(urls.includes("https://x/story/story-249"));
});

test("stops at the one-file URL cap", async () => {
  const { fetchPage } = pagedApi(MAX_STORIES + 500);
  assert.equal((await allPublishedStories(fetchPage)).length, MAX_STORIES);
});

test("lists only populated topics, dated by their newest story", () => {
  const entries = sitemapEntries("https://x", [
    story(1, ["visas"], "2026-09-01T00:00:00Z"),
    story(2, ["visas", "tollywood"], "2026-09-20T00:00:00Z"),
  ]);
  const topics = entries.filter((e) => e.url.includes("/topic/"));
  assert.deepEqual(topics, [
    { url: "https://x/topic/tollywood", lastModified: "2026-09-20T00:00:00Z" },
    { url: "https://x/topic/visas", lastModified: "2026-09-20T00:00:00Z" },
  ]);
  assert.equal(entries.find((e) => e.url === "https://x/latest").lastModified, "2026-09-20T00:00:00Z");
});

test("leaves out per-visitor utility pages", () => {
  const urls = sitemapEntries("https://x", []).map((e) => e.url);
  for (const path of NOT_INDEXED) {
    assert.ok(!urls.some((u) => u.startsWith(`https://x${path}`)), path);
  }
  assert.ok(urls.includes("https://x/latest"));
});
