"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { components } from "@teluguvarta/contracts";

import { RangePicker, type DayRange } from "@/components/RangePicker";
import { Badge, EmptyState, PageHeader, StatTile } from "@/components/ui";
import { presets } from "@/lib/dateRange";
import { query } from "@/lib/lists";
import { adminFetch, SessionExpired } from "@/lib/reports";

// Review 2026-09-30 R8: what feeds send vs. what reaches readers, by
// publisher and topic, over a chosen range of UTC days.
type Report = components["schemas"]["CoverageReportOut"];
type Lag = components["schemas"]["CoverageLagOut"];

const pct = (part: number, whole: number) => (whole > 0 ? `${Math.round((part / whole) * 100)}%` : "—");
const share = (fraction: number) => `${Math.round(fraction * 100)}%`;
// A publisher holding more than this share of publications is flagged.
const CONCENTRATED = 0.5;

const OUTCOMES = [
  ["live", "Live"],
  ["in_review", "In review"],
  ["not_relevant", "Not relevant"],
  ["backlog_skipped", "Backlog skipped"],
  ["rights_blocked", "Rights blocked"],
  ["other", "Waiting / other"],
] as const;

const LAG: [keyof Lag, string][] = [
  ["under_1h", "Under 1 hour"],
  ["under_3h", "1–3 hours"],
  ["under_12h", "3–12 hours"],
  ["under_24h", "12–24 hours"],
  ["over_24h", "Over 24 hours"],
  ["unknown", "No publisher time"],
];

const storiesLink = (filters: Record<string, string>) => `/stories?${query(filters)}`;

export default function CoveragePage() {
  const router = useRouter();
  const [range, setRange] = useState<DayRange>(() => {
    const week = presets().find((p) => p.key === "7d")!;
    return { start: week.start, end: week.end };
  });
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    adminFetch<Report>(`/v1/admin/coverage?${query(range)}`, {}, "Failed to load coverage")
      .then((body) => {
        setReport(body);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof SessionExpired) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Failed to load coverage");
      })
      .finally(() => setLoading(false));
  }, [range, router]);

  useEffect(load, [load]);

  const header = (
    <PageHeader
      title="Coverage"
      subtitle={report ? `${report.start} to ${report.end} (UTC days) · feed items by publisher date, stories by publication date` : undefined}
      actions={
        <button type="button" className="button-secondary" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      }
    />
  );
  const rangePicker = <RangePicker range={range} onChange={setRange} />;

  if (!report) {
    return (
      <main>
        {header}
        {rangePicker}
        {error ? <p role="alert">{error}</p> : <p className="state-note">Loading…</p>}
      </main>
    );
  }

  const { items } = report;
  const silentTopics = report.topics.filter((t) => t.active && t.published === 0);
  const concentrated = report.top_publisher_share > CONCENTRATED;
  const peak = Math.max(...report.by_day.map((d) => d.published), 0);

  return (
    <main>
      {header}
      {rangePicker}
      {error ? <p role="alert">{error} — showing {report.start} to {report.end}.</p> : null}

      <div className="tile-grid">
        <StatTile href="#daily" label="Published" value={report.published} note={`from ${report.publishers_published} publishers`} />
        <StatTile
          href="#publishers"
          label="Top publisher share"
          value={share(report.top_publisher_share)}
          note={report.top_publisher ?? "nothing published"}
          tone={concentrated ? "warn" : "ok"}
        />
        <StatTile href="#feeds" label="Feed items reaching readers" value={pct(items.live, items.items)} note={`${items.live} of ${items.items} items`} />
        <StatTile
          href="#topics"
          label="Topics with nothing published"
          value={silentTopics.length}
          note={`${report.published_untagged} published stories have no topic`}
          tone={silentTopics.length > 0 ? "warn" : "ok"}
        />
      </div>

      {items.items === 0 && report.published === 0 ? (
        <EmptyState title="No feed items or publications in this range" hint="Pick another range above." />
      ) : null}

      <section id="daily">
        <h2>Daily publications</h2>
        <div className="table-scroll"><table>
          <thead>
            <tr><th>Day (UTC)</th><th>Published</th><th>Publishers</th><th aria-hidden="true" /></tr>
          </thead>
          <tbody>
            {[...report.by_day].reverse().map((day) => (
              <tr key={day.day}>
                <td>{day.day}</td>
                <td>{day.published}</td>
                <td>{day.publishers}{day.published > 1 && day.publishers === 1 ? <> <Badge tone="warn">one source</Badge></> : null}</td>
                <td aria-hidden="true" style={{ minWidth: "8rem" }}>
                  <div className="budget-bar">
                    <div className="budget-bar__fill" style={{ width: peak > 0 ? `${(day.published / peak) * 100}%` : 0 }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="publishers">
        <h2>By publisher</h2>
        <p className="field__hint">
          A story counts for the publisher whose item started it. Section feeds of one site count as one publisher.
          {report.published_without_source > 0 ? ` ${report.published_without_source} published stories have no source item (hand-drafted).` : ""}
        </p>
        {report.publishers.length === 0 ? <p className="field__hint">No publishers.</p> : (
          <div className="table-scroll"><table>
            <thead>
              <tr><th>Publisher</th><th>Feeds</th><th>Items</th><th>Items live</th><th>Stories published</th><th>Share</th></tr>
            </thead>
            <tbody>
              {report.publishers.map((row) => (
                <tr key={row.publisher}>
                  <td>{row.publisher}</td>
                  <td>{row.feeds}</td>
                  <td>{row.items}</td>
                  <td>{row.items > 0 ? `${row.live} (${pct(row.live, row.items)})` : "—"}</td>
                  <td>{row.published}</td>
                  <td>{row.published > 0 ? <>{share(row.share)}{row.share > CONCENTRATED ? <> <Badge tone="warn">concentrated</Badge></> : null}</> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section id="feeds">
        <h2>Feed yield</h2>
        <p className="field__hint">
          Every item a feed dated in this range, by where it ended up. Items without a publisher date are not counted.
          Totals: {OUTCOMES.map(([key, label]) => `${label.toLowerCase()} ${items[key]}`).join(" · ")}.
        </p>
        <div className="table-scroll"><table>
          <thead>
            <tr>
              <th>Feed</th><th>Items</th>
              {OUTCOMES.map(([key, label]) => <th key={key}>{label}</th>)}
              <th>Stories published</th><th>Median lag</th>
            </tr>
          </thead>
          <tbody>
            {report.sources.map((row) => (
              <tr key={row.source_id}>
                <td>
                  <Link href={storiesLink({ source_id: row.source_id })}>{row.name}</Link>
                  <span className="card__meta"> · {row.publisher}{row.category ? ` · ${row.category}` : ""}</span>
                  {!row.active ? <> <Badge tone="neutral">paused</Badge></> : null}
                  {row.rights_status !== "LINK_ONLY" ? <> <Badge tone="warn">{row.rights_status.toLowerCase()}</Badge></> : null}
                </td>
                <td>{row.items}</td>
                {OUTCOMES.map(([key]) => <td key={key}>{row[key] || "—"}</td>)}
                <td>{row.published || "—"}</td>
                <td>{row.median_lag_hours === null ? "—" : `${row.median_lag_hours} h`}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="lag">
        <h2>Time to publish</h2>
        <p className="field__hint">From the publisher&apos;s own timestamp to our publication, for stories published in this range.</p>
        <div className="table-scroll"><table>
          <thead><tr><th>Lag</th><th>Stories</th></tr></thead>
          <tbody>
            {LAG.map(([key, label]) => (
              <tr key={key}><td>{label}</td><td>{report.lag[key]}</td></tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="topics">
        <h2>By topic</h2>
        <p className="field__hint">Every active topic, including ones with nothing published. &ldquo;In review&rdquo; is the queue now, not limited to this range.</p>
        <div className="table-scroll"><table>
          <thead><tr><th>Topic</th><th>Published</th><th>In review now</th></tr></thead>
          <tbody>
            {report.topics.map((row) => (
              <tr key={row.slug}>
                <td>
                  <Link href={storiesLink({ topic: row.slug })}>{row.name}</Link>
                  {!row.active ? <> <Badge tone="neutral">inactive</Badge></> : null}
                </td>
                <td>{row.published > 0 ? row.published : <Badge tone="warn">none</Badge>}</td>
                <td>{row.in_review || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>
    </main>
  );
}
