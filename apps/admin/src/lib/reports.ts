import type { components } from "@teluguvarta/contracts";

import { apiUrl, clearSession, getToken } from "@/lib/auth";

// ADR-029: private reader reports.
export type ReaderReport = components["schemas"]["AdminReaderReportOut"];
export type ReaderReportList = components["schemas"]["AdminReaderReportListOut"];
export type Resolution = components["schemas"]["AdminReaderReportResolveRequest"]["resolution"];

export const CATEGORY_LABELS: Record<ReaderReport["category"], string> = {
  FACTUAL_ERROR: "Factual error",
  TRANSLATION: "Translation",
  BROKEN_LINK: "Broken link",
  WRONG_IMAGE: "Wrong image",
  OFFENSIVE: "Offensive",
  OTHER: "Other",
};

export const RESOLUTIONS: { value: Resolution; label: string; help: string }[] = [
  { value: "CORRECTED", label: "Corrected", help: "Pick the correction you made on the story. Closes as resolved." },
  { value: "RETRACTED", label: "Retracted", help: "Retract the story first. Closes as resolved." },
  { value: "NO_CHANGE", label: "No change needed", help: "The story stands. Closes as dismissed." },
  { value: "DUPLICATE", label: "Duplicate", help: "Already handled through another report. Closes as dismissed." },
  { value: "SPAM", label: "Spam", help: "Not a real report. Closes as dismissed." },
];

export const resolutionLabel = (value: string | null | undefined) =>
  RESOLUTIONS.find((r) => r.value === value)?.label ?? "—";

export class SessionExpired extends Error {}

/** Authenticated admin request; clears the session on 401 and surfaces the API's error message. */
export async function adminFetch<T>(path: string, init: RequestInit = {}, failure = "Request failed"): Promise<T> {
  const token = getToken();
  if (!token) throw new SessionExpired("Not signed in");
  const response = await fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
  });
  if (response.status === 401) {
    clearSession();
    throw new SessionExpired("Session expired");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? failure);
  }
  return response.json() as Promise<T>;
}
