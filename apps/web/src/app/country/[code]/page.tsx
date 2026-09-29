import Link from "next/link";
import type { Metadata } from "next";

import { PageHeader, StoryGrid } from "@/components/StoryGrid";
import { listStories } from "@/lib/api";

export const revalidate = 60;
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ code: string }>; searchParams: Promise<{ cursor?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const code = (await params).code.toUpperCase();
  return { title: `${code} news`, description: `Latest stories about ${code} on TTE.` };
}

export default async function CountryPage({ params, searchParams }: Props) {
  const code = (await params).code.toUpperCase();
  const { cursor } = await searchParams;
  const { items, next_cursor } = await listStories({ country: code, cursor });

  return (
    <>
      <PageHeader eyebrow="Country" title={`${code} news`} />
      <StoryGrid stories={items} empty={<>No published stories about {code} yet.</>} />
      <nav className="pagination" aria-label="Story pages">
        {cursor && <Link className="button" href={`/country/${code}`}>Latest in this country</Link>}
        {next_cursor && <Link className="button" href={`/country/${code}?cursor=${encodeURIComponent(next_cursor)}`}>Older stories →</Link>}
      </nav>
    </>
  );
}
