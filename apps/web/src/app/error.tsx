"use client";

import { useEffect } from "react";

import { captureException } from "@/lib/errorTracking";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    captureException(error, { boundary: "app/error.tsx" });
  }, [error]);

  return (
    <div>
      <h1>Something went wrong</h1>
      <p>We hit an unexpected error loading this page. Please try again.</p>
      <button type="button" onClick={() => reset()}>
        Try again
      </button>
    </div>
  );
}
