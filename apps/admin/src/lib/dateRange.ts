// Inclusive ranges of UTC days, as the report endpoints take them.
export const MAX_DAYS = 93;
export const DAY_MS = 86_400_000;

export const isoDay = (d: Date) => d.toISOString().slice(0, 10);
export const shiftDays = (iso: string, days: number) => isoDay(new Date(Date.parse(`${iso}T00:00:00Z`) + days * DAY_MS));

export function presets(): { key: string; label: string; start: string; end: string }[] {
  const today = isoDay(new Date());
  const yesterday = shiftDays(today, -1);
  return [
    { key: "today", label: "Today", start: today, end: today },
    { key: "yesterday", label: "Yesterday", start: yesterday, end: yesterday },
    { key: "7d", label: "Last 7 days", start: shiftDays(today, -6), end: today },
    { key: "mtd", label: "Month to date", start: `${today.slice(0, 8)}01`, end: today },
    { key: "30d", label: "Last 30 days", start: shiftDays(today, -29), end: today },
  ];
}

export function rangeError(range: { start: string; end: string }): string | null {
  if (!range.start || !range.end) return "Choose both dates.";
  const days = Math.round((Date.parse(range.end) - Date.parse(range.start)) / DAY_MS) + 1;
  if (days < 1) return "Start must be on or before end.";
  return days > MAX_DAYS ? `At most ${MAX_DAYS} days.` : null;
}
