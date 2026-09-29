import type { ReactNode } from "react";

import { StoryCard } from "@/components/StoryCard";
import type { StoryOut } from "@/lib/api";

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="page-header">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      {children && <div className="page-header__lede">{children}</div>}
    </header>
  );
}

// Every listing route renders StoryBriefs in the same responsive card grid.
export function StoryGrid({ stories, empty }: { stories: StoryOut[]; empty?: ReactNode }) {
  if (stories.length === 0) return empty ? <div className="empty-state">{empty}</div> : null;
  return (
    <ul className="story-grid">
      {stories.map((story) => (
        <li key={story.id}>
          <StoryCard story={story} display="brief" />
        </li>
      ))}
    </ul>
  );
}
