// P07/ADR-041: option lists mirror apps/api/app/content/visa_bulletin.py. The
// server silently drops anything outside them, so validate here too.
export const VISA_CATEGORIES = ["F1", "F2A", "F2B", "F3", "F4", "EB1", "EB2", "EB3", "EB3-OW", "EB4", "EB5"] as const;
export const VISA_COUNTRIES = ["ALL", "CHINA", "INDIA", "MEXICO", "PHILIPPINES"] as const;
export const MAX_VISA_FOLLOWS = 5;
export const MAX_EXAM_FOLLOWS = 10;

export type FollowedVisa = { category: string; country: string; alerts: boolean };
export type FollowedExam = { exam: string; alerts: boolean };

export const isVisaCategory = (value: string) => (VISA_CATEGORIES as readonly string[]).includes(value);
export const isVisaCountry = (value: string) => (VISA_COUNTRIES as readonly string[]).includes(value);
export const isExamKey = (value: string) => /^[A-Z0-9][A-Z0-9-]{1,19}$/.test(value);

export const visaLabel = (v: { category: string; country: string }) =>
  `${v.category} · ${v.country === "ALL" ? "All countries" : v.country[0] + v.country.slice(1).toLowerCase()}`;

export function cutoffLabel(cutoff: string): string {
  if (cutoff === "C") return "Current";
  if (cutoff === "U") return "Unavailable";
  return cutoff;
}
