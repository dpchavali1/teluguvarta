"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

import { humanize, REASON_CODES, reasonHelp, reasonTone } from "@/lib/reviewReasons";
import { Badge, EmptyState, Freshness, PageHeader } from "@/components/ui";
import { TranslationHolds } from "@/components/TranslationHolds";
import { adminFetch, SessionExpired } from "@/lib/reports";
import { query, TELUGU_OPTIONS, teluguTone, useFilterOptions } from "@/lib/lists";
import { age } from "@/lib/time";

type QueuePage = components["schemas"]["ReviewQueuePageOut"];
type ReviewQueueItem = QueuePage["items"][number];

const PAGE_SIZE = 50;
const AGE_OPTIONS = [
  { value: "", label: "Any" },
  { value: "6", label: "Over 6 hours" },
  { value: "24", label: "Over 1 day" },
  { value: "72", label: "Over 3 days" },
];

interface Filters {
  q: string;
  reason: string;
  topic: string;
  source_id: string;
  telugu: string;
  older_than_hours: string;
}

const NO_FILTERS: Filters = { q: "", reason: "", topic: "", source_id: "", telugu: "", older_than_hours: "" };

export default function ReviewQueuePage() {
  const router = useRouter();
  const { topics, sources } = useFilterOptions();
  const [page, setPage] = useState<QueuePage | null>(null);
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  // Review 2026-09-30 R7: the queue is paged and filtered on the server;
  // always-human-reviewed reasons come first there, so every page agrees.
  const [filterReady, setFilterReady] = useState(false);
  const [dangerOnly, setDangerOnly] = useState(false);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [search, setSearch] = useState("");
  const [revision, setRevision] = useState(0);
  const [active, setActive] = useState(0);
  const [showMoreFilters, setShowMoreFilters] = useState(false);

  // Design-review fix: a reviewer who filtered yesterday should see the same
  // always-human-reviewed view today.
  useEffect(() => {
    try { setDangerOnly(window.localStorage.getItem("tg-admin-review-danger-only") === "1"); } catch { /* Storage is optional. */ }
    setFilterReady(true);
  }, []);

  useEffect(() => {
    if (filterReady) { try { window.localStorage.setItem("tg-admin-review-danger-only", dangerOnly ? "1" : "0"); } catch { /* Storage is optional. */ } }
  }, [dangerOnly, filterReady]);

  const fetchPage = useCallback(
    (cursor: string | null) =>
      adminFetch<QueuePage>(
        `/v1/admin/review-queue?${query({ ...filters, danger_only: dangerOnly, limit: PAGE_SIZE, cursor })}`,
        {},
        "Failed to load review queue"
      ),
    [filters, dangerOnly]
  );

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof SessionExpired) router.replace("/login");
      else setError(err instanceof Error ? err.message : "Failed to load review queue");
    },
    [router]
  );

  useEffect(() => {
    if (!filterReady) return;
    setError(null);
    setLoading(true);
    fetchPage(null)
      .then((body) => {
        setPage(body);
        setItems(body.items);
        setActive(0);
        setLoadedAt(new Date());
      })
      .catch(handleError)
      .finally(() => setLoading(false));
  }, [fetchPage, filterReady, handleError, revision]);

  function loadMore() {
    if (!page?.next_cursor) return;
    setLoading(true);
    fetchPage(page.next_cursor)
      .then((body) => {
        setPage(body);
        setItems((prev) => [...prev, ...body.items]);
      })
      .catch(handleError)
      .finally(() => setLoading(false));
  }

  const setFilter = (key: keyof Filters, value: string) => setFilters((prev) => ({ ...prev, [key]: value }));
  const filtered = dangerOnly || Object.values(filters).some(Boolean);
  const advancedFilterCount = [filters.reason, filters.topic, filters.source_id, filters.telugu, filters.older_than_hours].filter(Boolean).length;

  const rowsRef = useRef(items);
  rowsRef.current = items;

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

  const subtitle = page
    ? `${page.pending_total} waiting · ${page.danger_total} always-human-reviewed · ${page.unclassified_total} unclassified` +
      (page.oldest_created_at ? ` · oldest ${age(page.oldest_created_at)}` : "")
    : undefined;

  return (
    <main>
      <PageHeader
        title="Review queue"
        subtitle={subtitle}
        actions={<Freshness loadedAt={loadedAt} loading={loading} onRefresh={() => setRevision((v) => v + 1)} />}
      />
      <form
        className="filter-bar"
        aria-label="Filters"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setFilter("q", search.trim());
        }}
      >
        <label>
          Search headline or source
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} onBlur={() => setFilter("q", search.trim())} />
        </label>
        <label className="filter-bar__check">
          <input type="checkbox" checked={dangerOnly} onChange={(event) => setDangerOnly(event.target.checked)} />
          Only always-human-reviewed
        </label>
        <button type="button" className="button-secondary filter-bar__toggle" aria-expanded={showMoreFilters} aria-controls="review-more-filters" onClick={() => setShowMoreFilters((open) => !open)}>
          {showMoreFilters ? "Fewer filters" : `More filters${advancedFilterCount ? ` (${advancedFilterCount})` : ""}`}
        </button>
        <div id="review-more-filters" className={`filter-bar__advanced${showMoreFilters ? " filter-bar__advanced--open" : ""}`}>
        <label>
          Reason
          <select value={filters.reason} onChange={(event) => setFilter("reason", event.target.value)}>
            <option value="">Any</option>
            {REASON_CODES.map((code) => (
              <option key={code} value={code}>{humanize(code)}</option>
            ))}
          </select>
        </label>
        <label>
          Topic
          <select value={filters.topic} onChange={(event) => setFilter("topic", event.target.value)}>
            <option value="">Any</option>
            {topics.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label>
          Source
          <select value={filters.source_id} onChange={(event) => setFilter("source_id", event.target.value)}>
            <option value="">Any</option>
            {sources.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label>
          Telugu
          <select value={filters.telugu} onChange={(event) => setFilter("telugu", event.target.value)}>
            {TELUGU_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <label>
          Waiting
          <select value={filters.older_than_hours} onChange={(event) => setFilter("older_than_hours", event.target.value)}>
            {AGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        </div>
        {filtered ? (
          <button type="button" className="button-secondary" onClick={() => { setFilters(NO_FILTERS); setSearch(""); setDangerOnly(false); }}>
            Clear filters
          </button>
        ) : null}
      </form>
      {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((value) => value + 1)}>Try again</button></div> : null}
      {page === null && !error ? (
        <p className="state-note">Loading…</p>
      ) : page && page.pending_total === 0 ? (
        <EmptyState title="Nothing pending review" hint="New stories that trip a review gate will show up here." />
      ) : page && items.length === 0 ? (
        <p className="state-note">No items match these filters.</p>
      ) : page ? (
        <>
          {filtered ? <p className="state-note">{page.total} match these filters.</p> : null}
          <div className="table-scroll review-queue"><table>
            <thead>
              <tr>
                <th>Story</th>
                <th className="col-wide-only">Sources</th>
                <th>Reason</th>
                {/* No Status column: every row here is PENDING. */}
                <th>Waiting</th>
                <th className="col-wide-only"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr
                  key={item.id}
                  aria-current={index === active ? "true" : undefined}
                  className={index === active ? "row-active" : undefined}
                  onClick={() => setActive(index)}
                >
                  <td>
                    <Link href={`/review/${item.story_id}`}>{item.headline ?? item.source_title ?? "Untitled story"}</Link>
                    <span className="review-queue__mobile-source">{item.source_names?.join(", ") || "No source linked"}</span>
                    {item.headline ? null : <span className="card__meta"> · no draft yet</span>}
                    {item.te_qa_status !== "PASSED" ? (
                      <span className="card__meta"> · <Badge tone={teluguTone(item.te_qa_status)}>{item.te_qa_status ? `Telugu ${item.te_qa_status.toLowerCase()}` : "no Telugu"}</Badge></span>
                    ) : null}
                  </td>
                  <td className="col-wide-only">{item.source_names?.join(", ") || "No source linked"}</td>
                  <td data-label="Review reason">
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
                  <td data-label="Waiting" title={new Date(item.created_at).toLocaleString()}>{age(item.created_at)}</td>
                  <td className="col-wide-only">
                    <Link href={`/review/${item.story_id}`} aria-label={`Review: ${item.headline ?? item.source_title ?? item.story_id}`}>Review</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <nav className="preset-row" aria-label="Pages">
            <span className="state-note">Showing {items.length} of {page.total}</span>
            {page.next_cursor ? (
              <button type="button" className="button-secondary" onClick={loadMore} disabled={loading}>
                {loading ? "Loading…" : `Load ${PAGE_SIZE} more`}
              </button>
            ) : null}
          </nav>
        </>
      ) : null}
      <TranslationHolds />
    </main>
  );
}
