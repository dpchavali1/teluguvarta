"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, PageHeader } from "@/components/ui";
import { CATEGORY_LABELS, SessionExpired, adminFetch, resolutionLabel, type ReaderReport, type ReaderReportList } from "@/lib/reports";
import { ago } from "@/lib/time";

// ADR-029: private reader reports. Open reports come oldest first — the next one to handle.
const STATUSES = [
  { value: "OPEN", label: "Open" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "DISMISSED", label: "Dismissed" },
  { value: "ALL", label: "All" },
] as const;
type StatusFilter = (typeof STATUSES)[number]["value"];

const PAGE_SIZE = 50;

const statusTone = (status: ReaderReport["status"]) => (status === "OPEN" ? "warn" : status === "RESOLVED" ? "ok" : "neutral");

export default function ReportsPage() {
  const router = useRouter();
  const [status, setStatus] = useState<StatusFilter>("OPEN");
  const [category, setCategory] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [list, setList] = useState<ReaderReportList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams({ status, limit: String(PAGE_SIZE), offset: String(offset) });
    if (category) params.set("category", category);
    setLoading(true);
    adminFetch<ReaderReportList>(`/v1/admin/reports?${params}`, {}, "Failed to load reports")
      .then((body) => {
        setList(body);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof SessionExpired) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Failed to load reports");
      })
      .finally(() => setLoading(false));
  }, [status, category, offset, router]);

  useEffect(load, [load]);

  const header = (
    <PageHeader
      title="Reader reports"
      subtitle={list ? `${list.open_count} open · private to editors · text is erased 90 days after closing` : undefined}
      actions={
        <button type="button" className="button-secondary" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      }
    />
  );

  const filters = (
    <section aria-label="Filters" className="preset-row">
      {STATUSES.map((s) => (
        <button
          key={s.value}
          type="button"
          className={status === s.value ? "is-selected" : "button-secondary"}
          aria-pressed={status === s.value}
          onClick={() => {
            setStatus(s.value);
            setOffset(0);
          }}
        >
          {s.label}
        </button>
      ))}
      <label>
        Category{" "}
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Any</option>
          {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
    </section>
  );

  if (!list) {
    return (
      <main>
        {header}
        {filters}
        {error ? <p role="alert">{error}</p> : <p className="state-note">Loading…</p>}
      </main>
    );
  }

  const end = offset + list.items.length;

  return (
    <main>
      {header}
      {filters}
      {error ? <p role="alert">{error} — showing the last loaded list.</p> : null}

      {list.items.length === 0 ? (
        <EmptyState
          title={status === "OPEN" ? "No open reports" : "No reports match"}
          hint={status === "OPEN" ? "Reports readers send from a story appear here." : "Try another status or category."}
        />
      ) : (
        <div className="table-scroll"><table>
          <thead>
            <tr>
              <th>Received</th>
              <th>Category</th>
              <th>Story</th>
              <th>Report</th>
              <th>Sender</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((report) => (
              <tr key={report.id}>
                <td>{ago(report.created_at)}</td>
                <td>{CATEGORY_LABELS[report.category]}</td>
                <td>
                  <Link href={`/reports/${report.id}`}>{report.story_headline ?? report.story_slug}</Link>
                </td>
                <td>
                  {report.description ? (
                    report.description.length > 140 ? `${report.description.slice(0, 140)}…` : report.description
                  ) : (
                    <span className="card__meta">{report.description_purged_at ? "Text erased (retention)" : "No text"}</span>
                  )}
                </td>
                <td>
                  <code>{report.sender}</code>
                  {report.repeat_count > 0 ? <span className="card__meta"> +{report.repeat_count} repeats</span> : null}
                </td>
                <td>
                  <Badge tone={statusTone(report.status)}>
                    {report.status === "OPEN" ? "Open" : resolutionLabel(report.resolution)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}

      {list.total > PAGE_SIZE ? (
        <nav className="preset-row" aria-label="Pages">
          <button type="button" className="button-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </button>
          <span className="state-note">
            {offset + 1}–{end} of {list.total}
          </span>
          <button type="button" className="button-secondary" disabled={end >= list.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </button>
        </nav>
      ) : null}
    </main>
  );
}
