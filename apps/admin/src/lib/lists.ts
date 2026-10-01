import { useEffect, useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { apiUrl } from "@/lib/auth";
import { adminFetch } from "@/lib/reports";

// Review 2026-09-30 R7: shared filter options for the paged admin lists.

export type StoryStatus = components["schemas"]["AdminStoryListItemOut"]["status"];

export const TELUGU_OPTIONS = [
  { value: "", label: "Any" },
  { value: "MISSING", label: "No Telugu" },
  { value: "PASSED", label: "Telugu passed QA" },
  { value: "FAILED", label: "Telugu failed QA" },
  { value: "PENDING", label: "Telugu awaiting QA" },
] as const;

export const STORY_STATUSES: { value: StoryStatus; label: string; tone: "ok" | "warn" | "danger" | "neutral" }[] = [
  { value: "PUBLISHED", label: "Published", tone: "ok" },
  { value: "UPDATED", label: "Updated", tone: "ok" },
  { value: "SCHEDULED", label: "Scheduled", tone: "neutral" },
  { value: "APPROVED", label: "Approved", tone: "neutral" },
  { value: "REVIEW_REQUIRED", label: "In review", tone: "warn" },
  { value: "AI_READY", label: "AI ready", tone: "neutral" },
  { value: "DRAFT", label: "Draft", tone: "neutral" },
  { value: "CORRECTION_PENDING", label: "Correction pending", tone: "warn" },
  { value: "RETRACTED", label: "Retracted", tone: "danger" },
  { value: "ARCHIVED", label: "Archived", tone: "neutral" },
];

export const statusInfo = (status: string) =>
  STORY_STATUSES.find((s) => s.value === status) ?? { value: status, label: status, tone: "neutral" as const };

export const teluguTone = (qa: string | null | undefined) =>
  qa === "PASSED" ? "ok" : qa === "FAILED" ? "danger" : qa === "PENDING" ? "warn" : "neutral";

export interface Option {
  value: string;
  label: string;
}

/** Active topics and all sources, for filter selects. Empty on failure: filters are optional. */
export function useFilterOptions(): { topics: Option[]; sources: Option[] } {
  const [topics, setTopics] = useState<Option[]>([]);
  const [sources, setSources] = useState<Option[]>([]);
  useEffect(() => {
    fetch(`${apiUrl()}/v1/config`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("topics"))))
      .then((body: { topics: { slug: string; name: string; active: boolean }[] }) =>
        setTopics(body.topics.filter((t) => t.active).map((t) => ({ value: t.slug, label: t.name })).sort((a, b) => a.label.localeCompare(b.label)))
      )
      .catch(() => setTopics([]));
    adminFetch<{ id: string; name: string }[]>("/v1/admin/sources")
      .then((rows) => setSources(rows.map((s) => ({ value: s.id, label: s.name })).sort((a, b) => a.label.localeCompare(b.label))))
      .catch(() => setSources([]));
  }, []);
  return { topics, sources };
}

/** Query string from the non-empty entries. */
export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value !== null && value !== undefined && value !== false) search.set(key, String(value));
  }
  return search.toString();
}
