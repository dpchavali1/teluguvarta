"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

interface RightsEvidence {
  terms_url: string | null;
  permitted_fields: string[];
  restrictions: string | null;
  territory: string | null;
  expires_at: string | null;
  notes: string | null;
}

interface Source {
  id: string;
  name: string;
  base_url: string | null;
  feed_url: string | null;
  rights_status: string;
  rights_evidence_url: string | null;
  rights_reviewed_at: string | null;
  reviewer: string | null;
  rights_evidence: RightsEvidence;
  category: string | null;
  active: boolean;
}

// ADR-015 decision 3 allowlist (apps/api/app/ai/privacy.py ALLOWLIST_V1). Only
// these unlock the free AI tier; any other value is stored but routes paid.
const FREE_TIER_CATEGORIES = ["entertainment", "sports", "community_events"];

// ADR-002: only these two are reachable in this build phase.
const RIGHTS_STATUSES = ["DISABLED", "LINK_ONLY"];

async function api(path: string, method: string, body?: unknown): Promise<unknown> {
  const response = await fetch(`${apiUrl()}/v1/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`);
  }
  return response.json();
}

const blankToNull = (value: string) => (value.trim() === "" ? null : value.trim());

function AddSourceForm({ onCreated, onError }: { onCreated: () => void; onError: (m: string | null) => void }) {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (key: string) => blankToNull(String(form.get(key) ?? ""));
    const refresh = text("refresh_minutes");
    setBusy(true);
    onError(null);
    try {
      await api("/sources", "POST", {
        name: text("name"),
        feed_url: text("feed_url"),
        base_url: text("base_url"),
        source_type: text("source_type"),
        country: text("country"),
        language: text("language"),
        refresh_minutes: refresh === null ? null : Number(refresh),
        category: text("category")
      });
      (event.target as HTMLFormElement).reset();
      onCreated();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add source");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details>
      <summary>Add source</summary>
      <form onSubmit={submit}>
        <p className="state-note">New sources start DISABLED and inactive. Set rights below before they can ingest.</p>
        <label htmlFor="new-name">Name</label>
        <input id="new-name" name="name" required />
        <label htmlFor="new-feed">Feed URL (RSS/Atom)</label>
        <input id="new-feed" name="feed_url" type="url" required />
        <label htmlFor="new-base">Site URL</label>
        <input id="new-base" name="base_url" type="url" />
        <label htmlFor="new-type">Type</label>
        <select id="new-type" name="source_type" defaultValue="news">
          <option value="news">news</option>
          <option value="government">government</option>
          <option value="blog">blog</option>
        </select>
        <label htmlFor="new-country">Country (e.g. US, IN)</label>
        <input id="new-country" name="country" />
        <label htmlFor="new-lang">Language (e.g. en, te)</label>
        <input id="new-lang" name="language" defaultValue="en" />
        <label htmlFor="new-refresh">Refresh every (minutes)</label>
        <input id="new-refresh" name="refresh_minutes" type="number" min={5} defaultValue={30} />
        <label htmlFor="new-cat">Category (optional)</label>
        <input id="new-cat" name="category" list="source-categories" />
        <button type="submit" disabled={busy}>
          {busy ? "Adding…" : "Add source"}
        </button>
      </form>
    </details>
  );
}

function RightsForm({ source, onSaved, onError }: { source: Source; onSaved: () => void; onError: (m: string | null) => void }) {
  const [busy, setBusy] = useState(false);
  const ev = source.rights_evidence;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (key: string) => blankToNull(String(form.get(key) ?? ""));
    const status = String(form.get("rights_status"));
    const evidenceUrl = text("rights_evidence_url");
    const reviewer = text("reviewer");
    const fields = String(form.get("permitted_fields") ?? "")
      .split(",")
      .map((f) => f.trim())
      .filter(Boolean);
    setBusy(true);
    onError(null);
    try {
      await api(`/sources/${source.id}`, "PATCH", {
        rights_status: status,
        rights_evidence_url: evidenceUrl,
        reviewer,
        // Re-stamped on every save that touches rights: this is the review time.
        rights_reviewed_at: new Date().toISOString(),
        rights_evidence: {
          terms_url: text("terms_url"),
          permitted_fields: fields,
          restrictions: text("restrictions"),
          territory: text("territory"),
          expires_at: ev.expires_at,
          notes: text("notes")
        },
        active: form.get("active") === "on"
      });
      onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save rights");
    } finally {
      setBusy(false);
    }
  }

  const id = (name: string) => `${name}-${source.id}`;
  return (
    <form onSubmit={submit}>
      <p className="state-note">
        Enabling (LINK_ONLY) needs an evidence URL and reviewer, and an ADMIN account. Link + headline + short summary only (ADR-002).
      </p>
      <label htmlFor={id("status")}>Rights status</label>
      <select id={id("status")} name="rights_status" defaultValue={source.rights_status}>
        {RIGHTS_STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <label htmlFor={id("evurl")}>Evidence URL (terms / permission page)</label>
      <input id={id("evurl")} name="rights_evidence_url" type="url" defaultValue={source.rights_evidence_url ?? ""} />
      <label htmlFor={id("reviewer")}>Reviewer (your name)</label>
      <input id={id("reviewer")} name="reviewer" defaultValue={source.reviewer ?? ""} />
      <label htmlFor={id("terms")}>Terms URL</label>
      <input id={id("terms")} name="terms_url" type="url" defaultValue={ev.terms_url ?? ""} />
      <label htmlFor={id("fields")}>Permitted fields (comma-separated)</label>
      <input id={id("fields")} name="permitted_fields" defaultValue={ev.permitted_fields.join(", ") || "title, url, summary"} />
      <label htmlFor={id("restr")}>Restrictions</label>
      <input id={id("restr")} name="restrictions" defaultValue={ev.restrictions ?? ""} />
      <label htmlFor={id("terr")}>Territory</label>
      <input id={id("terr")} name="territory" defaultValue={ev.territory ?? ""} />
      <label htmlFor={id("notes")}>Notes</label>
      <textarea id={id("notes")} name="notes" defaultValue={ev.notes ?? ""} />
      <label htmlFor={id("active")}>
        <input id={id("active")} name="active" type="checkbox" defaultChecked={source.active} style={{ width: "auto", marginRight: "0.5rem" }} />
        Active (fetch this source)
      </label>
      <button type="submit" disabled={busy}>
        {busy ? "Saving…" : "Save rights"}
      </button>
    </form>
  );
}

export default function SourcesPage() {
  const router = useRouter();
  const [sources, setSources] = useState<Source[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/sources`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (response.status === 401) {
          clearSession();
          router.replace("/login");
        }
        return response.ok ? response.json() : Promise.reject(new Error("Failed to load sources"));
      })
      .then((body: Source[]) => setSources(body))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load sources"));
  }

  useEffect(load, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveCategory(source: Source) {
    const value = (drafts[source.id] ?? source.category ?? "").trim();
    setSavingId(source.id);
    setError(null);
    try {
      await api(`/sources/${source.id}`, "PATCH", { category: value === "" ? null : value });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[source.id];
        return next;
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save category");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <main>
      <h1>Sources</h1>
      {error ? <p role="alert">{error}</p> : null}
      <datalist id="source-categories">
        {FREE_TIER_CATEGORIES.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <AddSourceForm onCreated={load} onError={setError} />
      {sources === null ? (
        <p className="state-note">Loading…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Rights</th>
              <th>Category</th>
              <th>Free AI tier</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => {
              const draft = drafts[source.id];
              const current = (draft ?? source.category ?? "").trim();
              const dirty = draft !== undefined && current !== (source.category ?? "");
              return (
                <tr key={source.id}>
                  <td>
                    {source.name}
                    <details>
                      <summary>Rights &amp; status</summary>
                      <RightsForm source={source} onSaved={load} onError={setError} />
                    </details>
                  </td>
                  <td>
                    {source.rights_status}
                    <br />
                    {source.active ? "active" : "inactive"}
                  </td>
                  <td>
                    <input
                      list="source-categories"
                      aria-label={`Category for ${source.name}`}
                      value={draft ?? source.category ?? ""}
                      placeholder="unset"
                      onChange={(e) => setDrafts({ ...drafts, [source.id]: e.target.value })}
                    />
                  </td>
                  <td>{FREE_TIER_CATEGORIES.includes(current.toLowerCase()) ? "Eligible" : "Paid only"}</td>
                  <td>
                    <button type="button" disabled={!dirty || savingId === source.id} onClick={() => saveCategory(source)}>
                      {savingId === source.id ? "Saving…" : "Save"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
