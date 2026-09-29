"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { EmptyState, PageHeader, StatTile, Tone } from "@/components/ui";
import { apiUrl, clearSession, getRole, getToken } from "@/lib/auth";
import { captureException } from "@/lib/errorTracking";
import { STALE_QUEUE_SECONDS, duration } from "@/lib/time";

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
    monthly_budget_usd: number | null;
    over_monthly_budget: boolean;
  };
}

interface Data {
  sources: SourceRow[];
  reviewCount: number;
  obs: Observability;
}

const usd = (n: number) => `$${n.toFixed(2)}`;

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
    Promise.all([get("/sources"), get("/review-queue"), get("/observability")])
      .then(([sources, review, obs]) => setData({ sources, reviewCount: (review as unknown[]).length, obs }))
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

  const { sources, reviewCount, obs } = data;
  const needsRights = sources.filter((s) => s.rights_status === "DISABLED").length;
  const activeCount = sources.filter((s) => s.active).length;
  const tripped = obs.ingestion_health.filter((h) => h.circuit_breaker_tripped);
  const failing = sources.filter((s) => s.fail_count > 0).length;
  const jobs = obs.job_queue.counts_by_status;
  const failedJobs = jobs.FAILED ?? 0;
  const { ai_cost: ai } = obs;

  const attention: { key: string; href: string; node: ReactNode; tone: "danger" | "warn" }[] = [];
  if (ai.over_monthly_budget) {
    attention.push({ key: "budget", href: "/observability", tone: "danger", node: "AI monthly budget exceeded — paid AI is paused." });
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
  if (needsRights > 0) {
    attention.push({ key: "rights", href: "/sources", tone: "warn", node: `${needsRights} source${needsRights > 1 ? "s" : ""} need a rights review before they can ingest.` });
  }

  const budgetNote = ai.monthly_budget_usd === null ? "No budget set" : `of ${usd(ai.monthly_budget_usd)} budget`;

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
        <StatTile href="/review" label="Review queue" value={reviewCount} note="stories waiting" tone={reviewCount > 0 ? "warn" : "ok"} />
        <StatTile
          href="/observability"
          label="Jobs pending"
          value={jobs.PENDING ?? 0}
          note={oldest !== null ? `oldest waiting ${duration(oldest)}` : `${failedJobs} failed`}
          tone={failedJobs > 0 || staleQueue ? "danger" : "ok"}
        />
        <StatTile href="/observability" label="AI spend (month)" value={usd(ai.month_to_date_cost_usd)} note={budgetNote} tone={ai.over_monthly_budget ? "danger" : "ok"} />
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
