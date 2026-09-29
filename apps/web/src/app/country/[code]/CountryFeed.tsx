import Link from "next/link";
import type { Metadata } from "next";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { listStories } from "@/lib/api";

// Shared by /country/[code] and /country/[code]/older/[cursor]. The cursor
// lives in the path, not ?cursor=, because reading searchParams opts a page
// out of ISR.
export function countryMetadata(code: string): Metadata {
  return { title: `${code} news`, description: `Latest stories about ${code} on TTE.` };
}

export async function CountryFeed({ code, cursor }: { code: string; cursor?: string }) {
  const { items, next_cursor } = await listStories({ country: code, cursor });

  return (
    <>
      <PageHeader eyebrow="Country" title={`${code} news`} />
      <StoryGrid stories={items} empty={<>No published stories about {code} yet.</>} />
      <nav className="pagination" aria-label="Story pages">
        {cursor && <Link className="button" href={`/country/${code}`}>Latest in this country</Link>}
        {next_cursor && <Link className="button" href={`/country/${code}/older/${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
      </nav>
    </>
  );
}
