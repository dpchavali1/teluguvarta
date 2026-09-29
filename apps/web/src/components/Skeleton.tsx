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
