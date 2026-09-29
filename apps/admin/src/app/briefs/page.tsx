"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, PageHeader } from "@/components/ui";
import { apiUrl, clearSession, getToken } from "@/lib/auth";
import { age } from "@/lib/time";

type AutoBrief = components["schemas"]["AdminAutoBriefOut"];
type KillSwitches = components["schemas"]["KillSwitchesOut"];

// ADR-019: the after-publish check for the link-first brief lane. There is no
// pre-publish sampling; retract/correct live on the story page.
export default function AutoBriefsPage() {
  const router = useRouter();
  const [briefs, setBriefs] = useState<AutoBrief[] | null>(null);
  const [switches, setSwitches] = useState<KillSwitches | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setError(null);
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    const get = (path: string) =>
      fetch(`${apiUrl()}${path}`, { headers: { Authorization: `Bearer ${token}` } }).then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            clearSession();
            router.replace("/login");
          }
          throw new Error("Failed to load auto-published briefs");
        }
        return response.json();
      });
    Promise.all([get("/v1/admin/briefs/recent"), get("/v1/admin/kill-switches")])
      .then(([rows, flags]: [AutoBrief[], KillSwitches]) => {
        setBriefs(rows);
        setSwitches(flags);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load auto-published briefs"));
  }, [router, revision]);

  const laneState = switches
    ? switches.auto_publish_briefs
      ? `Lane on · ${switches.briefs_published_today} of ${switches.auto_publish_briefs_daily_cap} used today (resets at midnight New York time)`
      : "Lane off (AUTO_PUBLISH_BRIEFS=false)"
    : undefined;

  return (
    <main>
      <PageHeader title="Auto-published briefs (24h)" subtitle={laneState} />
      {error ? <div role="alert"><p>{error}</p><button onClick={() => setRevision((value) => value + 1)}>Try again</button></div> : null}
      {briefs === null && !error ? (
        <p className="state-note">Loading…</p>
      ) : briefs?.length === 0 ? (
        <EmptyState title="No briefs auto-published in the last 24 hours" hint="Stories the brief lane publishes show up here for a check after the fact." />
      ) : (
        <div className="table-scroll"><table>
          <thead>
            <tr>
              <th>Brief</th>
              <th className="col-wide-only">Source title</th>
              <th className="col-wide-only">Matched in title</th>
              <th>Status</th>
              <th>Approved</th>
            </tr>
          </thead>
          <tbody>
            {(briefs ?? []).map((brief) => (
              <tr key={brief.story_id}>
                <td>
                  <Link href={`/review/${brief.story_id}`}>{brief.headline ?? "Untitled brief"}</Link>
                  {brief.summary ? <span className="reason-help">{brief.summary}</span> : null}
                </td>
                <td className="col-wide-only">{brief.source_titles?.join(" · ") || "No source linked"}</td>
                <td className="col-wide-only">{brief.matched_tokens?.join(", ") || "—"}</td>
                <td><Badge tone={brief.status === "PUBLISHED" || brief.status === "SCHEDULED" ? "ok" : "warn"}>{brief.status}</Badge></td>
                <td title={new Date(brief.approved_at).toLocaleString()}>{age(brief.approved_at)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </main>
  );
}
