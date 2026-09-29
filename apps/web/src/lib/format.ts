// Formatting helpers shared by server and client components. Dates are
// formatted in UTC so server-rendered and hydrated output always match;
// relative "2h ago" wording is applied client-side only (see TimeAgo.tsx).

const DATE_FMT = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const EDITION_FMT = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });

export function formatDate(iso: string): string {
  return DATE_FMT.format(new Date(iso));
}

export function formatEditionDate(date: Date = new Date()): string {
  return EDITION_FMT.format(date);
}

export function relativeTime(iso: string, now: number = Date.now()): string | null {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000);
  if (Number.isNaN(minutes) || minutes < 0) return null;
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return null;
}

// "https://www.reuters.com/world/..." -> "reuters.com"
export function sourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
