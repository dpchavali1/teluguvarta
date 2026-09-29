"use client";

import { useEffect, useState } from "react";

import { formatDate, relativeTime } from "@/lib/format";

// Server and first client render show the absolute UTC date (identical
// output, so no hydration mismatch); after mount it switches to "3h ago"
// for anything under a week old.
export function TimeAgo({ iso }: { iso: string }) {
  const absolute = formatDate(iso);
  const [label, setLabel] = useState(absolute);
  useEffect(() => {
    setLabel(relativeTime(iso) ?? absolute);
  }, [iso, absolute]);
  return <time dateTime={iso} title={absolute}>{label}</time>;
}
