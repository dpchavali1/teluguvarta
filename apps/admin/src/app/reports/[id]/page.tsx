"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { components } from "@teluguvarta/contracts";

import { Badge, Field, PageHeader, useToast } from "@/components/ui";
import {
  CATEGORY_LABELS,
  RESOLUTIONS,
  SessionExpired,
  adminFetch,
  resolutionLabel,
  type ReaderReport,
  type ReaderReportList,
  type Resolution,
} from "@/lib/reports";
import { ago } from "@/lib/time";

// ADR-029: one reader report next to the story it is about. A report never
// changes the story: the editor corrects or retracts on the review page,
// then closes the report with a link to what they did.
type StoryDetail = components["schemas"]["AdminStoryDetailOut"];

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [report, setReport] = useState<ReaderReport | null>(null);
  const [story, setStory] = useState<StoryDetail | null>(null);
  const [related, setRelated] = useState<ReaderReport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resolution, setResolution] = useState<Resolution>("NO_CHANGE");
  const [correctionId, setCorrectionId] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fail = useCallback(
    (err: unknown, fallback: string) => {
      if (err instanceof SessionExpired) router.replace("/login");
      else setError(err instanceof Error ? err.message : fallback);
    },
    [router],
  );

  const load = useCallback(async () => {
    try {
      const loaded = await adminFetch<ReaderReport>(`/v1/admin/reports/${id}`, {}, "Failed to load report");
      setReport(loaded);
      const [storyDetail, others] = await Promise.all([
        adminFetch<StoryDetail>(`/v1/admin/stories/${loaded.story_id}`, {}, "Failed to load story"),
        adminFetch<ReaderReportList>(`/v1/admin/reports?status=ALL&story_id=${loaded.story_id}&limit=20`, {}, "Failed to load related reports"),
      ]);
      setStory(storyDetail);
      setRelated(others.items.filter((r) => r.id !== loaded.id));
      setError(null);
    } catch (err) {
      fail(err, "Failed to load report");
    }
  }, [id, fail]);

  useEffect(() => {
    void load();
  }, [load]);

  async function resolve(event: React.FormEvent) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const body = { resolution, note: note.trim() || null, correction_id: resolution === "CORRECTED" ? correctionId || null : null };
      const updated = await adminFetch<ReaderReport>(
        `/v1/admin/reports/${id}/resolve`,
        { method: "POST", body: JSON.stringify(body) },
        "Couldn't close the report",
      );
      setReport(updated);
      toast("ok", `Report closed: ${resolutionLabel(updated.resolution)}.`);
    } catch (err) {
      if (err instanceof SessionExpired) router.replace("/login");
      else toast("danger", err instanceof Error ? err.message : "Couldn't close the report");
    } finally {
      setSubmitting(false);
    }
  }

  const header = (
    <PageHeader
      title="Reader report"
      subtitle={report ? `${CATEGORY_LABELS[report.category]} · received ${ago(report.created_at)}` : undefined}
      actions={<Link href="/reports">All reports</Link>}
    />
  );

  if (!report) {
    return (
      <main>
        {header}
        {error ? <p role="alert">{error}</p> : <p className="state-note">Loading…</p>}
      </main>
    );
  }

  const help = RESOLUTIONS.find((r) => r.value === resolution)?.help;
  const corrections = story?.corrections ?? [];
  const blocked =
    (resolution === "CORRECTED" && !correctionId) || (resolution === "RETRACTED" && story?.status !== "RETRACTED");

  return (
    <main>
      {header}
      {error ? <p role="alert">{error}</p> : null}

      <section aria-labelledby="report-heading">
        <h2 id="report-heading">What the reader said</h2>
        {report.description ? (
          <blockquote className="card" style={{ whiteSpace: "pre-wrap" }}>{report.description}</blockquote>
        ) : (
          <p className="state-note">
            {report.description_purged_at ? `Text erased ${ago(report.description_purged_at)} under the retention rule.` : "The reader left no text."}
          </p>
        )}
        <p className="card__meta">
          Reading in {report.language === "te" ? "Telugu" : report.language === "en" ? "English" : "unknown language"} on{" "}
          {report.platform ?? "unknown platform"} · sender <code>{report.sender}</code> (same code = same sender, same UTC day)
          {report.repeat_count > 0 ? ` · sent ${report.repeat_count + 1} times` : ""}
        </p>
      </section>

      <section aria-labelledby="story-heading">
        <h2 id="story-heading">The story</h2>
        <p>
          <Badge>{report.story_status}</Badge>{" "}
          <Link href={`/review/${report.story_id}`}>Open on the review page to correct or retract</Link>
        </p>
        {story ? (
          <>
            {(["en", "te"] as const).map((language) => {
              const variant = story.variants?.[language];
              return variant ? (
                <div key={language} className="card" lang={language}>
                  <strong>{variant.headline}</strong>
                  <p>{variant.summary}</p>
                  <p className="card__meta">
                    {language === "en" ? "English" : "Telugu"} · QA {variant.qa_status.toLowerCase()}
                  </p>
                </div>
              ) : (
                <p key={language} className="state-note">No {language === "en" ? "English" : "Telugu"} version.</p>
              );
            })}
            {story.sources && story.sources.length > 0 ? (
              <ul>
                {story.sources.map((source) => (
                  <li key={source.url}>
                    {source.source_name}:{" "}
                    <a href={source.url} target="_blank" rel="noreferrer noopener">
                      {source.title ?? source.url}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : (
          <p className="state-note">Loading story…</p>
        )}
      </section>

      {related.length > 0 ? (
        <section aria-labelledby="related-heading">
          <h2 id="related-heading">Other reports on this story</h2>
          <ul>
            {related.map((r) => (
              <li key={r.id}>
                <Link href={`/reports/${r.id}`}>
                  {CATEGORY_LABELS[r.category]} · {ago(r.created_at)}
                </Link>{" "}
                · {r.status === "OPEN" ? "open" : resolutionLabel(r.resolution)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="resolve-heading">
        <h2 id="resolve-heading">Outcome</h2>
        {report.status !== "OPEN" ? (
          <p>
            <Badge tone={report.status === "RESOLVED" ? "ok" : "neutral"}>{resolutionLabel(report.resolution)}</Badge>{" "}
            by {report.resolved_by_email ?? "a removed account"} {report.resolved_at ? ago(report.resolved_at) : ""}
            {report.resolution_note ? ` — ${report.resolution_note}` : ""}
          </p>
        ) : (
          <form onSubmit={resolve}>
            <Field label="Resolution" htmlFor="resolution" hint={help}>
              <select id="resolution" value={resolution} onChange={(e) => setResolution(e.target.value as Resolution)}>
                {RESOLUTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </Field>
            {resolution === "CORRECTED" ? (
              <Field
                label="Correction"
                htmlFor="correction"
                hint={corrections.length === 0 ? "No corrections on this story yet — make one on the review page first." : undefined}
              >
                <select id="correction" value={correctionId} onChange={(e) => setCorrectionId(e.target.value)}>
                  <option value="">Choose…</option>
                  {corrections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {ago(c.created_at)}: {c.reason}
                    </option>
                  ))}
                </select>
              </Field>
            ) : null}
            {resolution === "RETRACTED" && story?.status !== "RETRACTED" ? (
              <p className="field__hint">The story is {story?.status ?? "…"}; retract it on the review page first.</p>
            ) : null}
            <Field label="Note (optional, kept in the audit log)" htmlFor="note">
              <textarea id="note" value={note} maxLength={1000} rows={3} onChange={(e) => setNote(e.target.value)} />
            </Field>
            <button type="submit" disabled={submitting || blocked}>
              {submitting ? "Closing…" : "Close report"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
