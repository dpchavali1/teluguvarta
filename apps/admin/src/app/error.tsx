"use client";

import { useEffect } from "react";

import { captureException } from "@/lib/errorTracking";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    captureException(error, { boundary: "app/error.tsx" });
  }, [error]);

  return (
    <main>
      <h1>Something went wrong</h1>
      <p>The error has been logged.</p>
    </main>
  );
}
