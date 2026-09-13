"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

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

  return (
    <main>
      <h1>Review queue</h1>
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
        <p className="state-note">Nothing pending review.</p>
      ) : visibleItems && visibleItems.length === 0 ? (
        <p className="state-note">No items match this filter.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Story</th>
              <th>Sources</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(visibleItems ?? []).map((item) => (
              <tr key={item.id}>
                <td><Link href={`/review/${item.story_id}`}>{item.headline ?? "Draft headline pending"}</Link></td>
                <td>{item.source_names?.join(", ") || "No source linked"}</td>
                <td>
                  {/* `reason` is a comma-joined list when a story trips more
                      than one gate (see jobs/generate.py). */}
                  <span className="pill-row">
                    {item.reason.split(",").map((reason) => (
                      <span
                        key={reason}
                        className={`status-pill status-pill--${reasonTone(reason.trim())}`}
                      >
                        {humanize(reason.trim())}
                      </span>
                    ))}
                  </span>
                </td>
                <td>
                  <span className="status-pill status-pill--warn">{humanize(item.status)}</span>
                </td>
                <td>{new Date(item.created_at).toLocaleString()}</td>
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
