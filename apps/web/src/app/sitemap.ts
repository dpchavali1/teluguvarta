import type { MetadataRoute } from "next";

import { duringBuild, listStories, siteUrl } from "@/lib/api";
import { allPublishedStories, sitemapEntries } from "@/lib/sitemap";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Unreachable API: at build, static routes still get a sitemap; at runtime it
  // throws, so ISR keeps serving the last good one rather than caching one
  // with no stories.
  const stories = await allPublishedStories(listStories).catch(duringBuild([]));
  return sitemapEntries(siteUrl(), stories);
}
