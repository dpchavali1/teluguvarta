"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

interface Source {
  id: string;
  name: string;
  rights_status: string;
  category: string | null;
  active: boolean;
}

// ADR-015 decision 3 allowlist (apps/api/app/ai/privacy.py ALLOWLIST_V1). Only
// these unlock the free AI tier; any other value is stored but routes paid.
const FREE_TIER_CATEGORIES = ["entertainment", "sports", "community_events"];

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
      const response = await fetch(`${apiUrl()}/v1/admin/sources/${source.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ category: value === "" ? null : value })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(body?.error?.message ?? "Failed to save category");
      }
      setDrafts(({ [source.id]: _saved, ...rest }) => rest);
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
      {sources === null ? (
        <p className="state-note">Loading…</p>
      ) : (
        <>
          <datalist id="source-categories">
            {FREE_TIER_CATEGORIES.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
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
                    <td>{source.name}</td>
                    <td>{source.rights_status}</td>
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
        </>
      )}
    </main>
  );
}
