import { notFound } from "next/navigation";

import { pathCursor } from "@/lib/api";

import { LatestFeed } from "../../LatestFeed";

export const metadata = { title: "Latest stories" };
export const revalidate = 60;

// Nothing prebuilt; each page renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export default async function OlderLatestPage({ params }: { params: Promise<{ cursor: string }> }) {
  const cursor = pathCursor((await params).cursor);
  if (!cursor) notFound();
  return <LatestFeed cursor={cursor} />;
}
