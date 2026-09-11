"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

interface ReviewQueueItem {
  id: string;
  story_id: string;
  reason: string;
  status: string;
  created_at: string;
}

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
  const [dangerOnly, setDangerOnly] = useState(false);

  // Design-review fix: this reset to false on every page load, undercutting
  // a queue whose whole point is surfacing highest-stakes items first — a
  // reviewer who filtered yesterday saw the unfiltered list again today.
  useEffect(() => {
    setDangerOnly(window.localStorage.getItem("tg-admin-review-danger-only") === "1");
  }, []);

  useEffect(() => {
    window.localStorage.setItem("tg-admin-review-danger-only", dangerOnly ? "1" : "0");
  }, [dangerOnly]);

  useEffect(() => {
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
  }, [router]);

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
      {error ? <p role="alert">{error}</p> : null}
      {items !== null && items.length > 0 && (
        <label>
          <input type="checkbox" checked={dangerOnly} onChange={(event) => setDangerOnly(event.target.checked)} />
          Show only always-human-reviewed categories
        </label>
      )}
      {items === null ? (
        <p className="state-note">Loading…</p>
      ) : items.length === 0 ? (
        <p className="state-note">Nothing pending review.</p>
      ) : visibleItems && visibleItems.length === 0 ? (
        <p className="state-note">No items match this filter.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Reason</th>
              <th>Status</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(visibleItems ?? []).map((item) => (
              <tr key={item.id}>
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
                  <Link href={`/review/${item.story_id}`}>Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
