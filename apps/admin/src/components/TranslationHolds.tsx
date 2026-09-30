"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiUrl, getRole, getToken } from "@/lib/auth";

// ADR-025 option 3: translations whose AI retries ran out. The story keeps
// serving English, so without this list nobody would notice.
type AiHold = {
  story_id: string;
  stage: "GENERATE" | "TRANSLATE";
  story_status: string;
  headline: string | null;
  last_status: string | null;
  updated_at: string;
  resets_left: number;
};

export function TranslationHolds() {
  const [holds, setHolds] = useState<AiHold[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch(`${apiUrl()}/v1/admin/ai-holds`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Couldn't load AI holds"))))
      .then((all: AiHold[]) => setHolds(all.filter((h) => h.stage === "TRANSLATE")))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => load(), [load]);

  async function retry(storyId: string) {
    const reason = window.prompt("Reason for retrying the translation (recorded in the audit log):")?.trim();
    if (!reason) return;
    setBusy(storyId);
    setError(null);
    try {
      const response = await fetch(`${apiUrl()}/v1/admin/stories/${storyId}/retry-ai`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ stage: "TRANSLATE", reason }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? "Retry failed");
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setBusy(null);
    }
  }

  if (holds === null && !error) return null;
  return (
    <section aria-labelledby="translation-holds">
      <h2 id="translation-holds">Telugu translations that failed</h2>
      {error ? <p role="alert">{error}</p> : null}
      {holds && holds.length === 0 ? <p>None — every translation finished or is still being retried.</p> : null}
      {holds && holds.length > 0 ? (
        <ul>
          {holds.map((hold) => (
            <li key={hold.story_id}>
              <Link href={`/review/${hold.story_id}`}>{hold.headline ?? hold.story_id}</Link>{" "}
              <span className="field__hint">
                {hold.story_status.toLowerCase()} · last result {hold.last_status ?? "unknown"} · {hold.resets_left} retries left
              </span>{" "}
              {getRole() === "ADMIN" && hold.resets_left > 0 ? (
                <button type="button" className="button-secondary" disabled={busy !== null} onClick={() => retry(hold.story_id)}>
                  Retry translation
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
