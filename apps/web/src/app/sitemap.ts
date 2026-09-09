import type { MetadataRoute } from "next";

import { getConfig, listStories, siteUrl } from "@/lib/api";

export const revalidate = 3600;

const STATIC_ROUTES = [
  "",
  "/search",
  "/saved",
  "/about",
  "/privacy",
  "/terms",
  "/ai-disclosure",
  "/corrections",
  "/copyright-takedown",
  "/account/delete",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const entries: MetadataRoute.Sitemap = STATIC_ROUTES.map((path) => ({ url: `${base}${path}` }));

  try {
    const config = await getConfig();
    for (const topic of config.topics) {
      entries.push({ url: `${base}/topic/${topic.slug}` });
    }
  } catch {
    // API unreachable at build time — static routes still get a sitemap.
  }

  try {
    const { items } = await listStories();
    for (const story of items) {
      entries.push({ url: `${base}/story/${story.canonical_slug}`, lastModified: story.updated_at });
    }
  } catch {
    // same as above
  }

  return entries;
}
