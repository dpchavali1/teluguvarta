"use client";

import { useCallback, useEffect, useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { Badge, useToast } from "@/components/ui";
import { apiFetch, apiUrl } from "@/lib/auth";
import { age } from "@/lib/time";

type Switch = components["schemas"]["RuntimeSwitchOut"];

// ADR-031: what each switch does, in the admin's words.
const COPY: Record<Switch["key"], { title: string; on: string; off: string; waiting: string; pause: string }> = {
  ai: {
    title: "AI",
    on: "Writing and translating new stories.",
    off: "No AI calls, no AI spend. News is still collected; new stories wait until AI is resumed.",
    waiting: "waiting for AI",
    pause: "Pause AI"
  },
  auto_publish: {
    title: "Auto-publish",
    on: "Finished stories go live automatically. Sensitive stories still wait for a person.",
    off: "Nothing goes live on its own. Finished stories wait; stories you approve by hand still publish.",
    waiting: "waiting to publish",
    pause: "Pause auto-publish"
  },
  breaking: {
    title: "Breaking & death briefs",
    on: "Breaking and death stories confirmed by 2+ approved sources (or one trusted source) go live as source-text briefs. Retract one from its story page.",
    off: "Breaking and death stories wait for a person.",
    waiting: "waiting in review",
    pause: "Pause breaking briefs"
  }
};

/** Pause/resume controls for the dashboard. Only an ADMIN can flip them. */
export function PauseSwitches({ canEdit }: { canEdit: boolean }) {
  const toast = useToast();
  const [switches, setSwitches] = useState<Switch[] | null>(null);
  const [confirming, setConfirming] = useState<Switch["key"] | null>(null);
  const [saving, setSaving] = useState<Switch["key"] | null>(null);

  const load = useCallback(() => {
    apiFetch(`${apiUrl()}/v1/admin/switches`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Failed to load switches"))))
      .then(setSwitches)
      .catch(() => setSwitches(null));
  }, []);

  useEffect(load, [load]);

  async function flip(sw: Switch) {
    setSaving(sw.key);
    try {
      const response = await apiFetch(`${apiUrl()}/v1/admin/switches/${sw.key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !sw.enabled })
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(body?.error?.message ?? "Failed to update switch");
      }
      toast("ok", `${COPY[sw.key].title} ${sw.enabled ? "paused" : "resumed"}.`);
      load();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Failed to update switch");
    } finally {
      setSaving(null);
      setConfirming(null);
    }
  }

  if (!switches) return null;

  return (
    <section aria-labelledby="controls-heading">
      <h2 id="controls-heading">Controls</h2>
      <ul className="switch-list">
        {switches.map((sw) => {
          const copy = COPY[sw.key];
          const locked = !sw.env_allows;
          const status = locked ? "Off (server setting)" : sw.enabled ? "Running" : "Paused";
          const tone = sw.effective ? "ok" : "warn";
          return (
            <li key={sw.key} className="switch-row">
              <div className="switch-row__text">
                <p className="switch-row__title">
                  {copy.title} <Badge tone={tone}>{status}</Badge>
                </p>
                <p className="switch-row__note">
                  {locked
                    ? "Turned off on the server (AUTO_PUBLISH_GLOBAL), so every story goes to the review queue. Change it in .env.prod."
                    : sw.enabled
                      ? copy.on
                      : copy.off}
                  {!sw.effective && sw.waiting > 0 ? ` ${sw.waiting} ${copy.waiting}.` : ""}
                </p>
                {sw.updated_by && sw.updated_at ? (
                  <p className="switch-row__meta">
                    Last changed by {sw.updated_by} {age(sw.updated_at)} ago
                  </p>
                ) : null}
              </div>
              {canEdit && !locked ? (
                <div className="switch-row__actions">
                  {confirming === sw.key ? (
                    <>
                      <button type="button" disabled={saving === sw.key} onClick={() => flip(sw)}>
                        {sw.enabled ? `Yes, ${copy.pause.toLowerCase()}` : "Yes, resume"}
                      </button>
                      <button type="button" className="button-secondary" onClick={() => setConfirming(null)}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button type="button" className={sw.enabled ? "button-secondary" : undefined} onClick={() => setConfirming(sw.key)}>
                      {sw.enabled ? copy.pause : "Resume"}
                    </button>
                  )}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
