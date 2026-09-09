"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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

interface Observability {
  ingestion_health: SourceIngestionHealth[];
  job_queue: JobQueueHealth;
  ai_cost: AiCostSummary;
}

export default function ObservabilityPage() {
  const router = useRouter();
  const [data, setData] = useState<Observability | null>(null);
  const [error, setError] = useState<string | null>(null);

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
  }, [router]);

  return (
    <main>
      <h1>Observability</h1>
      <p>
        <Link href="/">Back to admin home</Link>
      </p>
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
                      <td>{row.circuit_breaker_tripped ? "TRIPPED" : "ok"}</td>
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
        </>
      )}
    </main>
  );
}
