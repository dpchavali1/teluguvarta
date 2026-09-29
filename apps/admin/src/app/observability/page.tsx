"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, PageHeader, StatTile, useToast } from "@/components/ui";
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
  rows: AiCostRow[];
}

interface XCostSummary {
  month_to_date_cost_usd: number;
  monthly_budget_usd: number | null;
  monthly_budget_remaining_usd: number | null;
  over_monthly_budget: boolean;
  low_priority_accounts_paused: number;
}

interface Observability {
  ingestion_health: SourceIngestionHealth[];
  job_queue: JobQueueHealth;
  ai_cost: AiCostSummary;
  x_cost: XCostSummary;
}

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

const usd = (n: number) => `$${n.toFixed(2)}`;


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
      })
      .catch((err) => toast("danger", err instanceof Error ? err.message : "Failed to load observability data"));
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
        <p className="state-note">Loading…</p>
      </main>
    );
  }

  const jobs = data.job_queue.counts_by_status;
  const oldest = data.job_queue.oldest_pending_age_seconds;
  const ai = data.ai_cost;
  const x = data.x_cost;
  // Problems first: tripped breakers, then most failures in 24h.
  const health = [...data.ingestion_health].sort(
    (a, b) => Number(b.circuit_breaker_tripped) - Number(a.circuit_breaker_tripped) || b.failure_count_24h - a.failure_count_24h
  );

  return (
    <main>
      {header}

      <div className="tile-grid">
        <StatTile href="#ingestion" label="Sources tripped" value={health.filter((h) => h.circuit_breaker_tripped).length} note={`${health.length} sources`} tone={health.some((h) => h.circuit_breaker_tripped) ? "danger" : "ok"} />
        <StatTile href="#jobs" label="Jobs pending" value={jobs.PENDING ?? 0} note={oldest !== null ? `oldest waiting ${duration(oldest)}` : "queue empty"} tone={(jobs.FAILED ?? 0) > 0 ? "danger" : oldest !== null && oldest > STALE_QUEUE_SECONDS ? "warn" : "ok"} />
        <StatTile href="#ai-cost" label="AI spend (month)" value={usd(ai.month_to_date_cost_usd)} note={ai.monthly_budget_usd !== null ? `of ${usd(ai.monthly_budget_usd)}` : "no budget set"} tone={ai.over_monthly_budget ? "danger" : "ok"} />
        <StatTile href="#x" label="X spend (month)" value={usd(x.month_to_date_cost_usd)} note={x.monthly_budget_usd !== null ? `of ${usd(x.monthly_budget_usd)}` : "no budget set"} tone={x.over_monthly_budget ? "danger" : "ok"} />
      </div>

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
        {ai.over_monthly_budget ? <p role="alert">Over monthly budget — paid AI is paused.</p> : null}
        <BudgetBar spent={ai.month_to_date_cost_usd} budget={ai.monthly_budget_usd} />
        <p className="card__meta">
          Month-to-date {usd(ai.month_to_date_cost_usd)} · today {usd(ai.today_cost_usd)}
          {ai.monthly_budget_remaining_usd !== null ? ` · ${usd(ai.monthly_budget_remaining_usd)} remaining` : ""}
          {ai.daily_alert_usd !== null ? ` · daily alert at ${usd(ai.daily_alert_usd)}` : ""}
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
