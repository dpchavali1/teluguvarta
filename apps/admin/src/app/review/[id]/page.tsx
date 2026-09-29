"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Badge, EmptyState, Field, PageHeader, useToast } from "@/components/ui";
import { apiUrl, clearSession, getToken } from "@/lib/auth";
import { reasonHelp, reasonTone } from "@/lib/reviewReasons";

interface StoryVariant {
  language: "en" | "te";
  headline: string;
  summary: string;
  why_matters: string | null;
  qa_status: string;
}

interface StorySource {
  role: "PRIMARY" | "SUPPORTING";
  url: string;
  title: string | null;
  published_at: string | null;
  source_name: string;
  source_rights_status: string;
}

// Same always-human-reviewed set as the review queue list page's
// DANGER_REASONS — a sensitivity here should read with the same urgency as
// the reason pill a reviewer already saw on the queue.
const ALWAYS_REVIEWED_SENSITIVITIES = new Set(["IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]);

// ADR-014 EditorialStatus: same three states/register web's StoryCard notice
// uses (updated/retracted/under review), so a moderator sees the identical
// signal a reader would — tone here follows the ADR's color-discipline rule
// (green/amber/red only) rather than web's current indigo "updated" notice,
// which is a pre-existing drift from that rule, not a pattern to match.
const STATUS_NOTICE: Record<string, { text: string; tone: "warn" | "danger" } | undefined> = {
  REVIEW_REQUIRED: { text: "Under review — not visible to readers.", tone: "warn" },
  UPDATED: { text: "Updated / corrected since first publish.", tone: "warn" },
  CORRECTION_PENDING: { text: "Correction pending — not yet applied.", tone: "warn" },
  RETRACTED: { text: "Retracted — no longer live.", tone: "danger" }
};

interface Correction {
  id: string;
  reason: string;
  old_text_hash: string;
  new_text_hash: string;
  created_at: string;
}

interface StoryDetail {
  id: string;
  canonical_slug: string;
  status: string;
  sensitivity: string;
  importance: number;
  published_at: string | null;
  variants: Record<string, StoryVariant>;
  sources: StorySource[];
  review_task: { reason: string; status: string } | null;
  corrections: Correction[];
}

async function postAction(storyId: string, action: string, body: Record<string, unknown>): Promise<void> {
  const token = getToken();
  const response = await fetch(`${apiUrl()}/v1/admin/stories/${storyId}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(errorBody?.error?.message ?? `${action} failed`);
  }
}

export default function StoryReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const storyId = params.id;
  const toast = useToast();

  const [story, setStory] = useState<StoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [archive, setArchive] = useState(false);
  const [correctedHeadline, setCorrectedHeadline] = useState("");
  const [correctedSummary, setCorrectedSummary] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Design-review fix: approve/reject on an always-human-reviewed category
  // (immigration/legal/financial/breaking/obituary-accusation) previously
  // required no more friction, and no recorded reason, than any other
  // story — no audit trail for the highest-stakes decision in the product.
  const [pendingAction, setPendingAction] = useState<"approve" | "reject" | null>(null);
  // Design-review fix: correcting an already-published always-reviewed
  // story (immigration/legal/financial/breaking) went through on the same
  // one-click submit as a typo fix to a routine story — no confirm step
  // matching the one approve/reject already have for this category.
  const [pendingCorrect, setPendingCorrect] = useState(false);

  const load = useCallback(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/stories/${storyId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            clearSession();
            router.replace("/login");
          }
          throw new Error("Failed to load story");
        }
        return response.json();
      })
      .then((body: StoryDetail) => {
        setStory(body);
        setCorrectedHeadline(body.variants.en?.headline ?? "");
        setCorrectedSummary(body.variants.en?.summary ?? "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load story"));
  }, [router, storyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAction(action: "approve" | "reject" | "retract") {
    setSubmitting(true);
    setError(null);
    setPendingAction(null);
    try {
      const body = action === "reject" ? { reason: reason || null, archive } : { reason: reason || null };
      await postAction(storyId, action, body);
      setReason("");
      if (action === "retract") {
        toast("ok", "Story retracted.");
        load();
      } else {
        // Straight back to the queue so triage is one decision after another.
        toast("ok", action === "approve" ? "Approved." : archive ? "Rejected and archived." : "Rejected — sent back to draft.");
        router.push("/review");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitCorrection() {
    setSubmitting(true);
    setError(null);
    setPendingCorrect(false);
    try {
      const en = story?.variants.en;
      const body: Record<string, unknown> = { reason };
      if (correctedHeadline !== en?.headline) body.headline = correctedHeadline;
      if (correctedSummary !== en?.summary) body.summary = correctedSummary;
      await postAction(storyId, "correct", body);
      setReason("");
      toast("ok", "Correction submitted.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Correction failed");
    } finally {
      setSubmitting(false);
    }
  }

  function handleCorrectSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (isAlwaysReviewed && !pendingCorrect) {
      setPendingCorrect(true);
      return;
    }
    submitCorrection();
  }

  if (error && !story) {
    return (
      <main>
        <p role="alert">{error}</p>
        <Link href="/review">Back to review queue</Link>
      </main>
    );
  }

  if (!story) {
    return (
      <main>
        <p className="state-note">Loading…</p>
      </main>
    );
  }

  const en = story.variants.en;
  const te = story.variants.te;
  const isAlwaysReviewed = ALWAYS_REVIEWED_SENSITIVITIES.has(story.sensitivity);
  const reasonRequired = isAlwaysReviewed && reason.trim().length === 0;
  const statusNotice = STATUS_NOTICE[story.status];
  const heldReasons = story.review_task ? story.review_task.reason.split(",").map((r) => r.trim()) : [];

  return (
    <main>
      <p>
        <Link href="/review">← Back to review queue</Link>
      </p>
      <PageHeader
        title={en?.headline ?? story.canonical_slug}
        subtitle={`Importance ${story.importance.toFixed(2)}`}
        actions={
          <span className="pill-row">
            <Badge tone={statusNotice?.tone ?? "neutral"}>{story.status}</Badge>
            <Badge tone={isAlwaysReviewed ? "danger" : "warn"}>{story.sensitivity}</Badge>
          </span>
        }
      />
      {statusNotice ? (
        <p className={`editorial-status editorial-status--${statusNotice.tone}`} role="status">
          {statusNotice.text}
        </p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}

      <div className="detail-layout">
        <div>
          {heldReasons.length > 0 ? (
            <section>
              <h2>Why this is held</h2>
              <ul className="reason-list">
                {heldReasons.map((r) => (
                  <li key={r}>
                    <Badge tone={reasonTone(r)}>{r.replace(/_/g, " ").toLowerCase()}</Badge> {reasonHelp(r)}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section>
            <h2>AI draft</h2>
            {en || te ? (
              <div className="variant-grid">
                {en ? (
                  <div className="card">
                    <h3>English</h3>
                    <p className="variant-headline">{en.headline}</p>
                    <p>{en.summary}</p>
                    {en.why_matters ? (
                      <p>
                        <em>Why it matters:</em> {en.why_matters}
                      </p>
                    ) : null}
                    <Badge tone={en.qa_status === "PASSED" ? "ok" : en.qa_status === "FAILED" ? "danger" : "warn"}>QA {en.qa_status}</Badge>
                  </div>
                ) : null}
                {te ? (
                  <div className="card" lang="te">
                    <h3>Telugu</h3>
                    <p className="variant-headline">{te.headline}</p>
                    <p>{te.summary}</p>
                    {te.why_matters ? (
                      <p>
                        <em>Why it matters:</em> {te.why_matters}
                      </p>
                    ) : null}
                    <span lang="en">
                      <Badge tone={te.qa_status === "PASSED" ? "ok" : te.qa_status === "FAILED" ? "danger" : "warn"}>QA {te.qa_status}</Badge>
                    </span>
                  </div>
                ) : null}
              </div>
            ) : (
              <EmptyState title="No draft yet" hint="No English or Telugu variant has been written for this story." />
            )}
          </section>

          <section>
            <h2>Sources ({story.sources.length})</h2>
            <ul className="source-list">
              {story.sources.map((source) => (
                <li key={source.url}>
                  <span className="pill-row">
                    <Badge>{source.role}</Badge>
                    <Badge tone={source.source_rights_status === "DISABLED" ? "danger" : "ok"}>{source.source_rights_status}</Badge>
                  </span>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.title ?? source.url}
                  </a>
                  <span className="card__meta">{source.source_name}</span>
                </li>
              ))}
            </ul>
          </section>

          {story.status === "PUBLISHED" || story.status === "UPDATED" ? (
            <section>
              <h2>Correct this story</h2>
              <form onSubmit={handleCorrectSubmit}>
                <Field label="Headline" htmlFor="headline">
                  <input id="headline" value={correctedHeadline} onChange={(event) => setCorrectedHeadline(event.target.value)} />
                </Field>
                <Field label="Summary" htmlFor="summary">
                  <textarea id="summary" rows={5} value={correctedSummary} onChange={(event) => setCorrectedSummary(event.target.value)} />
                </Field>
                {isAlwaysReviewed && pendingCorrect && (
                  <p role="alert">{story.sensitivity} — confirm this correction to a published sensitive-category story.</p>
                )}
                <div className="card__foot">
                  {pendingCorrect ? (
                    <>
                      <button type="submit" disabled={submitting || !reason}>
                        Confirm submit correction
                      </button>
                      <button type="button" className="button-secondary" disabled={submitting} onClick={() => setPendingCorrect(false)}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button type="submit" disabled={submitting || !reason}>
                      Submit correction
                    </button>
                  )}
                </div>
                {!reason ? <p className="field__hint">Enter a reason in the Decision panel to enable this.</p> : null}
              </form>
            </section>
          ) : null}

          <section>
            <h2>Correction history</h2>
            {story.corrections.length === 0 ? (
              <p className="state-note">No corrections yet.</p>
            ) : (
              <ul>
                {story.corrections.map((correction) => (
                  <li key={correction.id}>
                    {new Date(correction.created_at).toLocaleString()} — {correction.reason}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="decision-panel" aria-label="Decision">
          <h2>Decision</h2>
          {story.status === "REVIEW_REQUIRED" || story.status === "PUBLISHED" || story.status === "UPDATED" ? (
            <Field label={`Reason${isAlwaysReviewed ? " (required for this category)" : ""}`} htmlFor="reason">
              <input id="reason" value={reason} onChange={(event) => setReason(event.target.value)} />
            </Field>
          ) : (
            <p className="state-note">No actions available while the story is {story.status}.</p>
          )}

          {story.status === "REVIEW_REQUIRED" ? (
            <>
              {isAlwaysReviewed && (
                <p role="alert">{story.sensitivity} requires a recorded reason before approve/reject.</p>
              )}
              <label htmlFor="archive">
                <input id="archive" type="checkbox" checked={archive} onChange={(event) => setArchive(event.target.checked)} />
                Archive instead of sending back to draft
              </label>
              <div className="card__foot">
                {pendingAction === "approve" || pendingAction === "reject" ? (
                  <>
                    <button type="button" disabled={submitting || reasonRequired} onClick={() => handleAction(pendingAction)}>
                      Confirm {pendingAction}
                    </button>
                    <button type="button" className="button-secondary" disabled={submitting} onClick={() => setPendingAction(null)}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button" disabled={submitting} onClick={() => (isAlwaysReviewed ? setPendingAction("approve") : handleAction("approve"))}>
                      Approve
                    </button>
                    <button type="button" className="button-secondary" disabled={submitting} onClick={() => (isAlwaysReviewed ? setPendingAction("reject") : handleAction("reject"))}>
                      Reject
                    </button>
                  </>
                )}
              </div>
            </>
          ) : null}

          {story.status === "PUBLISHED" ? (
            <div className="card__foot">
              <button type="button" className="button-secondary" disabled={submitting} onClick={() => handleAction("retract")}>
                Retract
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </main>
  );
}
