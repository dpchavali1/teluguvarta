"use client";

import { useEffect, useState } from "react";

import {
  DEFAULT_READING_PREFS,
  loadReadingPrefs,
  saveReadingPrefs,
  type ReadingPrefs,
} from "@/lib/readingPrefs";

const SIZE_LABELS = { small: "Small", default: "Default", large: "Large", xlarge: "Extra large" } as const;
const FONT_LABELS = { default: "Standard", serif: "Serif", mandali: "Mandali" } as const;
const STYLE_LABELS = { full: "Full", short: "Short" } as const;

function Group<K extends keyof ReadingPrefs>({
  legend, name, labels, prefs, onPick,
}: {
  legend: string; name: K; labels: Record<string, string>; prefs: ReadingPrefs; onPick: (name: K, value: string) => void;
}) {
  return (
    <fieldset className="onboarding__fieldset">
      <legend>{legend}</legend>
      {Object.entries(labels).map(([value, label]) => (
        <label key={value} className="onboarding__radio">
          <input type="radio" name={`reading-${name}`} value={value} checked={prefs[name] === value} onChange={() => onPick(name, value)} />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

export function ReadingControls() {
  const [prefs, setPrefs] = useState<ReadingPrefs>(DEFAULT_READING_PREFS);
  useEffect(() => setPrefs(loadReadingPrefs()), []);

  function pick<K extends keyof ReadingPrefs>(name: K, value: string) {
    const next = { ...prefs, [name]: value } as ReadingPrefs;
    setPrefs(next);
    saveReadingPrefs(next);
  }

  return (
    <section className="reading-controls" aria-labelledby="reading-controls-title">
      <h2 id="reading-controls-title">Reading</h2>
      <p className="onboarding__hint">Saved on this device. Text size builds on your browser&apos;s own font setting.</p>
      <Group legend="Text size" name="textSize" labels={SIZE_LABELS} prefs={prefs} onPick={pick} />
      <Group legend="Telugu font" name="teluguFont" labels={FONT_LABELS} prefs={prefs} onPick={pick} />
      <Group legend="Story length on cards" name="readingStyle" labels={STYLE_LABELS} prefs={prefs} onPick={pick} />
      <p className="reading-controls__preview" lang="te">తెలుగు వార్తలు — మీ భాషలో</p>
      <p className="reading-controls__preview">The Telugu world, thoughtfully edited.</p>
    </section>
  );
}
