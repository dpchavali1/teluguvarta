"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { EmptyState, Freshness, PageHeader } from "@/components/ui";
import { query } from "@/lib/lists";
import { adminFetch, SessionExpired } from "@/lib/reports";
import { humanize } from "@/lib/reviewReasons";

// Review 2026-09-30 R7: the whole audit log, searchable and paged (the API
// used to return only the latest 200 events, with no page here at all).
type AuditPage = components["schemas"]["AdminAuditPageOut"];
type AuditEvent = AuditPage["items"][number];

const PAGE_SIZE = 100;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

interface Filters {
  action: string;
  actor: string;
  entity_type: string;
  entity_id: string;
  since: string;
  until: string;
}

function entityHref(event: AuditEvent): string | null {
  if (event.entity_type === "story") return `/review/${event.entity_id}`;
  if (event.entity_type === "reader_report") return `/reports/${event.entity_id}`;
  return null;
}

// Date inputs are local days; the API takes instants. `until` is exclusive, so add a day.
function dayStart(value: string, addDays = 0): string | null {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + addDays);
  return date.toISOString();
}

function AuditLog() {
  const router = useRouter();
  const params = useSearchParams();
  const [draft, setDraft] = useState<Filters>(() => ({
    action: params.get("action") ?? "",
    actor: params.get("actor") ?? "",
    entity_type: params.get("entity_type") ?? "",
    entity_id: params.get("entity_id") ?? "",
    since: "",
    until: "",
  }));
  const [filters, setFilters] = useState<Filters>(draft);
  const [items, setItems] = useState<AuditEvent[] | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);
  const [knownActions, setKnownActions] = useState<string[]>([]);

  const fetchPage = useCallback(
    (cursor: string | null) =>
      adminFetch<AuditPage>(
        `/v1/admin/audit?${query({
          action: filters.action, actor: filters.actor, entity_type: filters.entity_type,
          entity_id: UUID_RE.test(filters.entity_id.trim()) ? filters.entity_id.trim() : null,
          since: dayStart(filters.since), until: dayStart(filters.until, 1), limit: PAGE_SIZE, cursor,
        })}`,
        {},
        "Failed to load the audit log"
      ),
    [filters]
  );

  const accept = useCallback((body: AuditPage, append: boolean) => {
    setItems((prev) => (append && prev ? [...prev, ...body.items] : body.items));
    setNextCursor(body.next_cursor ?? null);
    setKnownActions((prev) => [...new Set([...prev, ...body.items.map((e) => e.action)])].sort());
  }, []);

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof SessionExpired) router.replace("/login");
      else setError(err instanceof Error ? err.message : "Failed to load the audit log");
    },
    [router]
  );

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchPage(null)
      .then((body) => {
        accept(body, false);
        setLoadedAt(new Date());
      })
      .catch(fail)
      .finally(() => setLoading(false));
  }, [fetchPage, accept, fail, revision]);

  function loadMore() {
    if (!nextCursor) return;
    setLoading(true);
    fetchPage(nextCursor).then((body) => accept(body, true)).catch(fail).finally(() => setLoading(false));
  }

  const set = (key: keyof Filters) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setDraft((prev) => ({ ...prev, [key]: event.target.value }));
  const badEntity = draft.entity_id.trim() !== "" && !UUID_RE.test(draft.entity_id.trim());

  return (
    <main>
      <PageHeader
        title="Audit log"
        subtitle="Every recorded change, newest first. Times are in your local time zone."
        actions={<Freshness loadedAt={loadedAt} loading={loading} onRefresh={() => setRevision((v) => v + 1)} />}
      />
      <form
        className="filter-bar"
        role="search"
        aria-label="Filters"
        onSubmit={(event) => {
          event.preventDefault();
          if (!badEntity) setFilters(draft);
        }}
      >
        <label>
          Action
          <input type="text" list="audit-actions" value={draft.action} onChange={set("action")} placeholder="STORY_APPROVED" />
          <datalist id="audit-actions">
            {knownActions.map((a) => <option key={a} value={a} />)}
          </datalist>
        </label>
        <label>
          Actor contains
          <input type="text" value={draft.actor} onChange={set("actor")} placeholder="email or job" />
        </label>
        <label>
          Entity type
          <input type="text" value={draft.entity_type} onChange={set("entity_type")} placeholder="story" />
        </label>
        <label>
          Entity ID
          <input type="text" value={draft.entity_id} onChange={set("entity_id")} aria-invalid={badEntity} spellCheck={false} />
        </label>
        <label>
          From
          <input type="date" value={draft.since} onChange={set("since")} />
        </label>
        <label>
          To
          <input type="date" value={draft.until} onChange={set("until")} />
        </label>
        <button type="submit" disabled={badEntity}>Search</button>
        <button
          type="button"
          className="button-secondary"
          onClick={() => {
            const empty = { action: "", actor: "", entity_type: "", entity_id: "", since: "", until: "" };
            setDraft(empty);
            setFilters(empty);
          }}
        >
          Clear
        </button>
        {badEntity ? <p role="alert" className="field__hint">Entity ID must be a full ID.</p> : null}
      </form>
      {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((v) => v + 1)}>Try again</button></div> : null}
      {items === null ? (
        error ? null : <p className="state-note">Loading…</p>
      ) : items.length === 0 ? (
        <EmptyState title="No events match" hint="Widen the dates or clear a filter." />
      ) : (
        <>
          <div className="table-scroll"><table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Entity</th>
                <th className="col-wide-only">Details</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event) => {
                const href = entityHref(event);
                return (
                  <tr key={event.id}>
                    <td>{new Date(event.created_at).toLocaleString()}</td>
                    <td>{humanize(event.action)}</td>
                    <td>{event.actor ?? "—"}</td>
                    <td>
                      {event.entity_type}{" "}
                      {href ? <Link href={href}>{event.entity_id.slice(0, 8)}</Link> : <code>{event.entity_id.slice(0, 8)}</code>}{" "}
                      <button
                        type="button"
                        className="button-secondary"
                        aria-label={`Show only ${event.entity_type} ${event.entity_id}`}
                        onClick={() => {
                          const next = { ...draft, entity_type: event.entity_type, entity_id: event.entity_id };
                          setDraft(next);
                          setFilters(next);
                        }}
                      >
                        Only this
                      </button>
                    </td>
                    <td className="col-wide-only">
                      {Object.keys(event.metadata ?? {}).length ? (
                        <pre className="audit-meta">{JSON.stringify(event.metadata, null, 1)}</pre>
                      ) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table></div>
          <nav className="preset-row" aria-label="Pages">
            <span className="state-note">Showing {items.length}</span>
            {nextCursor ? (
              <button type="button" className="button-secondary" onClick={loadMore} disabled={loading}>
                {loading ? "Loading…" : "Load older"}
              </button>
            ) : <span className="state-note">· end of log</span>}
          </nav>
        </>
      )}
    </main>
  );
}

export default function AuditPage() {
  return (
    <Suspense fallback={<p className="state-note">Loading…</p>}>
      <AuditLog />
    </Suspense>
  );
}
