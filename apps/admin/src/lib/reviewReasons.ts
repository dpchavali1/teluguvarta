// Reasons that map to the always-human-reviewed categories in
// docs/NON_NEGOTIABLES.md get the danger tone so a reviewer can spot them
// without reading every row; everything else is a warn-tone pill.
export const DANGER_REASONS = new Set([
  "SENSITIVE_CATEGORY",
  "IMMIGRATION",
  "LEGAL",
  "FINANCIAL",
  "BREAKING"
]);

export function reasonTone(reason: string): "warn" | "danger" {
  return DANGER_REASONS.has(reason) ? "danger" : "warn";
}

// Plain-language "why is this held" for each gate in jobs/generate.py. Unknown
// codes fall back to the humanized code so a new gate is never hidden.
const REASON_HELP: Record<string, string> = {
  SENSITIVE_CATEGORY: "Sensitive topic — always needs a human (NON_NEGOTIABLES).",
  IMMIGRATION: "Immigration story — always human-reviewed.",
  LEGAL: "Legal story — always human-reviewed.",
  FINANCIAL: "Financial story — always human-reviewed.",
  BREAKING: "Breaking news — always human-reviewed.",
  HIGH_IMPORTANCE: "Marked high urgency, so a person checks it before it goes out.",
  LOW_CONFIDENCE_CLASSIFICATION: "The AI wasn't confident about the category.",
  LOW_CONFIDENCE_GENERATION: "The AI wasn't confident in its summary.",
  SIMILARITY_TO_SOURCE: "The summary is too close to the source text — rewrite it.",
  NO_PAID_PROVIDER: "This source's category needs paid AI and none is configured, so no draft was written."
};

export const reasonHelp = (reason: string) => REASON_HELP[reason.trim()] ?? humanize(reason.trim());

export function humanize(value: string): string {
  return value.replace(/_/g, " ").toLowerCase();
}
