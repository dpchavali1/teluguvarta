// Loading placeholders shaped like the real cards, so route transitions show
// the page's structure immediately instead of a blank main area.
export function SkeletonCard({ lead = false }: { lead?: boolean }) {
  return (
    <div className={`skeleton-card${lead ? " skeleton-card--lead" : ""}`} aria-hidden="true">
      <span className="skeleton skeleton--meta" />
      <span className="skeleton skeleton--title" />
      <span className="skeleton skeleton--title skeleton--short" />
      <span className="skeleton skeleton--line" />
      <span className="skeleton skeleton--line skeleton--short" />
    </div>
  );
}

export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="story-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => <SkeletonCard key={index} />)}
    </div>
  );
}

export function LoadingStatus({ label = "Loading stories…" }: { label?: string }) {
  return <p className="visually-hidden" role="status">{label}</p>;
}

// Listing-page skeleton. Each listing route re-exports this from its own
// loading.tsx instead of one app/loading.tsx: a root-level loading boundary
// wraps every route, flushes the response early, and turns notFound() into a
// 200 (see app/story/[slug]/layout.tsx).
export function ListingSkeleton() {
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
