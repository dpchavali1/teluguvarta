"use client";

import { useState } from "react";

import { presets, rangeError } from "@/lib/dateRange";

export type DayRange = { start: string; end: string };

// Preset and custom ranges of UTC days for the report pages.
export function RangePicker({ range, onChange }: { range: DayRange; onChange: (range: DayRange) => void }) {
  const [draft, setDraft] = useState(range);
  const draftError = rangeError(draft);

  return (
    <section aria-label="Date range">
      <div className="preset-row">
        {presets().map((p) => (
          <button
            key={p.key}
            type="button"
            className={p.start === range.start && p.end === range.end ? "is-selected" : "button-secondary"}
            aria-pressed={p.start === range.start && p.end === range.end}
            onClick={() => {
              onChange({ start: p.start, end: p.end });
              setDraft({ start: p.start, end: p.end });
            }}
          >
            {p.label}
          </button>
        ))}
      </div>
      <form
        className="preset-row"
        onSubmit={(event) => {
          event.preventDefault();
          if (!draftError) onChange(draft);
        }}
      >
        <label>
          From <input type="date" value={draft.start} onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
        </label>
        <label>
          To <input type="date" value={draft.end} onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
        </label>
        <button type="submit" className="button-secondary" disabled={Boolean(draftError)}>
          Show range
        </button>
        {draftError ? <span className="field__hint">{draftError}</span> : null}
      </form>
    </section>
  );
}
