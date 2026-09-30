import { notFound } from "next/navigation";

import { pathParam } from "@/lib/pathParam";

import { LatestFeed } from "../../LatestFeed";

export const metadata = { title: "Latest stories" };
export const revalidate = 60;

// Nothing prebuilt; each page renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export default async function OlderLatestPage({ params }: { params: Promise<{ cursor: string }> }) {
  const cursor = pathParam((await params).cursor);
  if (!cursor) notFound();
  return <LatestFeed cursor={cursor} />;
}
