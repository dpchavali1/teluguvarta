// Compact durations for a dense workbench: "45m", "3h", "20d".
export function duration(seconds: number): string {
  const minutes = Math.max(0, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours}h` : `${Math.round(hours / 24)}d`;
}

export function age(iso: string): string {
  return duration((Date.now() - new Date(iso).getTime()) / 1000);
}

export function ago(iso: string | null): string {
  return iso ? `${age(iso)} ago` : "—";
}

// A pending job older than this means nothing is draining the queue.
export const STALE_QUEUE_SECONDS = 30 * 60;
