import Link from "next/link";

export default function NotFound() {
  return (
    <div>
      <h1>Page not found</h1>
      <p>We couldn&rsquo;t find that page. It may have been moved, or the story may have been retracted.</p>
      <p>
        <Link href="/">Back to the home feed</Link>
      </p>
    </div>
  );
}
