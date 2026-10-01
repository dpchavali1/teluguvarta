import type { Tone } from "@/components/ui";

// Review 2026-09-30 R4: admin states what the gateway does at the current
// spend (`app.ai.budget.budget_mode`), not a blanket "paid AI is paused".
export type BudgetMode = "NORMAL" | "CLASSIFICATION_ONLY" | "PAID_STOPPED";

// Small totals keep four decimals, so a few cents of spend never shows as $0.00.
export function usd(n: number): string {
  return n > 0 && n < 1 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

export const BUDGET_MODE: Record<BudgetMode, { label: string; tone: Tone }> = {
  NORMAL: { label: "Normal", tone: "ok" },
  CLASSIFICATION_ONLY: { label: "Classification only", tone: "warn" },
  PAID_STOPPED: { label: "Paid calls stopped", tone: "danger" },
};

export function budgetModeMessage(mode: BudgetMode, budget: number | null, hardCap: number | null): string | null {
  if (mode === "CLASSIFICATION_ONLY") {
    const until = hardCap !== null ? `until the ${usd(hardCap)} hard cap` : "(no hard cap set)";
    return `Monthly AI budget${budget !== null ? ` (${usd(budget)})` : ""} reached — new summaries, why-it-matters and Telugu translations are stopped. Classification continues ${until}.`;
  }
  if (mode === "PAID_STOPPED") {
    return `Monthly AI hard cap${hardCap !== null ? ` (${usd(hardCap)})` : ""} reached — all paid AI calls are stopped, and so are summaries, why-it-matters and translations. Free-tier classification can still run.`;
  }
  return null;
}
