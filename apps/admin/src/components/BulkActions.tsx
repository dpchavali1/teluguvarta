"use client";

import { useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { useToast } from "@/components/ui";
import { getRole } from "@/lib/auth";
import { adminFetch } from "@/lib/reports";

// ADR-055: one action over the selected stories. The API checks each story
// against the single-story rules and reports the ones it skipped.
export type BulkAction = components["schemas"]["AdminBulkStoryRequest"]["action"];
type BulkResult = components["schemas"]["AdminBulkStoryOut"];

const LABELS: Record<BulkAction, { button: string; done: string }> = {
  reject: { button: "Reject to draft", done: "rejected to draft" },
  archive: { button: "Archive", done: "archived" },
  retract: { button: "Retract (take down)", done: "retracted" },
  restore: { button: "Restore to review", done: "sent back to review" },
  delete: { button: "Delete permanently", done: "deleted" }
};

export async function runBulk(action: BulkAction, storyIds: string[], reason: string | null): Promise<BulkResult> {
  return adminFetch<BulkResult>(
    "/v1/admin/stories/bulk",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, story_ids: storyIds, reason }) },
    `${LABELS[action].button} failed`
  );
}

export function BulkActions({
  selected,
  actions,
  onDone,
  onClearSelection
}: {
  selected: string[];
  actions: BulkAction[];
  onDone: () => void;
  onClearSelection: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState<BulkAction | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const isAdmin = getRole() === "ADMIN";
  const available = actions.filter((a) => a !== "delete" || isAdmin);

  if (selected.length === 0) return null;

  async function run(action: BulkAction) {
    setBusy(true);
    try {
      const result = await runBulk(action, selected, reason.trim() || null);
      const skipped = result.skipped.length;
      toast(
        skipped && !result.done.length ? "danger" : "ok",
        `${result.done.length} ${LABELS[action].done}` +
          (skipped ? ` · ${skipped} skipped (${[...new Set(result.skipped.map((s) => s.message))].slice(0, 2).join("; ")})` : "")
      );
      setReason("");
      setConfirming(null);
      setTyped("");
      onClearSelection();
      onDone();
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : "Bulk action failed");
    } finally {
      setBusy(false);
    }
  }

  const needsTyping = confirming === "delete";
  const reasonMissing = confirming === "delete" && !reason.trim();

  return (
    <section className="bulk-bar" aria-label="Bulk actions">
      <strong>{selected.length} selected</strong>
      <label>
        Reason{confirming === "delete" ? " (required)" : ""}
        <input type="text" value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} />
      </label>
      {confirming ? (
        <>
          <span role="alert">
            {LABELS[confirming].button} {selected.length} stor{selected.length === 1 ? "y" : "ies"}?
            {confirming === "delete" ? " This cannot be undone." : ""}
          </span>
          {needsTyping ? (
            <label>
              Type DELETE to confirm
              <input type="text" value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" />
            </label>
          ) : null}
          <button
            type="button"
            className={confirming === "delete" || confirming === "retract" ? "button-danger" : undefined}
            disabled={busy || reasonMissing || (needsTyping && typed !== "DELETE")}
            onClick={() => run(confirming)}
          >
            {busy ? "Working…" : `Confirm ${LABELS[confirming].button.toLowerCase()}`}
          </button>
          <button type="button" className="button-secondary" disabled={busy} onClick={() => { setConfirming(null); setTyped(""); }}>
            Cancel
          </button>
        </>
      ) : (
        <>
          {available.map((action) => (
            <button
              key={action}
              type="button"
              className={action === "delete" ? "button-danger" : "button-secondary"}
              onClick={() => setConfirming(action)}
            >
              {LABELS[action].button}
            </button>
          ))}
          <button type="button" className="button-secondary" onClick={onClearSelection}>
            Clear selection
          </button>
        </>
      )}
    </section>
  );
}
