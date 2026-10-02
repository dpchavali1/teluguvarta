"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, Field, PageHeader, useToast } from "@/components/ui";
import { apiFetch, apiUrl, clearSession, getRole, isSignedIn } from "@/lib/auth";
import { ago } from "@/lib/time";

interface RightsEvidence {
  terms_url: string | null;
  permitted_fields: string[];
  restrictions: string | null;
  territory: string | null;
  expires_at: string | null;
  notes: string | null;
  public_domain_basis: string | null;
}

interface Source {
  id: string;
  name: string;
  base_url: string | null;
  feed_url: string | null;
  source_type: string | null;
  rights_status: string;
  rights_evidence_url: string | null;
  rights_reviewed_at: string | null;
  reviewer: string | null;
  rights_evidence: RightsEvidence;
  description_evidence: boolean;
  category: string | null;
  active: boolean;
  fail_count: number;
  last_success_at: string | null;
  last_error_at: string | null;
}

interface FeedTest {
  ok: boolean;
  item_count: number;
  headlines: string[];
  error: string | null;
}

interface XAccount {
  source_id: string;
  handle: string;
  x_user_id: string;
  polling_cadence: number | null;
}

// ADR-015 decision 3 allowlist (apps/api/app/ai/privacy.py ALLOWLIST_V1). Only
// these unlock the free AI tier; any other value is stored but routes paid.
const FREE_TIER_CATEGORIES = ["entertainment", "sports", "community_events"];

// ADR-002: only these two are reachable in this build phase.
const RIGHTS_STATUSES = ["DISABLED", "LINK_ONLY"];

interface Preset {
  label: string;
  source_type: string;
  country: string;
  language: string;
  refresh_minutes: number;
  category: string;
}

// Presets prefill the add form only. They never touch rights: the evidence URL
// and reviewer still have to be supplied by a human (ADR-002).
const PRESETS: Preset[] = [
  { label: "US government feed", source_type: "government", country: "US", language: "en", refresh_minutes: 60, category: "" },
  { label: "India news site", source_type: "news", country: "IN", language: "en", refresh_minutes: 30, category: "" },
  { label: "Telugu news site", source_type: "news", country: "IN", language: "te", refresh_minutes: 30, category: "" },
  { label: "Sports blog", source_type: "blog", country: "", language: "en", refresh_minutes: 30, category: "sports" }
];

const BLANK_FORM = { name: "", feed_url: "", base_url: "", source_type: "news", country: "", language: "en", refresh_minutes: 30, category: "" };

async function api(path: string, method: string, body?: unknown): Promise<unknown> {
  const response = await apiFetch(`${apiUrl()}/v1/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`);
  }
  return response.json();
}

const blankToNull = (value: string) => (value.trim() === "" ? null : value.trim());

function AddSourcePanel({ onCreated, onClose }: { onCreated: () => void; onClose: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [preset, setPreset] = useState<string | null>(null);
  const [form, setForm] = useState(BLANK_FORM);
  const [enableNow, setEnableNow] = useState(false);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [reviewer, setReviewer] = useState("");
  const isAdmin = getRole() === "ADMIN";
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<FeedTest | null>(null);

  const set = (key: keyof typeof BLANK_FORM) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: key === "refresh_minutes" ? Number(e.target.value) : e.target.value }));

  async function testFeed() {
    setTesting(true);
    setTest(null);
    try {
      setTest((await api("/sources/test-feed", "POST", { feed_url: form.feed_url })) as FeedTest);
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Feed test failed");
    } finally {
      setTesting(false);
    }
  }

  function applyPreset(p: Preset) {
    setPreset(p.label);
    setForm((prev) => ({ ...prev, source_type: p.source_type, country: p.country, language: p.language, refresh_minutes: p.refresh_minutes, category: p.category }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const isX = form.source_type === "X_ACCOUNT";
      await api("/sources", "POST", {
        name: form.name.trim(),
        feed_url: isX ? null : blankToNull(form.feed_url),
        base_url: blankToNull(form.base_url),
        source_type: form.source_type,
        country: blankToNull(form.country),
        language: blankToNull(form.language),
        refresh_minutes: isX ? null : form.refresh_minutes,
        category: blankToNull(form.category),
        // Same ADR-002 gate as the rights form: the API rejects this unless the
        // caller is an ADMIN and evidence URL + reviewer are present.
        ...(enableNow && !isX
          ? {
              rights_status: "LINK_ONLY",
              rights_evidence_url: blankToNull(evidenceUrl),
              reviewer: blankToNull(reviewer),
              rights_evidence: {
                terms_url: blankToNull(evidenceUrl),
                permitted_fields: ["title", "url", "summary"],
                restrictions: "Link + headline + short summary only (ADR-002)",
                territory: null,
                expires_at: null,
                notes: null
              },
              active: true
            }
          : {})
      });
      toast("ok", isX ? `Added ${form.name.trim()} disabled. Link its verified X user ID, then review rights to enable polling.` : enableNow ? `Added ${form.name.trim()} — enabled and active.` : `Added ${form.name.trim()} — review its rights to enable it.`);
      setEnableNow(false);
      setEvidenceUrl("");
      setReviewer("");
      setForm(BLANK_FORM);
      setPreset(null);
      onCreated();
      onClose();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to add source");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Add a source</h2>
      <p className="field__hint" style={{ marginBottom: "0.75rem" }}>Start from a preset or choose X account. X sources start disabled until their account and rights are reviewed.</p>
      <div className="preset-row" role="group" aria-label="Presets">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" className={preset === p.label ? "is-selected" : "button-secondary"} onClick={() => applyPreset(p)}>
            {p.label}
          </button>
        ))}
      </div>
      <div className="field-grid">
        <Field label="Name" htmlFor="new-name">
          <input id="new-name" required value={form.name} onChange={set("name")} />
        </Field>
        {form.source_type !== "X_ACCOUNT" ? <Field label="Feed URL (RSS/Atom)" htmlFor="new-feed">
          <input id="new-feed" type="url" required value={form.feed_url} onChange={(e) => { setTest(null); set("feed_url")(e); }} placeholder="https://…/feed.xml" />
        </Field> : null}
        <Field label="Site URL" htmlFor="new-base">
          <input id="new-base" type="url" value={form.base_url} onChange={set("base_url")} />
        </Field>
        <Field label="Type" htmlFor="new-type">
          <select id="new-type" value={form.source_type} onChange={set("source_type")}>
            <option value="news">news</option>
            <option value="government">government</option>
            <option value="blog">blog</option>
            <option value="X_ACCOUNT">X account</option>
          </select>
        </Field>
        <Field label="Country" htmlFor="new-country" hint="e.g. US, IN">
          <input id="new-country" value={form.country} onChange={set("country")} />
        </Field>
        <Field label="Language" htmlFor="new-lang" hint="e.g. en, te">
          <input id="new-lang" value={form.language} onChange={set("language")} />
        </Field>
        {form.source_type !== "X_ACCOUNT" ? <Field label="Refresh every (minutes)" htmlFor="new-refresh">
          <input id="new-refresh" type="number" min={5} value={form.refresh_minutes} onChange={set("refresh_minutes")} />
        </Field> : null}
        <Field label="Category" htmlFor="new-cat" hint={`Free AI tier: ${FREE_TIER_CATEGORIES.join(", ")}. Anything else routes to paid AI.`}>
          <input id="new-cat" list="source-categories" value={form.category} onChange={set("category")} />
        </Field>
      </div>
      {form.source_type !== "X_ACCOUNT" ? <fieldset className="enable-now">
        <legend>Rights</legend>
        <label htmlFor="enable-now">
          <input id="enable-now" type="checkbox" checked={enableNow} disabled={!isAdmin} onChange={(e) => setEnableNow(e.target.checked)} />
          I have reviewed this source&apos;s terms — enable (LINK_ONLY) and activate it now
        </label>
        {!isAdmin ? <p className="field__hint">Only an ADMIN can enable a source. It will be added disabled.</p> : null}
        {enableNow ? (
          <div className="field-grid">
            <Field label="Evidence URL" htmlFor="new-evidence" hint="Terms or permission page (required)">
              <input id="new-evidence" type="url" required value={evidenceUrl} onChange={(e) => setEvidenceUrl(e.target.value)} />
            </Field>
            <Field label="Reviewer" htmlFor="new-reviewer" hint="Your name (required)">
              <input id="new-reviewer" required value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            </Field>
          </div>
        ) : (
          <p className="field__hint">Leave unchecked to add it disabled and review rights later.</p>
        )}
      </fieldset> : <p className="field__hint">After adding the source, link its stable X user ID below. Only then review rights and activate polling.</p>}
      {test ? (
        test.ok ? (
          <div className="test-result" role="status">
            <Badge tone="ok">{test.item_count} items found</Badge>
            <ul>
              {test.headlines.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p role="alert">{test.error}</p>
        )
      ) : null}
      <div className="card__foot">
        {form.source_type !== "X_ACCOUNT" ? <button type="button" className="button-secondary" disabled={testing || form.feed_url.trim() === ""} onClick={testFeed}>
          {testing ? "Testing…" : "Test feed"}
        </button> : null}
        <button type="submit" disabled={busy}>
          {busy ? "Adding…" : enableNow ? "Add and activate" : "Add source"}
        </button>
        <button type="button" className="button-secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function RightsForm({ source, onSaved }: { source: Source; onSaved: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const ev = source.rights_evidence;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (key: string) => blankToNull(String(form.get(key) ?? ""));
    const fields = String(form.get("permitted_fields") ?? "")
      .split(",")
      .map((f) => f.trim())
      .filter(Boolean);
    setBusy(true);
    try {
      await api(`/sources/${source.id}`, "PATCH", {
        rights_status: String(form.get("rights_status")),
        rights_evidence_url: text("rights_evidence_url"),
        reviewer: text("reviewer"),
        // Re-stamped on every save that touches rights: this is the review time.
        rights_reviewed_at: new Date().toISOString(),
        rights_evidence: {
          terms_url: text("terms_url"),
          permitted_fields: fields,
          restrictions: text("restrictions"),
          territory: text("territory"),
          expires_at: ev.expires_at,
          notes: text("notes"),
          public_domain_basis: text("public_domain_basis")
        },
        description_evidence: form.get("description_evidence") === "on",
        active: form.get("active") === "on"
      });
      toast("ok", `Saved rights for ${source.name}.`);
      onSaved();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to save rights");
    } finally {
      setBusy(false);
    }
  }

  const id = (name: string) => `${name}-${source.id}`;
  return (
    <form onSubmit={submit} style={{ marginTop: "1rem" }}>
      <p className="field__hint" style={{ marginBottom: "0.75rem" }}>
        Enabling (LINK_ONLY) needs an evidence URL and reviewer, and an ADMIN account. Link + headline + short summary only (ADR-002).
      </p>
      <div className="field-grid">
        <Field label="Rights status" htmlFor={id("status")}>
          <select id={id("status")} name="rights_status" defaultValue={source.rights_status}>
            {RIGHTS_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Evidence URL" htmlFor={id("evurl")} hint="Terms or permission page">
          <input id={id("evurl")} name="rights_evidence_url" type="url" defaultValue={source.rights_evidence_url ?? ""} />
        </Field>
        <Field label="Reviewer" htmlFor={id("reviewer")} hint="Your name">
          <input id={id("reviewer")} name="reviewer" defaultValue={source.reviewer ?? ""} />
        </Field>
        <Field label="Terms URL" htmlFor={id("terms")}>
          <input id={id("terms")} name="terms_url" type="url" defaultValue={ev.terms_url ?? ""} />
        </Field>
        <Field label="Permitted fields" htmlFor={id("fields")} hint="Comma-separated">
          <input id={id("fields")} name="permitted_fields" defaultValue={ev.permitted_fields.join(", ") || "title, url, summary"} />
        </Field>
        <Field label="Restrictions" htmlFor={id("restr")}>
          <input id={id("restr")} name="restrictions" defaultValue={ev.restrictions ?? ""} />
        </Field>
        <Field label="Territory" htmlFor={id("terr")}>
          <input id={id("terr")} name="territory" defaultValue={ev.territory ?? ""} />
        </Field>
      </div>
      <Field label="Notes" htmlFor={id("notes")}>
        <textarea id={id("notes")} name="notes" defaultValue={ev.notes ?? ""} />
      </Field>
      <Field label="Public-domain basis" htmlFor={id("pdbasis")} hint="Needed to store feed text, e.g. U.S. federal government work, 17 U.S.C. §105">
        <input id={id("pdbasis")} name="public_domain_basis" defaultValue={ev.public_domain_basis ?? ""} />
      </Field>
      <label htmlFor={id("descev")}>
        <input id={id("descev")} name="description_evidence" type="checkbox" defaultChecked={source.description_evidence} />
        Store feed text as evidence (ADR-020: ADMIN only, LINK_ONLY + public-domain basis; never shown to readers)
      </label>
      <label htmlFor={id("active")}>
        <input id={id("active")} name="active" type="checkbox" defaultChecked={source.active} />
        Active (fetch this source)
      </label>
      <div className="card__foot">
        <button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save rights"}
        </button>
      </div>
    </form>
  );
}

function XAccountForm({ source, onChanged }: { source: Source; onChanged: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api(`/sources/${source.id}/x-account`, "POST", {
        x_user_id: String(data.get("x_user_id") ?? "").trim(),
        handle: String(data.get("handle") ?? "").trim().replace(/^@/, ""),
        polling_cadence: Number(data.get("polling_cadence")),
        budget_class: String(data.get("budget_class"))
      });
      toast("ok", `Linked X account to ${source.name}. Review rights before activating.`);
      onChanged();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to link X account");
    } finally {
      setBusy(false);
    }
  }

  return <form onSubmit={submit} style={{ marginTop: "1rem" }}>
    <p className="field__hint">Verify official ownership and the stable numeric user ID before linking. The handle alone is not enough. No X API key belongs in this form.</p>
    <div className="field-grid">
      <Field label="X handle" htmlFor={`x-handle-${source.id}`}>
        <input id={`x-handle-${source.id}`} name="handle" required pattern="@?[A-Za-z0-9_]{1,15}" placeholder="@USCIS" />
      </Field>
      <Field label="Stable X user ID" htmlFor={`x-id-${source.id}`}>
        <input id={`x-id-${source.id}`} name="x_user_id" required pattern="[0-9]+" inputMode="numeric" />
      </Field>
      <Field label="Poll every (minutes)" htmlFor={`x-cadence-${source.id}`}>
        <input id={`x-cadence-${source.id}`} name="polling_cadence" type="number" min="5" defaultValue="30" required />
      </Field>
      <Field label="Budget priority" htmlFor={`x-budget-${source.id}`}>
        <select id={`x-budget-${source.id}`} name="budget_class" defaultValue="LOW">
          <option value="LOW">Low — pause when monthly budget is reached</option>
          <option value="STANDARD">Standard — continue past monthly budget</option>
        </select>
      </Field>
    </div>
    <div className="card__foot"><button type="submit" disabled={busy}>{busy ? "Linking…" : "Link X account"}</button></div>
  </form>;
}

function SourceCard({ source, xAccount, xAccountsLoaded, onChanged }: { source: Source; xAccount?: XAccount; xAccountsLoaded: boolean; onChanged: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const current = (draft ?? source.category ?? "").trim();
  const dirty = draft !== null && current !== (source.category ?? "");
  const enabled = source.rights_status !== "DISABLED";
  const isX = source.source_type === "X_ACCOUNT";
  const freeTier = FREE_TIER_CATEGORIES.includes(current.toLowerCase());

  async function saveCategory() {
    setSaving(true);
    try {
      await api(`/sources/${source.id}`, "PATCH", { category: current === "" ? null : current });
      setDraft(null);
      toast("ok", `Category saved for ${source.name}.`);
      onChanged();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to save category");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className={enabled ? "card" : "card card--attention"}>
      <div className="card__head">
        <h2 className="card__title">{source.name}</h2>
        <span className="pill-row">
          <Badge tone={enabled ? "ok" : "warn"}>{source.rights_status}</Badge>
          <Badge tone={source.active ? "ok" : "neutral"}>{source.active ? "active" : "inactive"}</Badge>
          {isX ? <Badge tone="neutral">X account</Badge> : null}
          {source.fail_count > 0 ? <Badge tone="danger">failing</Badge> : null}
          <Badge tone={freeTier ? "ok" : "neutral"}>{freeTier ? "free AI tier" : "paid AI only"}</Badge>
        </span>
      </div>
      <p className="card__meta">{isX ? xAccount ? `@${xAccount.handle} · ID ${xAccount.x_user_id} · every ${xAccount.polling_cadence ?? "—"} min` : xAccountsLoaded ? "X account not linked" : "Loading X account…" : source.feed_url ?? source.base_url ?? "No feed URL"}</p>
      {enabled ? (
        <p className="card__meta" title={source.last_success_at ? new Date(source.last_success_at).toLocaleString() : undefined}>
          {source.last_success_at ? `Last fetched ${ago(source.last_success_at)}` : "Never fetched"}
          {source.fail_count > 0 ? ` · ${source.fail_count} consecutive failures` : ""}
        </p>
      ) : null}
      {!enabled ? (
        <p className="card__prompt">Needs a rights review before it can ingest — add the evidence URL and your name.</p>
      ) : null}
      <div className="card__foot">
        <input
          list="source-categories"
          aria-label={`Category for ${source.name}`}
          value={draft ?? source.category ?? ""}
          placeholder="category (unset)"
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="button" disabled={!dirty || saving} onClick={saveCategory}>
          {saving ? "Saving…" : "Save category"}
        </button>
        <button type="button" className={enabled ? "button-secondary" : undefined} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : enabled ? "Edit rights" : "Review rights"}
        </button>
      </div>
      {isX && xAccountsLoaded && !xAccount ? <XAccountForm source={source} onChanged={onChanged} /> : null}
      {open ? <RightsForm source={source} onSaved={onChanged} /> : null}
    </article>
  );
}

export default function SourcesPage() {
  const router = useRouter();
  const toast = useToast();
  const [sources, setSources] = useState<Source[] | null>(null);
  const [xAccounts, setXAccounts] = useState<XAccount[] | null>(null);
  const [adding, setAdding] = useState(false);

  function load() {
    const signedIn = isSignedIn();
    if (!signedIn) {
      router.replace("/login");
      return;
    }
    apiFetch(`${apiUrl()}/v1/admin/sources`)
      .then((response) => {
        if (response.status === 401) {
          clearSession();
          router.replace("/login");
        }
        return response.ok ? response.json() : Promise.reject(new Error("Failed to load sources"));
      })
      .then((body: Source[]) => setSources(body))
      .catch((err) => toast("danger", err instanceof Error ? err.message : "Failed to load sources"));
    api("/x-accounts", "GET")
      .then((body) => setXAccounts(body as XAccount[]))
      .catch((err) => toast("danger", err instanceof Error ? err.message : "Failed to load X accounts"));
  }

  useEffect(load, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  const needsReview = sources?.filter((s) => s.rights_status === "DISABLED").length ?? 0;

  return (
    <main>
      <PageHeader
        title="Sources"
        subtitle={sources ? `${sources.length} total · ${needsReview} need a rights review` : undefined}
        actions={
          !adding ? (
            <button type="button" onClick={() => setAdding(true)}>
              Add source
            </button>
          ) : null
        }
      />
      <datalist id="source-categories">
        {FREE_TIER_CATEGORIES.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {adding ? <AddSourcePanel onCreated={load} onClose={() => setAdding(false)} /> : null}
      {sources === null ? (
        <p className="state-note">Loading…</p>
      ) : sources.length === 0 ? (
        <EmptyState title="No sources yet" hint="Add a feed to start ingesting stories." />
      ) : (
        <div className="card-list">
          {sources.map((source) => (
            <SourceCard key={source.id} source={source} xAccount={xAccounts?.find((account) => account.source_id === source.id)} xAccountsLoaded={xAccounts !== null} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  );
}
