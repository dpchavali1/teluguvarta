import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { topicLabel } from "@teluguvarta/domain";

import { Icon } from "@/components/Icon";
import { StoryCard } from "@/components/StoryCard";
import { TrackEvent } from "@/components/TrackEvent";
import { ApiNotFoundError, getShareMeta, getStory, listStories, storyUrl, type StoryOut } from "@/lib/api";

export const revalidate = 60;

type Props = { params: Promise<{ slug: string }> };

// No stories prebuilt (build never needs the API); each one renders on first
// request and is then cached and revalidated every 60s.
export async function generateStaticParams() {
  return [];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const meta = await getShareMeta(slug);
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

// "More in <topic>" is a nice-to-have: never let it fail the article.
async function relatedStories(story: StoryOut): Promise<StoryOut[]> {
  const topic = story.topics[0];
  try {
    const { items } = await listStories(topic ? { topic, limit: "5" } : { limit: "5" });
    return items.filter((item) => item.id !== story.id).slice(0, 4);
  } catch {
    return [];
  }
}

// schema.org NewsArticle so search engines can show the story as news.
// Only fields we actually have: no image, no author byline (AI-drafted).
function articleJsonLd(story: StoryOut): string {
  const en = story.variants.en;
  return JSON.stringify({
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: en?.headline,
    description: en?.summary,
    datePublished: story.published_at ?? undefined,
    dateModified: story.updated_at,
    mainEntityOfPage: storyUrl(story.canonical_slug),
    publisher: { "@type": "Organization", name: "The Telugu Edit" },
    isBasedOn: story.sources.map((source) => source.url),
  }).replace(/</g, "\\u003c");
}

export default async function StoryPage({ params }: Props) {
  const { slug } = await params;
  let story;
  try {
    story = await getStory(slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }
  const related = await relatedStories(story);
  const topic = story.topics[0];

  return (
    <div className="story-page">
      <TrackEvent event="story_open" properties={{ story_id: story.id }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: articleJsonLd(story) }} />
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <ol>
          <li><Link href="/">Home</Link></li>
          {topic && <li><Link href={`/topic/${topic}`}>{topicLabel(topic)}</Link></li>}
        </ol>
      </nav>
      <div className="story-detail">
        <StoryCard story={story} headingLevel="h1" />
      </div>
      {related.length > 0 && (
        <aside className="related" aria-labelledby="related-title">
          <div className="section-head">
            <h2 id="related-title">{topic ? `More in ${topicLabel(topic)}` : "More stories"}</h2>
            <Link className="section-head__more" href={topic ? `/topic/${topic}` : "/latest"}>See all <Icon name="arrowRight" size={16} /></Link>
          </div>
          <ul className="story-grid story-grid--compact">
            {related.map((item) => (
              <li key={item.id}><StoryCard story={item} headingLevel="h3" display="brief" /></li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
