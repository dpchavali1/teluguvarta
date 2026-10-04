// ADR-046 §4: in-process sliding-window limiter for the public share-card
// route (PNG rendering is CPU work). Process-local, like the API limiter.
// The per-client key comes from a proxy header, which is only trustworthy once
// the perimeter (ADR-046 §3) is decided, so a global cap backstops a spoofed key.
const windows = new Map<string, number[]>();

export function allow(key: string, max: number, windowMs: number, now = Date.now()): boolean {
  const recent = (windows.get(key) ?? []).filter((t) => t > now - windowMs);
  if (recent.length >= max) {
    windows.set(key, recent);
    return false;
  }
  recent.push(now);
  windows.set(key, recent);
  if (windows.size > 5000) {
    for (const [k, v] of windows) if (v.every((t) => t <= now - windowMs)) windows.delete(k);
  }
  return true;
}

export function clientKey(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for");
  // Last hop is the one our own proxy appended; earlier hops are client-supplied.
  return forwarded?.split(",").at(-1)?.trim() || headers.get("x-real-ip") || "unknown";
}

export const SHARE_CARD_PER_CLIENT = { max: 20, windowMs: 60_000 };
export const SHARE_CARD_GLOBAL = { max: 300, windowMs: 60_000 };

export function shareCardAllowed(headers: Headers, now = Date.now()): boolean {
  return (
    allow(`card:${clientKey(headers)}`, SHARE_CARD_PER_CLIENT.max, SHARE_CARD_PER_CLIENT.windowMs, now) &&
    allow("card:*", SHARE_CARD_GLOBAL.max, SHARE_CARD_GLOBAL.windowMs, now)
  );
}
