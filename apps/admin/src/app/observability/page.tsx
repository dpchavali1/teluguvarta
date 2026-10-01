"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, PageHeader, StatTile, type Tone, useToast } from "@/components/ui";
import { BUDGET_MODE, type BudgetMode, budgetModeMessage, usd } from "@/lib/aiBudget";
import { apiUrl, clearSession, getToken } from "@/lib/auth";
import { STALE_QUEUE_SECONDS, ago, duration } from "@/lib/time";

interface SourceIngestionHealth {
  source_id: string;
  source_name: string;
  success_count_24h: number;
  failure_count_24h: number;
  fail_count: number;
  circuit_breaker_tripped: boolean;
  last_success_at: string | null;
  last_error_at: string | null;
}

interface JobQueueHealth {
  counts_by_status: Record<string, number>;
  oldest_pending_age_seconds: number | null;
}

interface AiCostRow {
  task: string;
  day: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

interface AiCostSummary {
  month_to_date_cost_usd: number;
  monthly_budget_usd: number | null;
  monthly_budget_remaining_usd: number | null;
  today_cost_usd: number;
  daily_alert_usd: number | null;
  over_monthly_budget: boolean;
  monthly_hard_cap_usd: number | null;
  hard_cap_remaining_usd: number | null;
  mode: BudgetMode;
  day_start: string;
  month_start: string;
  quota_resets_at: string;
  rows: AiCostRow[];
}

interface XCostSummary {
  month_to_date_cost_usd: number;
  monthly_budget_usd: number | null;
  monthly_budget_remaining_usd: number | null;
  over_monthly_budget: boolean;
  low_priority_accounts_paused: number;
}

type OpsState = "OK" | "STALE" | "FAILING" | "NEVER";

interface OpsCheck {
  check: string;
  label: string;
  state: OpsState;
  last_success_at: string | null;
  success_detail: string | null;
  last_failure_at: string | null;
  failure_detail: string | null;
  max_age_seconds: number | null;
}

interface Observability {
  ingestion_health: SourceIngestionHealth[];
  job_queue: JobQueueHealth;
  ai_cost: AiCostSummary;
  x_cost: XCostSummary;
  operations: OpsCheck[];
}

// Review 2026-09-30 R3: text as well as colour, and NEVER is a problem —
// an unrecorded backup is not evidence of one.
const OPS_STATE: Record<OpsState, { label: string; tone: Tone }> = {
  OK: { label: "OK", tone: "ok" },
  STALE: { label: "Overdue", tone: "warn" },
  FAILING: { label: "Failing", tone: "danger" },
  NEVER: { label: "No record", tone: "warn" },
};

interface XAccount {
  id: string;
  source_id: string;
  x_user_id: string;
  handle: string;
  priority: number;
  polling_cadence: number | null;
  since_id: string | null;
  budget_class: string | null;
  rights_status: string;
  active: boolean;
  last_success_at: string | null;
  last_error_at: string | null;
  fail_count: number;
  circuit_breaker_tripped: boolean;
  recent_error_count_24h: number;
  month_to_date_cost_usd: number;
  budget_paused: boolean;
}



function BudgetBar({ spent, budget }: { spent: number; budget: number | null }) {
  if (budget === null || budget <= 0) return <p className="field__hint">No monthly budget set.</p>;
  const pct = Math.min(100, Math.round((spent / budget) * 100));
  return (
    <div className="budget-bar" role="img" aria-label={`${pct}% of monthly budget used`}>
      <div className={`budget-bar__fill${pct >= 100 ? " budget-bar__fill--over" : ""}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function ObservabilityPage() {
  const router = useRouter();
  const toast = useToast();
  const [data, setData] = useState<Observability | null>(null);
  const [xAccounts, setXAccounts] = useState<XAccount[] | null>(null);
  const [pausingSourceId, setPausingSourceId] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  // Review 2026-09-30 R4: a failed minute refresh leaves old figures on screen,
  // so say so until a refresh succeeds rather than only flashing a toast.
  const [refreshFailedAt, setRefreshFailedAt] = useState<Date | null>(null);

  const load = useCallback(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    const get = (path: string) =>
      fetch(`${apiUrl()}/v1/admin${path}`, { headers: { Authorization: `Bearer ${token}` } }).then((response) => {
        if (response.status === 401) {
          clearSession();
          router.replace("/login");
        }
        return response.ok ? response.json() : Promise.reject(new Error(`Failed to load ${path.slice(1)}`));
      });
    get("/observability")
      .then((body: Observability) => {
        setData(body);
        setUpdatedAt(new Date());
        setRefreshFailedAt(null);
      })
      .catch((err) => {
        setRefreshFailedAt(new Date());
        toast("danger", err instanceof Error ? err.message : "Failed to load observability data");
      });
    get("/x-accounts")
      .then((body: XAccount[]) => setXAccounts(body))
      .catch((err) => toast("danger", err instanceof Error ? err.message : "Failed to load X accounts"));
  }, [router, toast]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);

  async function togglePause(account: XAccount) {
    const token = getToken();
    setPausingSourceId(account.source_id);
    try {
      const response = await fetch(`${apiUrl()}/v1/admin/sources/${account.source_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ active: !account.active })
      });
      if (!response.ok) {
        const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(errorBody?.error?.message ?? "Failed to update X account");
      }
      toast("ok", `${account.handle} ${account.active ? "paused" : "resumed"}.`);
      load();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to update X account");
    } finally {
      setPausingSourceId(null);
    }
  }

  const header = (
    <PageHeader
      title="Observability"
      subtitle={updatedAt ? `Updated ${updatedAt.toLocaleTimeString()} · refreshes every minute` : undefined}
      actions={
        <button type="button" className="button-secondary" onClick={load}>
          Refresh
        </button>
      }
    />
  );

  if (data === null) {
    return (
      <main>
        {header}
        {refreshFailedAt ? <p role="alert">Could not load observability data. Try Refresh.</p> : <p className="state-note">Loading…</p>}
      </main>
    );
  }

  const jobs = data.job_queue.counts_by_status;
  const oldest = data.job_queue.oldest_pending_age_seconds;
  const ai = data.ai_cost;
  const x = data.x_cost;
  const budgetMessage = budgetModeMessage(ai.mode, ai.monthly_budget_usd, ai.monthly_hard_cap_usd);
  // Problems first: tripped breakers, then most failures in 24h.
  const opsProblems = data.operations.filter((op) => op.state !== "OK");
  const health = [...data.ingestion_health].sort(
    (a, b) => Number(b.circuit_breaker_tripped) - Number(a.circuit_breaker_tripped) || b.failure_count_24h - a.failure_count_24h
  );

  return (
    <main>
      {header}
      {refreshFailedAt && updatedAt ? (
        <p role="alert">
          Refresh failed at {refreshFailedAt.toLocaleTimeString()} — the figures below are from {updatedAt.toLocaleTimeString()}.
        </p>
      ) : null}

      <div className="tile-grid">
        <StatTile href="#ingestion" label="Sources tripped" value={health.filter((h) => h.circuit_breaker_tripped).length} note={`${health.length} sources`} tone={health.some((h) => h.circuit_breaker_tripped) ? "danger" : "ok"} />
        <StatTile href="#jobs" label="Jobs pending" value={jobs.PENDING ?? 0} note={oldest !== null ? `oldest waiting ${duration(oldest)}` : "queue empty"} tone={(jobs.FAILED ?? 0) > 0 ? "danger" : oldest !== null && oldest > STALE_QUEUE_SECONDS ? "warn" : "ok"} />
        <StatTile href="#ai-cost" label="AI spend this month (est.)" value={usd(ai.month_to_date_cost_usd)} note={`${ai.monthly_budget_usd !== null ? `of ${usd(ai.monthly_budget_usd)}` : "no budget set"} · ${BUDGET_MODE[ai.mode].label.toLowerCase()}`} tone={BUDGET_MODE[ai.mode].tone} />
        <StatTile href="#operations" label="Backups & monitoring" value={opsProblems.length === 0 ? "OK" : `${opsProblems.length} to check`} note={`${data.operations.length} checks`} tone={opsProblems.some((op) => op.state === "FAILING") ? "danger" : opsProblems.length > 0 ? "warn" : "ok"} />
        <StatTile href="#x" label="X spend (month)" value={usd(x.month_to_date_cost_usd)} note={x.monthly_budget_usd !== null ? `of ${usd(x.monthly_budget_usd)}` : "no budget set"} tone={x.over_monthly_budget ? "danger" : "ok"} />
      </div>

      <section id="operations">
        <h2>Backups &amp; monitoring</h2>
        <p className="card__meta">Reported by the server&apos;s backup, restore-drill and monitor scripts (infra/deploy). Overdue means no success within the expected interval.</p>
        <div className="table-scroll"><table>
          <thead>
            <tr>
              <th>Check</th>
              <th>Status</th>
              <th>Last success</th>
              <th>Last failure</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {data.operations.map((op) => (
              <tr key={op.check}>
                <td>
                  {op.label}
                  {op.max_age_seconds !== null ? <span className="card__meta"> (due every {duration(op.max_age_seconds)})</span> : null}
                </td>
                <td><Badge tone={OPS_STATE[op.state].tone}>{OPS_STATE[op.state].label}</Badge></td>
                <td title={op.last_success_at ? new Date(op.last_success_at).toLocaleString() : undefined}>{ago(op.last_success_at)}</td>
                <td title={op.last_failure_at ? new Date(op.last_failure_at).toLocaleString() : undefined}>{ago(op.last_failure_at)}</td>
                <td>{(op.state === "FAILING" ? op.failure_detail : op.success_detail) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </section>

      <section id="ingestion">
        <h2>Ingestion health (last 24h)</h2>
        {health.length === 0 ? (
          <EmptyState title="No sources configured" hint="Add one on the Sources page." />
        ) : (
          <div className="table-scroll"><table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>OK / failed (24h)</th>
                <th>Consecutive failures</th>
                <th>Last success</th>
                <th>Last error</th>
              </tr>
            </thead>
            <tbody>
              {health.map((row) => (
                <tr key={row.source_id}>
                  <td>{row.source_name}</td>
                  <td>
                    {row.circuit_breaker_tripped ? <Badge tone="danger">Tripped</Badge> : row.fail_count > 0 ? <Badge tone="warn">Failing</Badge> : <Badge tone="ok">OK</Badge>}
                  </td>
                  <td>
                    {row.success_count_24h} / {row.failure_count_24h}
                  </td>
                  <td>{row.fail_count}</td>
                  <td title={row.last_success_at ? new Date(row.last_success_at).toLocaleString() : undefined}>{ago(row.last_success_at)}</td>
                  <td title={row.last_error_at ? new Date(row.last_error_at).toLocaleString() : undefined}>{ago(row.last_error_at)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section id="jobs">
        <h2>Job queue</h2>
        {Object.keys(jobs).length === 0 ? (
          <p className="state-note">No jobs yet.</p>
        ) : (
          <p className="pill-row">
            {Object.entries(jobs).map(([status, count]) => (
              <Badge key={status} tone={status === "FAILED" && count > 0 ? "danger" : status === "DONE" ? "ok" : "neutral"}>
                {status}: {count}
              </Badge>
            ))}
          </p>
        )}
      </section>

      <section id="ai-cost">
        <h2>AI cost vs. budget</h2>
        <p className="pill-row">
          Mode: <Badge tone={BUDGET_MODE[ai.mode].tone}>{BUDGET_MODE[ai.mode].label}</Badge>
        </p>
        {budgetMessage ? <p role="alert">{budgetMessage}</p> : null}
        <BudgetBar spent={ai.month_to_date_cost_usd} budget={ai.monthly_budget_usd} />
        <dl className="kv-list">
          <dt>Today</dt>
          <dd>{usd(ai.today_cost_usd)}{ai.daily_alert_usd !== null ? ` (alert at ${usd(ai.daily_alert_usd)})` : ""}</dd>
          <dt>This month</dt>
          <dd>{usd(ai.month_to_date_cost_usd)}</dd>
          <dt>Monthly budget</dt>
          <dd>
            {ai.monthly_budget_usd !== null ? `${usd(ai.monthly_budget_usd)} — summaries, why-it-matters and translations stop here` : "not set"}
            {ai.monthly_budget_remaining_usd !== null ? ` (${usd(Math.max(0, ai.monthly_budget_remaining_usd))} left)` : ""}
          </dd>
          <dt>Hard cap</dt>
          <dd>
            {ai.monthly_hard_cap_usd !== null ? `${usd(ai.monthly_hard_cap_usd)} — all paid calls stop here` : "not set"}
            {ai.hard_cap_remaining_usd !== null ? ` (${usd(Math.max(0, ai.hard_cap_remaining_usd))} left)` : ""}
          </dd>
        </dl>
        <p className="field__hint">
          Estimates from logged token counts and list prices, not a reconciled invoice; cached input is priced at
          the full rate. &ldquo;Today&rdquo; and the month are UTC (today began {new Date(ai.day_start).toLocaleString()} your
          time). The Gemini free-tier quota resets separately, at midnight Pacific (next {new Date(ai.quota_resets_at).toLocaleString()}).
          Limits are checked before each call, so a call already running can finish past them.
        </p>
        {ai.rows.length > 0 ? (
          <details>
            <summary>Daily breakdown ({ai.rows.length} rows)</summary>
            <div className="table-scroll"><table>
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Task</th>
                  <th>Tokens in</th>
                  <th>Tokens out</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {ai.rows.map((row) => (
                  <tr key={`${row.day}-${row.task}`}>
                    <td>{row.day}</td>
                    <td>{row.task}</td>
                    <td>{row.tokens_in}</td>
                    <td>{row.tokens_out}</td>
                    <td>${row.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          </details>
        ) : null}
      </section>

      <section id="x">
        <h2>X account health &amp; budget</h2>
        {x.over_monthly_budget ? (
          <p role="alert">Over monthly budget — {x.low_priority_accounts_paused} low-priority account(s) paused.</p>
        ) : null}
        <BudgetBar spent={x.month_to_date_cost_usd} budget={x.monthly_budget_usd} />
        <p className="card__meta">
          Month-to-date {usd(x.month_to_date_cost_usd)}
          {x.monthly_budget_remaining_usd !== null ? ` · ${usd(x.monthly_budget_remaining_usd)} remaining` : ""}
        </p>
        {xAccounts === null ? (
          <p className="state-note">Loading X accounts…</p>
        ) : xAccounts.length === 0 ? (
          <EmptyState title="No X accounts configured" />
        ) : (
          <div className="table-scroll"><table>
            <thead>
              <tr>
                <th>Handle</th>
                <th>Status</th>
                <th>Budget class</th>
                <th>Failures</th>
                <th>Errors (24h)</th>
                <th>MTD cost</th>
                <th>Last success</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {xAccounts.map((account) => (
                <tr key={account.id} title={account.since_id ? `since_id ${account.since_id}` : undefined}>
                  <td>{account.handle}</td>
                  <td>
                    <span className="pill-row">
                      <Badge tone={account.rights_status === "DISABLED" ? "danger" : "ok"}>{account.rights_status}</Badge>
                      <Badge tone={account.active ? "ok" : "warn"}>{account.active ? "Active" : "Paused"}</Badge>
                      {account.budget_paused ? <Badge tone="warn">Budget-paused</Badge> : null}
                      {account.circuit_breaker_tripped ? <Badge tone="danger">Tripped</Badge> : null}
                    </span>
                  </td>
                  <td>{account.budget_class ?? "—"}</td>
                  <td>{account.fail_count}</td>
                  <td>{account.recent_error_count_24h}</td>
                  <td>{usd(account.month_to_date_cost_usd)}</td>
                  <td>{ago(account.last_success_at)}</td>
                  <td>
                    <button type="button" className="button-secondary" disabled={pausingSourceId === account.source_id} onClick={() => togglePause(account)}>
                      {account.active ? "Pause" : "Resume"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>
    </main>
  );
}
