import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { pathCursor } from "@/lib/api";

import { TopicFeed, topicMetadata } from "../../TopicFeed";

export const revalidate = 60;

type Props = { params: Promise<{ slug: string; cursor: string }> };

// Nothing prebuilt; each page renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return topicMetadata((await params).slug);
}

export default async function OlderTopicPage({ params }: Props) {
  const { slug, cursor: raw } = await params;
  const cursor = pathCursor(raw);
  if (!cursor) notFound();
  return <TopicFeed slug={slug} cursor={cursor} />;
}
