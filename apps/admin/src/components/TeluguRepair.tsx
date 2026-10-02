"use client";

import { useState } from "react";
import type { components } from "@teluguvarta/contracts";
import { Field, useToast } from "@/components/ui";
import { apiFetch, apiUrl, getRole } from "@/lib/auth";

type RepairInfo = components["schemas"]["AdminTeluguRepairOut"];

export function TeluguRepair({ storyId, info, onSaved }: {
  storyId: string; info: RepairInfo; onSaved: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<"withhold" | "regenerate" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const canWithhold = Boolean(info.english_text_hash && info.telugu_text_hash);

  async function confirm() {
    if (!pending || busy || !reason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const body: components["schemas"]["AdminTeluguRepairRequest"] = {
        action: pending, reason: reason.trim(),
        english_text_hash: info.english_text_hash!, telugu_text_hash: info.telugu_text_hash!,
      };
      const response = await apiFetch(`${apiUrl()}/v1/admin/stories/${storyId}/repair-telugu`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        throw new Error(result?.error?.message ?? "Translation repair failed");
      }
      const message = pending === "withhold" ? "Telugu withheld. New responses use English." : "Regeneration requested. Readers see English while translation is pending.";
      toast("ok", message);
      setCompleted(pending === "regenerate");
      setPending(null);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation repair failed");
    } finally { setBusy(false); }
  }

  return (
    <section className="card" aria-labelledby="telugu-repair-title" lang="en">
      <h3 id="telugu-repair-title">Telugu quality and repair</h3>
      <p>Current automated checks are separate from the stored QA status. They do not establish translation fidelity.</p>
      {!canWithhold ? <p>English and Telugu variants are required to check or repair this translation.</p> :
        info.qa_issues?.length ? <ul>{info.qa_issues.map((issue, index) => <li style={{ overflowWrap: "anywhere" }} key={`${issue}-${index}`}>{issue}</li>)}</ul> :
          <p>No issues found by the current automated checks.</p>}
      <p>{info.resets_left} of 2 manual translation resets remaining, shared with exhausted-AI retries.</p>
      <p>Cached website and phone copies may show earlier text until their normal refresh. Regeneration waits when AI is paused or translation is disabled.</p>
      {getRole() === "ADMIN" && canWithhold ? <>
        <Field label="Translation repair reason (required)" htmlFor="telugu-repair-reason">
          <input id="telugu-repair-reason" value={reason} maxLength={500} disabled={busy || completed} onChange={(event) => { setReason(event.target.value); setPending(null); }} />
        </Field>
        {error ? <p role="alert">{error}</p> : null}
        {pending ? <>
          <p>{pending === "withhold" ? "Withhold this Telugu translation? Its text stays available to editors and readers get English." : "Regenerate this withheld translation? This removes its text and uses one manual reset. Normal AI and QA checks still apply."}</p>
          <div className="card__foot">
            <button type="button" disabled={busy || !reason.trim()} onClick={confirm}>Confirm {pending === "withhold" ? "withholding" : "regeneration"}</button>
            <button type="button" className="button-secondary" disabled={busy} onClick={() => setPending(null)}>Cancel repair</button>
          </div>
        </> : <div className="card__foot">
          <button type="button" className="button-secondary" disabled={busy || completed || !reason.trim()} onClick={() => setPending("withhold")}>Withhold Telugu</button>
          <button type="button" disabled={busy || completed || !reason.trim() || !info.can_regenerate} onClick={() => setPending("regenerate")}>Regenerate Telugu</button>
        </div>}
        <button type="button" className="button-secondary" disabled={busy} onClick={onSaved}>Reload translation status</button>
      </> : null}
    </section>
  );
}
