import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { StoryCard } from "@/components/StoryCard";
import { ApiNotFoundError, getTopic } from "@/lib/api";

export const revalidate = 60;

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  try {
    const { topic } = await getTopic(params.slug);
    return { title: topic.name, description: `Latest ${topic.name} stories on Telugu Global.` };
  } catch (err) {
    if (err instanceof ApiNotFoundError) return {};
    throw err;
  }
}

export default async function TopicPage({ params }: Props) {
  let data;
  try {
    data = await getTopic(params.slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound();
    throw err;
  }

  return (
    <>
      <h1>{data.topic.name}</h1>
      {data.stories.length === 0 ? (
        <p className="empty-state">No published stories in this topic yet.</p>
      ) : (
        <ul className="story-list">
          {data.stories.map((story) => (
            <li key={story.id}>
              <StoryCard story={story} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
