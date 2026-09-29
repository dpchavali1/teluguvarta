import Link from "next/link";

export default function NotFound() {
  return (
    <div className="status-page">
      <p className="status-page__code" aria-hidden="true">404</p>
      <h1>Page not found</h1>
      <p>We couldn&rsquo;t find that page. It may have been moved, or the story may have been retracted.</p>
      <p className="status-page__actions">
        <Link className="button button--primary" href="/">Back to the home feed</Link>
        <Link className="button" href="/search">Search stories</Link>
      </p>
    </div>
  );
}
