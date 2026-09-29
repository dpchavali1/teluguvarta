"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

import { EmptyState, PageHeader } from "@/components/ui";
import { apiUrl, clearSession, getToken } from "@/lib/auth";

type ReviewQueueItem = components["schemas"]["ReviewQueueItemOut"];

// Reasons that map to the always-human-reviewed categories in
// docs/NON_NEGOTIABLES.md get the danger tone so a reviewer can spot them
// without reading every row; everything else is a warn-tone pill.
const DANGER_REASONS = new Set([
  "SENSITIVE_CATEGORY",
  "IMMIGRATION",
  "LEGAL",
  "FINANCIAL",
  "BREAKING"
]);

function reasonTone(reason: string): "warn" | "danger" {
  return DANGER_REASONS.has(reason) ? "danger" : "warn";
}

// Plain-language "why is this held" for each gate in jobs/generate.py. Unknown
// codes fall back to the humanized code so a new gate is never hidden.
const REASON_HELP: Record<string, string> = {
  SENSITIVE_CATEGORY: "Sensitive topic — always needs a human (NON_NEGOTIABLES).",
  IMMIGRATION: "Immigration story — always human-reviewed.",
  LEGAL: "Legal story — always human-reviewed.",
  FINANCIAL: "Financial story — always human-reviewed.",
  BREAKING: "Breaking news — always human-reviewed.",
  HIGH_IMPORTANCE: "Marked high urgency, so a person checks it before it goes out.",
  LOW_CONFIDENCE_CLASSIFICATION: "The AI wasn't confident about the category.",
  LOW_CONFIDENCE_GENERATION: "The AI wasn't confident in its summary.",
  SIMILARITY_TO_SOURCE: "The summary is too close to the source text — rewrite it.",
  NO_PAID_PROVIDER: "This source's category needs paid AI and none is configured, so no draft was written."
};

const reasonHelp = (reason: string) => REASON_HELP[reason.trim()] ?? humanize(reason.trim());

function age(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h` : `${Math.round(hours / 24)}d`;
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").toLowerCase();
}

export default function ReviewQueuePage() {
  const router = useRouter();
  const [items, setItems] = useState<ReviewQueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Design-review fix: the queue was flat and unsorted — as volume grows,
  // there was no way to surface always-human-reviewed categories first.
  const [filterReady, setFilterReady] = useState(false);
  const [revision, setRevision] = useState(0);
  const [dangerOnly, setDangerOnly] = useState(false);
  const [active, setActive] = useState(0);

  // Design-review fix: this reset to false on every page load, undercutting
  // a queue whose whole point is surfacing highest-stakes items first — a
  // reviewer who filtered yesterday saw the unfiltered list again today.
  useEffect(() => {
    try { setDangerOnly(window.localStorage.getItem("tg-admin-review-danger-only") === "1"); } catch { /* Storage is optional. */ }
    setFilterReady(true);
  }, []);

  useEffect(() => {
    if (filterReady) { try { window.localStorage.setItem("tg-admin-review-danger-only", dangerOnly ? "1" : "0"); } catch { /* Storage is optional. */ } }
  }, [dangerOnly, filterReady]);

  useEffect(() => {
    setError(null);
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/review-queue`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            clearSession();
            router.replace("/login");
          }
          throw new Error("Failed to load review queue");
        }
        return response.json();
      })
      .then((body: ReviewQueueItem[]) => setItems(body))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load review queue"));
  }, [router, revision]);

  // Danger-tone (always-human-reviewed) rows first, otherwise oldest first
  // (queue order) — a reviewer scanning top-to-bottom sees the
  // highest-stakes items before routine ones regardless of arrival order.
  const sortedItems = items
    ? [...items].sort((a, b) => {
        const aDanger = a.reason.split(",").some((r) => reasonTone(r.trim()) === "danger");
        const bDanger = b.reason.split(",").some((r) => reasonTone(r.trim()) === "danger");
        return aDanger === bDanger ? 0 : aDanger ? -1 : 1;
      })
    : null;
  const visibleItems = dangerOnly
    ? sortedItems?.filter((item) => item.reason.split(",").some((r) => reasonTone(r.trim()) === "danger"))
    : sortedItems;

  const rows = visibleItems ?? [];
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  // j/k move, Enter opens the highlighted story. Opening is the only action —
  // approve/reject stay on the detail page so nothing is decided unseen.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(target.tagName)) return;
      const list = rowsRef.current;
      if (event.key === "j") setActive((i) => Math.min(i + 1, Math.max(list.length - 1, 0)));
      else if (event.key === "k") setActive((i) => Math.max(i - 1, 0));
      else if (event.key === "Enter" && list[active]) router.push(`/review/${list[active].story_id}`);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, router]);

  useEffect(() => {
    document.querySelector('tr[aria-current="true"]')?.scrollIntoView({ block: "nearest" });
  }, [active]);

  useEffect(() => setActive(0), [dangerOnly]);

  const dangerCount = (items ?? []).filter((item) => item.reason.split(",").some((r) => reasonTone(r.trim()) === "danger")).length;

  return (
    <main>
      <PageHeader
        title="Review queue"
        subtitle={items ? `${items.length} waiting · ${dangerCount} always-human-reviewed · press j / k to move, Enter to open` : undefined}
      />
      {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((value) => value + 1)}>Try again</button></div> : null}
      {items !== null && items.length > 0 && (
        <label>
          <input type="checkbox" checked={dangerOnly} onChange={(event) => setDangerOnly(event.target.checked)} />
          Show only always-human-reviewed categories
        </label>
      )}
      {items === null && !error ? (
        <p className="state-note">Loading…</p>
      ) : items?.length === 0 ? (
        <EmptyState title="Nothing pending review" hint="New stories that trip a review gate will show up here." />
      ) : visibleItems && visibleItems.length === 0 ? (
        <p className="state-note">No items match this filter.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Story</th>
              <th>Sources</th>
              <th>Reason</th>
              {/* No Status column: this endpoint only ever returns
                  ReviewTask.status === "PENDING" rows, so every cell would
                  read the same value — dead width on a dense table. */}
              <th>Waiting</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item, index) => (
              <tr
                key={item.id}
                aria-current={index === active ? "true" : undefined}
                className={index === active ? "row-active" : undefined}
                onClick={() => setActive(index)}
              >
                <td><Link href={`/review/${item.story_id}`}>{item.headline ?? "Draft headline pending"}</Link></td>
                <td>{item.source_names?.join(", ") || "No source linked"}</td>
                <td>
                  {/* `reason` is a comma-joined list when a story trips more
                      than one gate (see jobs/generate.py). */}
                  <span className="pill-row">
                    {item.reason.split(",").map((reason) => (
                      <span
                        key={reason}
                        title={reasonHelp(reason)}
                        className={`status-pill status-pill--${reasonTone(reason.trim())}`}
                      >
                        {humanize(reason.trim())}
                      </span>
                    ))}
                  </span>
                  <span className="reason-help">{item.reason.split(",").map(reasonHelp).join(" ")}</span>
                </td>
                <td title={new Date(item.created_at).toLocaleString()}>{age(item.created_at)}</td>
                <td>
                  <Link href={`/review/${item.story_id}`} aria-label={`Review: ${item.headline ?? item.story_id}`}>Review</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
