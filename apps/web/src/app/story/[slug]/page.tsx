import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { StoryCard } from "@/components/StoryCard";
import { TrackEvent } from "@/components/TrackEvent";
import { ApiNotFoundError, getShareMeta, getStory } from "@/lib/api";

export const revalidate = 60;

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  try {
    const meta = await getShareMeta(params.slug);
    return {
      title: meta.title,
      description: meta.description,
      alternates: { canonical: meta.canonical_url },
      openGraph: {
        title: meta.title,
        description: meta.description,
        url: meta.canonical_url,
        type: "article",
        // Text-only social preview in this phase — ADR-002 defers the
        // branded Share Card image feature, so no `images` field here.
      },
      twitter: { card: "summary", title: meta.title, description: meta.description },
    };
  } catch (err) {
    if (err instanceof ApiNotFoundError) return {};
    throw err;
  }
}

export default async function StoryPage({ params }: Props) {
  let story;
  try {
    story = await getStory(params.slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }

  return (
    <div className="story-detail">
      <TrackEvent event="story_open" properties={{ story_id: story.id }} />
      <p className="story-detail__meta">
        Published {story.published_at ? new Date(story.published_at).toLocaleDateString() : "—"}
      </p>
      <StoryCard story={story} headingLevel="h1" />
    </div>
  );
}
