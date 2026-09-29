"use client";

import { useEffect, useState } from "react";

import { formatEditionDate } from "@/lib/format";

// The server only knows UTC, which is "tomorrow" for a US reader in the
// evening. Render the UTC date first (hydration-safe), then the reader's
// own local date.
export function EditionDate() {
  const [label, setLabel] = useState(() => formatEditionDate());
  useEffect(() => {
    setLabel(new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(new Date()));
  }, []);
  return <>{label}</>;
}
