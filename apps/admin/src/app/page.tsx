"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { components } from "@teluguvarta/contracts";

import { EmptyState, PageHeader, StatTile, Tone } from "@/components/ui";
import { BUDGET_MODE, type BudgetMode, budgetModeMessage, usd } from "@/lib/aiBudget";
import { apiUrl, clearSession, getRole, getToken } from "@/lib/auth";
import { captureException } from "@/lib/errorTracking";
import { STALE_QUEUE_SECONDS, age, duration } from "@/lib/time";

interface SourceRow {
  rights_status: string;
  active: boolean;
  fail_count: number;
}

interface Observability {
  ingestion_health: { circuit_breaker_tripped: boolean; source_name: string }[];
  job_queue: { counts_by_status: Record<string, number>; oldest_pending_age_seconds: number | null };
  ai_cost: {
    month_to_date_cost_usd: number;
    today_cost_usd: number;
    daily_alert_usd: number | null;
    monthly_budget_usd: number | null;
    monthly_hard_cap_usd: number | null;
    mode: BudgetMode;
  };
}

interface Data {
  sources: SourceRow[];
  obs: Observability;
  // Review 2026-09-30 R5: stage counts and the oldest wait at each stage.
  pipeline: components["schemas"]["PipelineStatusOut"];
}

export default function Home() {
  const router = useRouter();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setRole(getRole());
    const get = (path: string) =>
      fetch(`${apiUrl()}/v1/admin${path}`, { headers: { Authorization: `Bearer ${token}` } }).then((response) => {
        if (response.status === 401) {
          clearSession();
          router.replace("/login");
          return Promise.reject(new Error("Session expired"));
        }
        return response.ok ? response.json() : Promise.reject(new Error(`Failed to load ${path}`));
      });
    Promise.all([get("/sources"), get("/observability"), get("/pipeline")])
      .then(([sources, obs, pipeline]) => setData({ sources, obs, pipeline }))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"));
  }, [router]);

  if (error) {
    return (
      <main>
        <PageHeader title="Dashboard" />
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!data) {
    return (
      <main>
        <p className="state-note">Loading…</p>
      </main>
    );
  }

  const { sources, obs, pipeline } = data;
  const reviewCount = pipeline.review_pending;
  const aiRetrying = pipeline.ai_work.reduce((sum, w) => sum + w.retrying, 0);
  const aiExhausted = pipeline.ai_work.reduce((sum, w) => sum + w.exhausted, 0);
  const needsRights = sources.filter((s) => s.rights_status === "DISABLED").length;
  const activeCount = sources.filter((s) => s.active).length;
  const tripped = obs.ingestion_health.filter((h) => h.circuit_breaker_tripped);
  const failing = sources.filter((s) => s.fail_count > 0).length;
  const jobs = obs.job_queue.counts_by_status;
  const failedJobs = jobs.FAILED ?? 0;
  const { ai_cost: ai } = obs;

  const attention: { key: string; href: string; node: ReactNode; tone: "danger" | "warn" }[] = [];
  const budgetMessage = budgetModeMessage(ai.mode, ai.monthly_budget_usd, ai.monthly_hard_cap_usd);
  if (budgetMessage) {
    attention.push({ key: "budget", href: "/observability#ai-cost", tone: ai.mode === "PAID_STOPPED" ? "danger" : "warn", node: budgetMessage });
  }
  if (tripped.length > 0) {
    attention.push({
      key: "breaker",
      href: "/observability",
      tone: "danger",
      node: `${tripped.length} source${tripped.length > 1 ? "s" : ""} stopped fetching (circuit breaker): ${tripped.map((t) => t.source_name).join(", ")}.`
    });
  }
  if (failedJobs > 0) {
    attention.push({ key: "jobs", href: "/observability", tone: "warn", node: `${failedJobs} failed job${failedJobs > 1 ? "s" : ""}.` });
  }
  const oldest = obs.job_queue.oldest_pending_age_seconds;
  const staleQueue = oldest !== null && oldest > STALE_QUEUE_SECONDS;
  if (staleQueue) {
    attention.push({
      key: "stale-queue",
      href: "/observability#jobs",
      tone: "danger",
      node: `Jobs have been waiting ${duration(oldest)} — the worker may not be running.`
    });
  }
  if (reviewCount > 0) {
    attention.push({ key: "review", href: "/review", tone: "warn", node: `${reviewCount} stor${reviewCount > 1 ? "ies" : "y"} waiting for human review.` });
  }
  if (pipeline.reports_open > 0) {
    const oldestReport = pipeline.reports_oldest_open_at ? `, oldest ${age(pipeline.reports_oldest_open_at)}` : "";
    attention.push({
      key: "reports",
      href: "/reports",
      tone: "warn",
      node: `${pipeline.reports_open} open reader report${pipeline.reports_open > 1 ? "s" : ""}${oldestReport}.`
    });
  }
  if (aiExhausted > 0) {
    attention.push({
      key: "ai-exhausted",
      href: "/review",
      tone: "warn",
      node: `${aiExhausted} stor${aiExhausted > 1 ? "ies have" : "y has"} used up automatic AI retries and need${aiExhausted > 1 ? "" : "s"} an editor.`
    });
  }
  if (needsRights > 0) {
    attention.push({ key: "rights", href: "/sources", tone: "warn", node: `${needsRights} source${needsRights > 1 ? "s" : ""} need a rights review before they can ingest.` });
  }

  const budgetNote = [
    ai.monthly_budget_usd === null ? "no budget set" : `of ${usd(ai.monthly_budget_usd)} budget`,
    BUDGET_MODE[ai.mode].label.toLowerCase(),
  ].join(" · ");

  return (
    <main>
      <PageHeader title="Dashboard" subtitle={role ? `Signed in as ${role}` : undefined} />

      <h2>Needs attention</h2>
      {attention.length === 0 ? (
        <EmptyState title="All clear" hint="Nothing is failing and nothing is waiting on you." />
      ) : (
        <ul className="attention-list">
          {attention.map((a) => (
            <li key={a.key} role="alert" className={a.tone === "warn" ? "editorial-status" : undefined}>
              <Link href={a.href}>{a.node}</Link>
            </li>
          ))}
        </ul>
      )}

      <h2>Pipeline</h2>
      <div className="tile-grid">
        <StatTile href="/sources" label="Active sources" value={activeCount} note={`${sources.length} total · ${failing} failing`} tone={failing > 0 ? "warn" : "ok"} />
        <StatTile href="/sources" label="Need rights review" value={needsRights} tone={(needsRights > 0 ? "warn" : "ok") as Tone} />
        <StatTile href="/review" label="Review queue" value={reviewCount} note={pipeline.review_oldest_at ? `oldest waiting ${age(pipeline.review_oldest_at)}` : "stories waiting"} tone={reviewCount > 0 ? "warn" : "ok"} />
        <StatTile href="/review" label="Published (24h)" value={pipeline.published_24h} note={`${(pipeline.stories_by_status.PUBLISHED ?? 0) + (pipeline.stories_by_status.UPDATED ?? 0)} live in total`} />
        <StatTile
          href="/review"
          label="Live in English only"
          value={pipeline.telugu_missing}
          note={pipeline.telugu_missing_oldest_published_at ? `no passed Telugu · oldest ${age(pipeline.telugu_missing_oldest_published_at)} · ${pipeline.telugu_failed_qa} failed QA` : "every live story has Telugu"}
          tone={pipeline.telugu_missing > 0 ? "warn" : "ok"}
        />
        <StatTile href="/review" label="AI retries" value={aiRetrying} note={`${aiExhausted} out of retries`} tone={aiExhausted > 0 ? "warn" : "ok"} />
        <StatTile
          href="/observability"
          label="Jobs pending"
          value={jobs.PENDING ?? 0}
          note={oldest !== null ? `oldest waiting ${duration(oldest)}` : `${failedJobs} failed`}
          tone={failedJobs > 0 || staleQueue ? "danger" : "ok"}
        />
        <StatTile href="/costs" label="AI spend today (est.)" value={usd(ai.today_cost_usd)} note={`since 00:00 UTC${ai.daily_alert_usd !== null ? ` · alert at ${usd(ai.daily_alert_usd)}` : ""}`} tone={ai.daily_alert_usd !== null && ai.today_cost_usd >= ai.daily_alert_usd ? "warn" : "ok"} />
        <StatTile href="/costs" label="AI spend this month (est.)" value={usd(ai.month_to_date_cost_usd)} note={budgetNote} tone={BUDGET_MODE[ai.mode].tone} />
      </div>

      {process.env.NODE_ENV !== "production" ? (
        <section>
          <h2>Debug</h2>
          <button
            type="button"
            onClick={() => captureException(new Error("T18 debug throw — deliberate, for error-tracking verification"), { role: role ?? "" })}
          >
            Debug: throw error
          </button>
        </section>
      ) : null}
    </main>
  );
}
