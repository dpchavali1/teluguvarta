"use client";

import { useState } from "react";
import { MAX_NOTE_LENGTH, setNote, toggleMembership, type SavedExtras } from "@teluguvarta/domain/savedExtras.ts";

// P06 / ADR-044: a note and collections for one bookmark, device-only.
export function SavedOrganizer({ storyId, extras, onChange }: {
  storyId: string; extras: SavedExtras; onChange: (next: SavedExtras) => void;
}) {
  const [draft, setDraft] = useState(extras.notes[storyId] ?? "");
  const memberOf = extras.membership[storyId] ?? [];
  const noteChanged = draft.trim() !== (extras.notes[storyId] ?? "");
  const summary = [memberOf.length ? `${memberOf.length} ${memberOf.length === 1 ? "list" : "lists"}` : "", extras.notes[storyId] ? "note" : ""].filter(Boolean).join(", ");

  return (
    <details className="saved-organizer">
      <summary>Organize{summary ? ` (${summary})` : ""}</summary>
      {extras.collections.length ? (
        <fieldset>
          <legend>Lists</legend>
          {extras.collections.map((c) => (
            <label key={c.id}>
              <input type="checkbox" checked={memberOf.includes(c.id)}
                onChange={() => onChange(toggleMembership(extras, storyId, c.id))} /> {c.name}
            </label>
          ))}
        </fieldset>
      ) : <p>Create a list above to group saved stories.</p>}
      <label htmlFor={`note-${storyId}`}>Private note (stays in this browser)</label>
      <textarea id={`note-${storyId}`} rows={3} maxLength={MAX_NOTE_LENGTH} value={draft}
        onChange={(event) => setDraft(event.target.value)} />
      <button type="button" className="button button--small" disabled={!noteChanged}
        onClick={() => onChange(setNote(extras, storyId, draft))}>Save note</button>
    </details>
  );
}
