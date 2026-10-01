"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { Badge, EmptyState, Freshness, PageHeader } from "@/components/ui";
import { query, STORY_STATUSES, statusInfo, TELUGU_OPTIONS, teluguTone, useFilterOptions } from "@/lib/lists";
import { adminFetch, SessionExpired } from "@/lib/reports";
import { ago } from "@/lib/time";

// Review 2026-09-30 R7: every story in any status — drafts, scheduled,
// live, corrected, retracted — in one searchable library. Changes still
// happen one story at a time on its review page.
type StoryList = components["schemas"]["AdminStoryListOut"];

const PAGE_SIZE = 50;

export default function StoriesPage() {
  const router = useRouter();
  const { topics, sources } = useFilterOptions();
  const [list, setList] = useState<StoryList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  // "" = all, "CORRECTED" = has a correction, else a story status.
  const [view, setView] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [telugu, setTelugu] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  // Links from other pages (e.g. coverage) preselect filters via the URL.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setView(params.get("status") ?? "");
    setTopic(params.get("topic") ?? "");
    setSourceId(params.get("source_id") ?? "");
    setReady(true);
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = query({
      status: view && view !== "CORRECTED" ? view : null,
      corrected: view === "CORRECTED",
      q, topic, source_id: sourceId, telugu, limit: PAGE_SIZE, offset,
    });
    adminFetch<StoryList>(`/v1/admin/stories?${params}`, {}, "Failed to load stories")
      .then((body) => {
        setList(body);
        setLoadedAt(new Date());
      })
      .catch((err) => {
        if (err instanceof SessionExpired) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Failed to load stories");
      })
      .finally(() => setLoading(false));
  }, [view, q, topic, sourceId, telugu, offset, router]);

  useEffect(() => {
    if (ready) load();
  }, [load, revision, ready]);

  function change<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setOffset(0);
    };
  }

  const all = list ? Object.values(list.status_counts).reduce((sum, n) => sum + n, 0) : null;
  const views = [
    { value: "", label: "All", count: all },
    ...STORY_STATUSES.map((s) => ({ value: s.value as string, label: s.label, count: list?.status_counts[s.value] ?? 0 })).filter(
      (s) => s.count > 0 || s.value === view
    ),
    { value: "CORRECTED", label: "Corrected", count: list?.corrected_total ?? null },
  ];
  const end = list ? offset + list.items.length : 0;

  return (
    <main>
      <PageHeader
        title="Stories"
        subtitle="Every story by latest activity. Open one to review, correct or retract it."
        actions={<Freshness loadedAt={loadedAt} loading={loading} onRefresh={() => setRevision((v) => v + 1)} />}
      />
      <section aria-label="Status" className="preset-row">
        {views.map((v) => (
          <button
            key={v.value || "all"}
            type="button"
            className={view === v.value ? "is-selected" : "button-secondary"}
            aria-pressed={view === v.value}
            onClick={() => change(setView)(v.value)}
          >
            {v.label}
            {v.count !== null ? ` (${v.count})` : ""}
          </button>
        ))}
      </section>
      <form
        className="filter-bar"
        role="search"
        aria-label="Filters"
        onSubmit={(event) => {
          event.preventDefault();
          change(setQ)(search.trim());
        }}
      >
        <label>
          Search headline, source or slug
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} onBlur={() => search.trim() !== q && change(setQ)(search.trim())} />
        </label>
        <label>
          Topic
          <select value={topic} onChange={(event) => change(setTopic)(event.target.value)}>
            <option value="">Any</option>
            {topics.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label>
          Source
          <select value={sourceId} onChange={(event) => change(setSourceId)(event.target.value)}>
            <option value="">Any</option>
            {sources.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label>
          Telugu
          <select value={telugu} onChange={(event) => change(setTelugu)(event.target.value)}>
            {TELUGU_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </form>
      {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((v) => v + 1)}>Try again</button></div> : null}
      {!list ? (
        error ? null : <p className="state-note">Loading…</p>
      ) : list.items.length === 0 ? (
        <EmptyState title="No stories match" hint="Try another status or clear the search." />
      ) : (
        <>
          <div className="table-scroll"><table>
            <thead>
              <tr>
                <th>Story</th>
                <th>Status</th>
                <th className="col-wide-only">Telugu</th>
                <th className="col-wide-only">Source</th>
                <th>Activity</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((story) => {
                const status = statusInfo(story.status);
                return (
                  <tr key={story.id}>
                    <td>
                      <Link href={`/review/${story.id}`}>{story.headline ?? story.source_title ?? story.canonical_slug}</Link>
                      {story.headline ? null : <span className="card__meta"> · no draft yet</span>}
                      {story.topics?.length ? <span className="card__meta"> · {story.topics.join(", ")}</span> : null}
                    </td>
                    <td>
                      <span className="pill-row">
                        <Badge tone={status.tone}>{status.label}</Badge>
                        {story.format === "BRIEF" ? <Badge>Brief</Badge> : null}
                        {story.sensitivity !== "NONE" ? <Badge tone="danger">{story.sensitivity.toLowerCase()}</Badge> : null}
                        {story.review_pending ? <Badge tone="warn">awaiting review</Badge> : null}
                        {story.corrections ? <Badge tone="warn">{story.corrections} correction{story.corrections > 1 ? "s" : ""}</Badge> : null}
                      </span>
                    </td>
                    <td className="col-wide-only">
                      <Badge tone={teluguTone(story.te_qa_status)}>{story.te_qa_status?.toLowerCase() ?? "none"}</Badge>
                    </td>
                    <td className="col-wide-only">{story.source_names?.join(", ") || "—"}</td>
                    <td title={story.last_activity_at ? new Date(story.last_activity_at).toLocaleString() : undefined}>
                      {story.published_at ? `published ${ago(story.published_at)}` : story.last_activity_at ? `drafted ${ago(story.last_activity_at)}` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table></div>
          <nav className="preset-row" aria-label="Pages">
            <button type="button" className="button-secondary" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </button>
            <span className="state-note">{offset + 1}–{end} of {list.total}</span>
            <button type="button" className="button-secondary" disabled={end >= list.total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next
            </button>
          </nav>
        </>
      )}
    </main>
  );
}
