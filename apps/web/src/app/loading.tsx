import { LoadingStatus, SkeletonCard, SkeletonGrid } from "@/components/Skeleton";

// Shown instantly on navigation to any route without its own loading.tsx
// while the server fetches from the API.
export default function Loading() {
  return (
    <>
      <LoadingStatus />
      <div className="skeleton-header" aria-hidden="true">
        <span className="skeleton skeleton--meta" />
        <span className="skeleton skeleton--heading" />
      </div>
      <div className="front-grid" aria-hidden="true">
        <SkeletonCard lead />
        <div className="front-grid__side"><SkeletonCard /><SkeletonCard /></div>
      </div>
      <SkeletonGrid count={3} />
    </>
  );
}
