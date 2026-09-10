"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

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

export default function ObservabilityPage() {
  const router = useRouter();
  const [data, setData] = useState<Observability | null>(null);
  const [xAccounts, setXAccounts] = useState<XAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pausingSourceId, setPausingSourceId] = useState<string | null>(null);

  const loadXAccounts = () => {
    const token = getToken();
    if (!token) return;
    fetch(`${apiUrl()}/v1/admin/x-accounts`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Failed to load X accounts"))))
      .then((body: XAccount[]) => setXAccounts(body))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load X accounts"));
  };

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/observability`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            clearSession();
            router.replace("/login");
          }
          throw new Error("Failed to load observability data");
        }
        return response.json();
      })
      .then((body: Observability) => setData(body))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load observability data"));
    loadXAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function togglePause(account: XAccount) {
    const token = getToken();
    setPausingSourceId(account.source_id);
    setError(null);
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
      loadXAccounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update X account");
    } finally {
      setPausingSourceId(null);
    }
  }

  return (
    <main>
      <h1>Observability</h1>
      {error ? <p role="alert">{error}</p> : null}
      {data === null ? (
        <p>Loading…</p>
      ) : (
        <>
          <section>
            <h2>Ingestion health (last 24h)</h2>
            {data.ingestion_health.length === 0 ? (
              <p>No sources configured.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Success (24h)</th>
                    <th>Failure (24h)</th>
                    <th>Fail count</th>
                    <th>Circuit breaker</th>
                    <th>Last success</th>
                    <th>Last error</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ingestion_health.map((row) => (
                    <tr key={row.source_id}>
                      <td>{row.source_name}</td>
                      <td>{row.success_count_24h}</td>
                      <td>{row.failure_count_24h}</td>
                      <td>{row.fail_count}</td>
                      <td>
                        <span className={`status-pill ${row.circuit_breaker_tripped ? "status-pill--danger" : "status-pill--ok"}`}>
                          {row.circuit_breaker_tripped ? "Tripped" : "OK"}
                        </span>
                      </td>
                      <td>{row.last_success_at ? new Date(row.last_success_at).toLocaleString() : "—"}</td>
                      <td>{row.last_error_at ? new Date(row.last_error_at).toLocaleString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section>
            <h2>Job queue</h2>
            <ul>
              {Object.entries(data.job_queue.counts_by_status).map(([status, count]) => (
                <li key={status}>
                  {status}: {count}
                </li>
              ))}
            </ul>
            <p>
              Oldest pending job age:{" "}
              {data.job_queue.oldest_pending_age_seconds !== null
                ? `${Math.round(data.job_queue.oldest_pending_age_seconds)}s`
                : "n/a (queue empty)"}
            </p>
          </section>

          <section>
            <h2>AI cost vs. budget</h2>
            <ul>
              <li>Month-to-date spend: ${data.ai_cost.month_to_date_cost_usd.toFixed(2)}</li>
              <li>
                Monthly budget:{" "}
                {data.ai_cost.monthly_budget_usd !== null ? `$${data.ai_cost.monthly_budget_usd.toFixed(2)}` : "not set"}
              </li>
              <li>
                Remaining budget:{" "}
                {data.ai_cost.monthly_budget_remaining_usd !== null
                  ? `$${data.ai_cost.monthly_budget_remaining_usd.toFixed(2)}`
                  : "n/a"}
              </li>
              <li>Today&apos;s spend: ${data.ai_cost.today_cost_usd.toFixed(2)}</li>
              {data.ai_cost.over_monthly_budget ? <li role="alert">Over monthly budget</li> : null}
            </ul>
            <table>
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
                {data.ai_cost.rows.map((row) => (
                  <tr key={`${row.day}-${row.task}`}>
                    <td>{row.day}</td>
                    <td>{row.task}</td>
                    <td>{row.tokens_in}</td>
                    <td>{row.tokens_out}</td>
                    <td>${row.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <h2>X account health &amp; budget (X4)</h2>
            <ul>
              <li>Month-to-date X API spend: ${data.x_cost.month_to_date_cost_usd.toFixed(2)}</li>
              <li>
                Monthly budget:{" "}
                {data.x_cost.monthly_budget_usd !== null ? `$${data.x_cost.monthly_budget_usd.toFixed(2)}` : "not set"}
              </li>
              <li>
                Remaining budget:{" "}
                {data.x_cost.monthly_budget_remaining_usd !== null
                  ? `$${data.x_cost.monthly_budget_remaining_usd.toFixed(2)}`
                  : "n/a"}
              </li>
              {data.x_cost.over_monthly_budget ? (
                <li role="alert">
                  Over monthly budget — {data.x_cost.low_priority_accounts_paused} low-priority account(s) paused
                </li>
              ) : null}
            </ul>
            {xAccounts === null ? (
              <p>Loading X accounts…</p>
            ) : xAccounts.length === 0 ? (
              <p>No X accounts configured.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Handle</th>
                    <th>Rights status</th>
                    <th>Active</th>
                    <th>Budget class</th>
                    <th>Budget paused</th>
                    <th>since_id</th>
                    <th>Fail count</th>
                    <th>Errors (24h)</th>
                    <th>MTD cost</th>
                    <th>Last success</th>
                    <th>Last error</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {xAccounts.map((account) => (
                    <tr key={account.id}>
                      <td>{account.handle}</td>
                      <td>{account.rights_status}</td>
                      <td>
                        <span className={`status-pill ${account.active ? "status-pill--ok" : "status-pill--warn"}`}>
                          {account.active ? "Active" : "Paused"}
                        </span>
                      </td>
                      <td>{account.budget_class ?? "—"}</td>
                      <td>{account.budget_paused ? <span className="status-pill status-pill--warn">Budget-paused</span> : "—"}</td>
                      <td>{account.since_id ?? "—"}</td>
                      <td>{account.fail_count}{account.circuit_breaker_tripped ? " (TRIPPED)" : ""}</td>
                      <td>{account.recent_error_count_24h}</td>
                      <td>${account.month_to_date_cost_usd.toFixed(2)}</td>
                      <td>{account.last_success_at ? new Date(account.last_success_at).toLocaleString() : "—"}</td>
                      <td>{account.last_error_at ? new Date(account.last_error_at).toLocaleString() : "—"}</td>
                      <td>
                        <button
                          type="button"
                          disabled={pausingSourceId === account.source_id}
                          onClick={() => togglePause(account)}
                        >
                          {account.active ? "Pause" : "Resume"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}
