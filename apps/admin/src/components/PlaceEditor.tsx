"use client";

import { useState } from "react";
import { PLACES, getPlace } from "@teluguvarta/domain";
import { useToast } from "@/components/ui";
import { apiFetch, apiUrl } from "@/lib/auth";

// Mirrors AdminPlacesRequest.places max_length in the API.
const MAX_STORY_PLACES = 8;
const MAX_MATCHES = 12;

function label(id: string): string {
  const place = getPlace(id);
  if (!place) return id;
  const parent = place.parentId ? getPlace(place.parentId) : undefined;
  return parent ? `${place.nameEn}, ${parent.nameEn}` : place.nameEn;
}

// ADR-043: catalog places where the story happens. Generation proposes them;
// an editor replaces the set here. Catalog ids only (the API rejects others).
export function PlaceEditor({ storyId, current, reason, onSaved }: {
  storyId: string; current: string[]; reason: string; onSaved: () => void;
}) {
  const toast = useToast();
  const [selected, setSelected] = useState<string[]>(current);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = [...selected].sort().join(",") !== [...current].sort().join(",");
  const needle = query.trim().toLowerCase();
  const matches = needle
    ? PLACES.filter((p) => !selected.includes(p.id) &&
        (p.nameEn.toLowerCase().includes(needle) || p.nameTe.includes(query.trim()) || p.id.toLowerCase() === needle))
        .slice(0, MAX_MATCHES)
    : [];

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/places`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ places: selected, reason: reason || null }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(body?.error?.message ?? "Saving places failed");
      }
      toast("ok", "Places saved.");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving places failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <fieldset className="enable-now">
      <legend>Places (up to {MAX_STORY_PLACES}; readers following these places see the story)</legend>
      {selected.length ? (
        <ul aria-label="Selected places">
          {selected.map((id) => (
            <li key={id}>
              {label(id)}{" "}
              <button type="button" className="button-secondary" aria-label={`Remove ${label(id)}`}
                onClick={() => setSelected((prev) => prev.filter((p) => p !== id))}>Remove</button>
            </li>
          ))}
        </ul>
      ) : <p>No places set. The story shows only on country-level pages.</p>}
      <label htmlFor="place-search">Add a place</label>
      <input id="place-search" type="search" value={query} placeholder="Search by English or Telugu name"
        disabled={selected.length >= MAX_STORY_PLACES} onChange={(event) => setQuery(event.target.value)} />
      {needle && !matches.length ? <p>No catalog place matches. Only catalog places can be added.</p> : null}
      {matches.length ? (
        <ul aria-label="Matching places">
          {matches.map((p) => (
            <li key={p.id}>
              <button type="button" className="button-secondary"
                onClick={() => { setSelected((prev) => [...prev, p.id]); setQuery(""); }}>
                Add {label(p.id)}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      <div className="card__foot">
        <button type="button" disabled={saving || !changed} onClick={save}>Save places</button>
      </div>
    </fieldset>
  );
}
