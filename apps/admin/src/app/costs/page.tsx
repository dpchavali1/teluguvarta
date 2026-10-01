"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { components } from "@teluguvarta/contracts";

import { RangePicker } from "@/components/RangePicker";
import { Badge, EmptyState, PageHeader, StatTile } from "@/components/ui";
import { usd } from "@/lib/aiBudget";
import { apiFetch, apiUrl, clearSession, isSignedIn } from "@/lib/auth";
import { presets } from "@/lib/dateRange";
import { humanize } from "@/lib/reviewReasons";

// Review 2026-09-30 R5: where AI money goes, over a chosen range of UTC days.
type Report = components["schemas"]["AiCostReportOut"];
type Figures = components["schemas"]["AiCostFiguresOut"];

const tokens = (n: number) => n.toLocaleString();
const pct = (part: number, whole: number) => (whole > 0 ? `${Math.round((part / whole) * 100)}%` : "—");

function TokenCells({ row }: { row: Figures }) {
  return (
    <>
      <td>{tokens(row.tokens_in)}{row.tokens_cached > 0 ? <span className="card__meta"> ({tokens(row.tokens_cached)} cached)</span> : null}</td>
      <td>{tokens(row.tokens_out)}{row.tokens_thinking > 0 ? <span className="card__meta"> ({tokens(row.tokens_thinking)} thinking)</span> : null}</td>
    </>
  );
}

export default function CostsPage() {
  const router = useRouter();
  const [range, setRange] = useState(() => {
    const mtd = presets().find((p) => p.key === "mtd")!;
    return { start: mtd.start, end: mtd.end };
  });
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    const signedIn = isSignedIn();
    if (!signedIn) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    apiFetch(`${apiUrl()}/v1/admin/ai-costs?start=${range.start}&end=${range.end}`)
      .then(async (response) => {
        if (response.status === 401) {
          clearSession();
          router.replace("/login");
          throw new Error("Session expired");
        }
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
          throw new Error(body?.error?.message ?? "Failed to load AI costs");
        }
        return response.json() as Promise<Report>;
      })
      .then((body) => {
        setReport(body);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load AI costs"))
      .finally(() => setLoading(false));
  }, [range, router]);

  useEffect(load, [load]);

  const header = (
    <PageHeader
      title="AI costs"
      subtitle={report ? `${report.start} to ${report.end} (UTC days) · estimates from logged tokens and list prices` : undefined}
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

  const { totals, publication_cohort: cohort } = report;
  const peak = Math.max(...report.by_day.map((d) => d.cost_usd), 0);
  const paid = report.breakdown.filter((r) => r.tier === "PAID").reduce((sum, r) => sum + r.cost_usd, 0);

  return (
    <main>
      {header}
      {rangePicker}
      {error ? <p role="alert">{error} — showing {report.start} to {report.end}.</p> : null}

      <div className="tile-grid">
        <StatTile href="#trend" label="Spend (est.)" value={usd(totals.cost_usd)} note={`${totals.calls.toLocaleString()} calls · ${usd(paid)} paid`} />
        <StatTile
          href="#outcomes"
          label="Paid for, not used"
          value={usd(totals.unusable_cost_usd)}
          note={`${totals.unusable_calls} calls · ${pct(totals.unusable_cost_usd, totals.cost_usd)} of spend`}
          tone={totals.unusable_cost_usd > 0 ? "warn" : "ok"}
        />
        <StatTile href="#outcomes" label="Retry spend" value={usd(totals.retry_cost_usd)} note="constrained retries that succeeded" />
        <StatTile href="#stories" label="Not linked to a story" value={usd(report.unlinked.cost_usd)} note={`${report.unlinked.calls} calls`} />
        <StatTile
          href="#cohort"
          label="Published in range"
          value={cohort.stories_published}
          note={`lifecycle AI cost ${usd(cohort.lifecycle_cost_usd)}`}
        />
      </div>

      {totals.calls === 0 ? <EmptyState title="No AI calls in this range" hint="Pick another range above." /> : null}

      <section id="trend">
        <h2>Daily spend</h2>
        <div className="table-scroll"><table>
          <thead>
            <tr><th>Day (UTC)</th><th>Spend</th><th>Calls</th><th>Not used</th><th aria-hidden="true" /></tr>
          </thead>
          <tbody>
            {[...report.by_day].reverse().map((day) => (
              <tr key={day.day}>
                <td>{day.day}</td>
                <td>{usd(day.cost_usd)}</td>
                <td>{day.calls}</td>
                <td>{day.unusable_calls > 0 ? `${day.unusable_calls} (${usd(day.unusable_cost_usd)})` : "—"}</td>
                <td aria-hidden="true" style={{ minWidth: "8rem" }}>
                  <div className="budget-bar">
                    <div className="budget-bar__fill" style={{ width: peak > 0 ? `${(day.cost_usd / peak) * 100}%` : 0 }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="breakdown">
        <h2>By provider, model and task</h2>
        {report.breakdown.length === 0 ? <p className="field__hint">No calls.</p> : (
          <div className="table-scroll"><table>
            <thead>
              <tr><th>Provider</th><th>Model</th><th>Task</th><th>Calls</th><th>Not used</th><th>Tokens in</th><th>Tokens out</th><th>Spend</th></tr>
            </thead>
            <tbody>
              {report.breakdown.map((row) => (
                <tr key={`${row.provider}-${row.model}-${row.task}`}>
                  <td>{row.provider} {row.tier !== "PAID" ? <Badge tone="neutral">{row.tier === "FREE" ? "free tier" : "no provider"}</Badge> : null}</td>
                  <td>{row.model || "—"}</td>
                  <td>{humanize(row.task)}</td>
                  <td>{row.calls}</td>
                  <td>{row.unusable_calls > 0 ? `${row.unusable_calls} (${pct(row.unusable_calls, row.calls)})` : "—"}</td>
                  <TokenCells row={row} />
                  <td>{usd(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section id="outcomes">
        <h2>Call outcomes</h2>
        <p className="card__meta">
          Success and retry-success replies were used. Holds, parse errors and blocked replies are still billed. A
          constrained retry follows an unusable first reply, so its cost sits on top of that reply&apos;s. Deferred and
          provider-error calls usually cost nothing.
        </p>
        <div className="table-scroll"><table>
          <thead><tr><th>Outcome</th><th>Calls</th><th>Spend</th></tr></thead>
          <tbody>
            {report.outcomes.map((row) => (
              <tr key={row.status}>
                <td>
                  <Badge tone={row.status === "SUCCESS" || row.status === "RETRY_SUCCESS" ? "ok" : "warn"}>{humanize(row.status)}</Badge>
                </td>
                <td>{row.calls}</td>
                <td>{usd(row.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="stories">
        <h2>Spend by where the story is now</h2>
        <p className="card__meta">Calls in this range linked to a story, grouped by that story&apos;s current status. {usd(report.unlinked.cost_usd)} ({report.unlinked.calls} calls) had no story.</p>
        {report.by_story_status.length === 0 ? <p className="field__hint">No story-linked calls.</p> : (
          <div className="table-scroll"><table>
            <thead><tr><th>Story status</th><th>Stories</th><th>Calls</th><th>Spend</th></tr></thead>
            <tbody>
              {report.by_story_status.map((row) => (
                <tr key={row.status}><td>{humanize(row.status)}</td><td>{row.stories}</td><td>{row.calls}</td><td>{usd(row.cost_usd)}</td></tr>
              ))}
            </tbody>
          </table></div>
        )}
        <h3>Costliest stories in this range</h3>
        {report.top_stories.length === 0 ? <p className="field__hint">None.</p> : (
          <div className="table-scroll"><table>
            <thead><tr><th>Story</th><th>Status</th><th>Calls</th><th>Not used</th><th>Spend</th></tr></thead>
            <tbody>
              {report.top_stories.map((story) => (
                <tr key={story.story_id}>
                  <td><Link href={`/review/${story.story_id}`}>{story.headline ?? story.story_id.slice(0, 8)}</Link></td>
                  <td>{humanize(story.status)}</td>
                  <td>{story.calls}</td>
                  <td>{story.unusable_calls || "—"}</td>
                  <td>{usd(story.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section id="cohort">
        <h2>Stories published in this range</h2>
        <dl className="kv-list">
          <dt>Published</dt>
          <dd>{cohort.stories_published}</dd>
          <dt>Their lifecycle AI cost</dt>
          <dd>
            {usd(cohort.lifecycle_cost_usd)} over {cohort.lifecycle_calls} calls
            {cohort.stories_published > 0 ? ` · ${usd(cohort.lifecycle_cost_usd / cohort.stories_published)} per published story on average` : ""}
          </dd>
        </dl>
        <p className="field__hint">
          Lifecycle cost counts every call linked to these stories, including calls before or after this range. It
          leaves out spend on stories that were never published and calls with no story, so it is not this
          range&apos;s spend divided by publications.
        </p>
      </section>
    </main>
  );
}
