import { LoadingStatus } from "@/components/Skeleton";

export default function StoryLoading() {
  return (
    <div className="story-page">
      <LoadingStatus label="Loading story…" />
      <div className="story-detail skeleton-article" aria-hidden="true">
        <span className="skeleton skeleton--meta" />
        <span className="skeleton skeleton--display" />
        <span className="skeleton skeleton--display skeleton--short" />
        <span className="skeleton skeleton--line" />
        <span className="skeleton skeleton--line" />
        <span className="skeleton skeleton--line skeleton--short" />
        <span className="skeleton skeleton--block" />
      </div>
    </div>
  );
}
