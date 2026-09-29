import type { Metadata } from "next";

import { TopicFeed, topicMetadata } from "./TopicFeed";

export const revalidate = 60;

type Props = { params: Promise<{ slug: string }> };

// Nothing prebuilt; each topic renders on first request, then is cached.
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return topicMetadata((await params).slug);
}

export default async function TopicPage({ params }: Props) {
  return <TopicFeed slug={(await params).slug} />;
}
