import type { ReactNode } from "react";
import { notFound } from "next/navigation";

import { ApiNotFoundError, getStory } from "@/lib/api";
import { pathParam } from "@/lib/pathParam";

// Existence check outside this segment's loading.tsx boundary: a layout runs
// before the loading skeleton starts streaming, so notFound() here still sets
// a real 404 status. The fetch is memoized, so the page reuses this request.
export default async function StoryLayout({ children, params }: { children: ReactNode; params: Promise<{ slug: string }> }) {
  const slug = pathParam((await params).slug);
  if (slug === null) notFound();
  try {
    await getStory(slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }
  return children;
}
