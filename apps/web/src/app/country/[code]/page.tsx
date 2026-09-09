import type { Metadata } from "next";

import { StoryCard } from "@/components/StoryCard";
import { listStories } from "@/lib/api";

export const revalidate = 60;

type Props = { params: { code: string } };

export function generateMetadata({ params }: Props): Metadata {
  const code = params.code.toUpperCase();
  return { title: `${code} news`, description: `Latest stories about ${code} on Telugu Global.` };
}

export default async function CountryPage({ params }: Props) {
  const code = params.code.toUpperCase();
  const { items } = await listStories({ country: code });

  return (
    <>
      <h1>{code} news</h1>
      {items.length === 0 ? (
        <p className="empty-state">No published stories about {code} yet.</p>
      ) : (
        <ul className="story-list">
          {items.map((story) => (
            <li key={story.id}>
              <StoryCard story={story} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
