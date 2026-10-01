"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Badge, EmptyState, Field, PageHeader, useToast } from "@/components/ui";
import { apiFetch, apiUrl, clearSession, getRole, isSignedIn } from "@/lib/auth";
import { isUnclassified, reasonHelp, reasonTone } from "@/lib/reviewReasons";
import { useUnsavedGuard } from "@/lib/unsaved";

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
  // ADR-020: stored feed text (public-domain sources only); never shown to readers.
  description: string | null;
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
  format?: "FULL" | "BRIEF";
  importance: number;
  importance_override?: ImportanceLevel | null;
  classification_confidence?: number | null;
  published_at: string | null;
  variants: Record<string, StoryVariant>;
  topics?: string[];
  countries?: string[];
  sources: StorySource[];
  review_task: { reason: string; status: string } | null;
  corrections: Correction[];
}

async function postAction(storyId: string, action: string, body: Record<string, unknown>): Promise<void> {
  const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(errorBody?.error?.message ?? `${action} failed`);
  }
}

// Next pending story in the queue's order (always-human-reviewed first, then
// oldest; the server sorts). Null on any failure, so the caller falls back to
// the queue.
async function nextQueueStory(currentId: string): Promise<string | null> {
  try {
    const response = await apiFetch(`${apiUrl()}/v1/admin/review-queue?limit=2`);
    if (!response.ok) return null;
    const page = (await response.json()) as { items: { story_id: string }[] };
    return page.items.find((item) => item.story_id !== currentId)?.story_id ?? null;
  } catch {
    return null;
  }
}

async function putDraft(storyId: string, language: "en" | "te", body: Record<string, unknown>): Promise<void> {
  const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/variants/${language}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(errorBody?.error?.message ?? "Saving the draft failed");
  }
}

async function putStoryField(storyId: string, field: string, body: Record<string, unknown>, failure: string): Promise<void> {
  const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/${field}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(errorBody?.error?.message ?? failure);
  }
}

type ImportanceLevel = "LOW" | "NORMAL" | "HIGH";

// ADR-027: the countries the API accepts (app/content/geography.py).
const EVENT_COUNTRIES: { code: string; name: string }[] = [
  { code: "US", name: "United States" },
  { code: "IN", name: "India" },
  { code: "CA", name: "Canada" },
  { code: "GB", name: "United Kingdom" },
  { code: "AU", name: "Australia" },
  { code: "AE", name: "United Arab Emirates" },
  { code: "SG", name: "Singapore" },
  { code: "NZ", name: "New Zealand" },
  { code: "DE", name: "Germany" }
];
const MAX_COUNTRIES = 5;

// ADR-027: where the story happens, not where the publisher is based. The
// model's countries fill this for AI drafts; hand-drafted stories get it here.
function CountryEditor({ storyId, current, reason, onSaved }: { storyId: string; current: string[]; reason: string; onSaved: () => void }) {
  const toast = useToast();
  const [selected, setSelected] = useState<string[]>(current);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = [...selected].sort().join(",") !== [...current].sort().join(",");

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await putStoryField(storyId, "countries", { countries: selected, reason: reason || null }, "Saving countries failed");
      toast("ok", "Countries saved.");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving countries failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <fieldset className="enable-now">
      <legend>Where it happens (up to {MAX_COUNTRIES}; not the publisher&apos;s country)</legend>
      {EVENT_COUNTRIES.map((country) => {
        const checked = selected.includes(country.code);
        return (
          <label key={country.code} htmlFor={`country-${country.code}`}>
            <input
              id={`country-${country.code}`}
              type="checkbox"
              checked={checked}
              disabled={!checked && selected.length >= MAX_COUNTRIES}
              onChange={(event) =>
                setSelected((prev) => (event.target.checked ? [...prev, country.code] : prev.filter((c) => c !== country.code)))
              }
            />
            {country.name}
          </label>
        );
      })}
      {error ? <p role="alert">{error}</p> : null}
      <div className="card__foot">
        <button type="button" disabled={saving || !changed} onClick={save}>
          Save countries
        </button>
      </div>
    </fieldset>
  );
}

// ADR-027: importance is scored from urgency, sources and topics; an editor's
// level replaces the score until cleared.
function ImportanceEditor({ storyId, current, reason, onSaved }: { storyId: string; current: ImportanceLevel | null; reason: string; onSaved: () => void }) {
  const toast = useToast();
  const [level, setLevel] = useState<ImportanceLevel | "">(current ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await putStoryField(storyId, "importance", { level: level || null, reason: reason || null }, "Saving importance failed");
      toast("ok", "Importance saved.");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving importance failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <label htmlFor="importance-level">Importance</label>{" "}
      <select id="importance-level" value={level} onChange={(event) => setLevel(event.target.value as ImportanceLevel | "")}>
        <option value="">Computed</option>
        <option value="LOW">Low</option>
        <option value="NORMAL">Normal</option>
        <option value="HIGH">High</option>
      </select>{" "}
      <button type="button" disabled={saving || level === (current ?? "")} onClick={save}>
        Save importance
      </button>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}

const MAX_TOPICS = 5;

// Review #11: AI classification tags the stories it drafts; a hand-drafted
// story gets topics only here, or it never shows on a topic page. Picks from
// the existing active topics (the public config), in any story status.
function TopicEditor({ storyId, current, reason, onSaved }: { storyId: string; current: string[]; reason: string; onSaved: () => void }) {
  const toast = useToast();
  const [topics, setTopics] = useState<{ slug: string; name: string }[] | null>(null);
  const [selected, setSelected] = useState<string[]>(current);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiUrl()}/v1/config`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Couldn't load topics"))))
      .then((body: { topics: { slug: string; name: string; active: boolean }[] }) =>
        setTopics(body.topics.filter((t) => t.active).sort((a, b) => a.name.localeCompare(b.name)))
      )
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load topics"));
  }, []);

  const changed = [...selected].sort().join(",") !== [...current].sort().join(",");

  function toggle(slug: string, on: boolean) {
    setSelected((prev) => (on ? [...prev, slug] : prev.filter((s) => s !== slug)));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/topics`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topics: selected, reason: reason || null })
      });
      if (!response.ok) {
        const errorBody = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(errorBody?.error?.message ?? "Saving topics failed");
      }
      toast("ok", "Topics saved.");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving topics failed");
    } finally {
      setSaving(false);
    }
  }

  if (topics === null) return error ? <p role="alert">{error}</p> : <p>Loading topics…</p>;

  return (
    <fieldset className="enable-now">
      <legend>Topics (up to {MAX_TOPICS})</legend>
      {topics.map((topic) => {
        const checked = selected.includes(topic.slug);
        return (
          <label key={topic.slug} htmlFor={`topic-${topic.slug}`}>
            <input
              id={`topic-${topic.slug}`}
              type="checkbox"
              checked={checked}
              disabled={!checked && selected.length >= MAX_TOPICS}
              onChange={(event) => toggle(topic.slug, event.target.checked)}
            />
            {topic.name}
          </label>
        );
      })}
      {error ? <p role="alert">{error}</p> : null}
      <div className="card__foot">
        <button type="button" disabled={saving || !changed} onClick={save}>
          Save topics
        </button>
      </div>
    </fieldset>
  );
}

// Editor-written draft for a story still in review — the fallback when no AI
// route could draft it (NO_PAID_PROVIDER, budget exhausted, outage). Rewriting
// the English discards any Telugu, which is derived from it.
// Review 2026-09-30 R9: docs/EDITORIAL_STYLE.md targets, as guidance only
// (ADR-026 decides what blocks publication). Word targets are for English;
// Telugu gets the count alone.
function lengthHint(text: string, language: string, englishTarget: string): string {
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const count = `${words} ${words === 1 ? "word" : "words"}`;
  return language === "en" ? `${count}. Guide: ${englishTarget}.` : `${count}. Keep it as short as the English.`;
}

function DraftEditor({
  storyId,
  language,
  variant,
  sourceTitle,
  reason,
  onSaved
}: {
  storyId: string;
  language: "en" | "te";
  variant: StoryVariant | undefined;
  // Pre-fills a new English headline so the editor edits rather than types.
  sourceTitle?: string | null;
  reason: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const prefilled = !variant && Boolean(sourceTitle);
  const [headline, setHeadline] = useState(variant?.headline ?? sourceTitle ?? "");
  const [summary, setSummary] = useState(variant?.summary ?? "");
  const [whyMatters, setWhyMatters] = useState(variant?.why_matters ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = language === "en" ? "English" : "Telugu";
  const id = `draft-${language}`;
  useUnsavedGuard(
    open &&
      (headline !== (variant?.headline ?? sourceTitle ?? "") ||
        summary !== (variant?.summary ?? "") ||
        whyMatters !== (variant?.why_matters ?? ""))
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await putDraft(storyId, language, { headline, summary, why_matters: whyMatters || null, reason: reason || null });
      toast("ok", `${label} draft saved.`);
      setOpen(false);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving the draft failed");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <div className="card__foot">
        <button type="button" className="button-secondary" onClick={() => setOpen(true)}>
          {variant ? `Edit ${label}` : `Write ${label} draft`}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} lang={language}>
      <h3 lang="en">{label} draft</h3>
      <Field label="Headline" htmlFor={`${id}-headline`} hint={lengthHint(headline, language, "at most 12")}>
        <input id={`${id}-headline`} required value={headline} onChange={(event) => setHeadline(event.target.value)} />
      </Field>
      <Field label="Summary" htmlFor={`${id}-summary`} hint={lengthHint(summary, language, "about 40–80, two or three sentences")}>
        <textarea id={`${id}-summary`} required rows={5} value={summary} onChange={(event) => setSummary(event.target.value)} />
      </Field>
      <Field
        label="Why it matters (optional)"
        htmlFor={`${id}-why`}
        hint={lengthHint(whyMatters, language, "one sentence, at most 30; leave empty if the sources support no concrete consequence")}
      >
        <textarea id={`${id}-why`} rows={2} value={whyMatters} onChange={(event) => setWhyMatters(event.target.value)} />
      </Field>
      {prefilled ? (
        <p className="field__hint" lang="en">
          Headline pre-filled from the source. Rewrite it in our own words, and summarise only what the source says.
        </p>
      ) : null}
      {language === "en" ? (
        <p className="field__hint" lang="en">
          Saving replaces any Telugu version, which must then be rewritten or re-translated.
        </p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      <div className="card__foot" lang="en">
        <button type="submit" disabled={saving}>
          Save {label}
        </button>
        <button type="button" className="button-secondary" disabled={saving} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
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
    const signedIn = isSignedIn();
    if (!signedIn) {
      router.replace("/login");
      return;
    }
    apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}`)
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

  useUnsavedGuard(
    story !== null &&
      (correctedHeadline !== (story.variants.en?.headline ?? "") || correctedSummary !== (story.variants.en?.summary ?? ""))
  );

  async function handleAction(action: "approve" | "reject" | "retract") {
    setSubmitting(true);
    setError(null);
    setPendingAction(null);
    try {
      const body = action === "reject" ? { reason: reason || null, archive } : { reason: reason || null };
      await postAction(storyId, action, body);
      setReason("");
      setArchive(false); // the next story reuses this page, so don't carry the choice over
      if (action === "retract") {
        toast("ok", "Story retracted.");
        load();
      } else {
        // Straight on to the next story so triage is one decision after another.
        toast("ok", action === "approve" ? "Approved." : archive ? "Rejected and archived." : "Rejected — sent back to draft.");
        const next = await nextQueueStory(storyId);
        router.push(next ? `/review/${next}` : "/review");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  }

  // ADR-025: send an AI-held story back through generation. ADMIN only,
  // audited, at most 2 times per story — the API enforces all three.
  async function retryAi() {
    if (!reason.trim()) {
      setError("Give a reason for retrying the AI (it's recorded in the audit log).");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await postAction(storyId, "retry-ai", { stage: "GENERATE", reason: reason.trim() });
      setReason("");
      toast("ok", "Sent back to the AI — it will return to the queue once drafted.");
      const next = await nextQueueStory(storyId);
      router.push(next ? `/review/${next}` : "/review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed");
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
  const heldByAi = heldReasons.some((r) => r === "AI_RETRIES_EXHAUSTED" || r === "NO_PAID_PROVIDER");
  const unclassified = story.sensitivity === "NONE" && story.review_task !== null && isUnclassified(story.review_task.reason);
  const primarySourceTitle =(story.sources.find((s) => s.role === "PRIMARY") ?? story.sources[0])?.title ?? null;

  return (
    <main>
      <p>
        <Link href="/review">← Back to review queue</Link>
      </p>
      <PageHeader
        title={en?.headline ?? primarySourceTitle ?? story.canonical_slug}
        subtitle={`Importance ${story.importance.toFixed(2)}${story.importance_override ? ` (set ${story.importance_override.toLowerCase()})` : ""} · Model confidence ${
          story.classification_confidence == null ? "—" : story.classification_confidence.toFixed(2)
        }`}
        actions={
          <span className="pill-row">
            <Badge tone={statusNotice?.tone ?? "neutral"}>{story.status}</Badge>
            <Badge tone={isAlwaysReviewed ? "danger" : "warn"}>{unclassified ? "UNCLASSIFIED" : story.sensitivity}</Badge>
            {story.format === "BRIEF" ? <Badge>BRIEF · auto-published (ADR-019)</Badge> : null}
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
            <h2>Draft</h2>
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
            {story.status === "REVIEW_REQUIRED" ? (
              <div>
                {/* Keyed on the saved text so an open editor never shows stale copy after a save. */}
                <DraftEditor key={`en-${story.id}-${en?.headline}`} storyId={story.id} language="en" variant={en} sourceTitle={primarySourceTitle} reason={reason} onSaved={load} />
                {en ? (
                  <DraftEditor key={`te-${story.id}-${te?.headline}`} storyId={story.id} language="te" variant={te} reason={reason} onSaved={load} />
                ) : null}
              </div>
            ) : null}
          </section>

          <section>
            <h2>Topics</h2>
            <TopicEditor key={(story.topics ?? []).join(",")} storyId={story.id} current={story.topics ?? []} reason={reason} onSaved={load} />
          </section>

          <section>
            <h2>Geography and importance</h2>
            <CountryEditor key={(story.countries ?? []).join(",")} storyId={story.id} current={story.countries ?? []} reason={reason} onSaved={load} />
            <ImportanceEditor key={story.importance_override ?? "computed"} storyId={story.id} current={story.importance_override ?? null} reason={reason} onSaved={load} />
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
                  {source.description ? (
                    <details>
                      <summary>Source text (evidence only, not for readers)</summary>
                      <p className="field__hint">{source.description}</p>
                    </details>
                  ) : null}
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
            <p>
              <Link href={`/audit?entity_id=${story.id}`}>Every recorded action on this story</Link>
            </p>
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
                    <button type="button" disabled={submitting || !en} onClick={() => (isAlwaysReviewed ? setPendingAction("approve") : handleAction("approve"))}>
                      Approve
                    </button>
                    <button type="button" className="button-secondary" disabled={submitting} onClick={() => (isAlwaysReviewed ? setPendingAction("reject") : handleAction("reject"))}>
                      Reject
                    </button>
                    {heldByAi && getRole() === "ADMIN" ? (
                      <button type="button" className="button-secondary" disabled={submitting} onClick={retryAi}>
                        Retry AI
                      </button>
                    ) : null}
                  </>
                )}
              </div>
              {!en ? <p className="field__hint">Write an English draft before approving.</p> : null}
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
