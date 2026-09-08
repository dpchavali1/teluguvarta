"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

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

  const [story, setStory] = useState<StoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [archive, setArchive] = useState(false);
  const [correctedHeadline, setCorrectedHeadline] = useState("");
  const [correctedSummary, setCorrectedSummary] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
    try {
      const body = action === "reject" ? { reason: reason || null, archive } : { reason: reason || null };
      await postAction(storyId, action, body);
      setReason("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCorrect(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const en = story?.variants.en;
      const body: Record<string, unknown> = { reason };
      if (correctedHeadline !== en?.headline) body.headline = correctedHeadline;
      if (correctedSummary !== en?.summary) body.summary = correctedSummary;
      await postAction(storyId, "correct", body);
      setReason("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Correction failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !story) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }

  if (!story) {
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  }

  const en = story.variants.en;
  const te = story.variants.te;

  return (
    <main>
      <p>
        <Link href="/review">Back to review queue</Link>
      </p>
      <h1>{en?.headline ?? story.canonical_slug}</h1>
      <p>
        Status: <strong>{story.status}</strong> · Sensitivity: <strong>{story.sensitivity}</strong> · Importance:{" "}
        {story.importance.toFixed(2)}
      </p>
      {story.review_task ? <p>Review reason: {story.review_task.reason}</p> : null}
      {error ? <p role="alert">{error}</p> : null}

      <section>
        <h2>AI draft (English)</h2>
        {en ? (
          <>
            <p>{en.summary}</p>
            {en.why_matters ? <p><em>Why it matters:</em> {en.why_matters}</p> : null}
            <p>QA status: {en.qa_status}</p>
          </>
        ) : (
          <p>No English variant yet.</p>
        )}
        {te ? (
          <>
            <h3>Telugu variant</h3>
            <p>{te.summary}</p>
            <p>QA status: {te.qa_status}</p>
          </>
        ) : null}
      </section>

      <section>
        <h2>Sources ({story.sources.length})</h2>
        <ul>
          {story.sources.map((source) => (
            <li key={source.url}>
              <strong>{source.role}</strong> — {source.source_name} [{source.source_rights_status}]:{" "}
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.title ?? source.url}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Actions</h2>
        <div>
          <label htmlFor="reason">Reason</label>
          <input id="reason" value={reason} onChange={(event) => setReason(event.target.value)} />
        </div>

        {story.status === "REVIEW_REQUIRED" ? (
          <>
            <button type="button" disabled={submitting} onClick={() => handleAction("approve")}>
              Approve
            </button>
            <label>
              <input type="checkbox" checked={archive} onChange={(event) => setArchive(event.target.checked)} />
              Archive instead of sending back to draft
            </label>
            <button type="button" disabled={submitting} onClick={() => handleAction("reject")}>
              Reject
            </button>
          </>
        ) : null}

        {story.status === "PUBLISHED" ? (
          <button type="button" disabled={submitting} onClick={() => handleAction("retract")}>
            Retract
          </button>
        ) : null}
      </section>

      {story.status === "PUBLISHED" || story.status === "UPDATED" ? (
        <section>
          <h2>Correct this story</h2>
          <form onSubmit={handleCorrect}>
            <div>
              <label htmlFor="headline">Headline</label>
              <input
                id="headline"
                value={correctedHeadline}
                onChange={(event) => setCorrectedHeadline(event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="summary">Summary</label>
              <textarea id="summary" value={correctedSummary} onChange={(event) => setCorrectedSummary(event.target.value)} />
            </div>
            <button type="submit" disabled={submitting || !reason}>
              Submit correction
            </button>
          </form>
        </section>
      ) : null}

      <section>
        <h2>Correction history</h2>
        {story.corrections.length === 0 ? (
          <p>No corrections yet.</p>
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
    </main>
  );
}
