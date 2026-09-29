import type { ReactNode } from "react";
import { notFound } from "next/navigation";

import { ApiNotFoundError, getTopic } from "@/lib/api";

// Same as app/story/[slug]/layout.tsx: check existence outside this segment's
// loading.tsx boundary so notFound() sets a real 404 status. Layouts can't
// read ?cursor, so this fetches page one — the same memoized request the page
// makes when there is no cursor.
export default async function TopicLayout({ children, params }: { children: ReactNode; params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  try {
    await getTopic(slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }
  return children;
}
