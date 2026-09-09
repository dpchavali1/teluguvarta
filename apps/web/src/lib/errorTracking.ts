"use client";

/**
 * T18 client-side error tracking — see
 * `apps/admin/src/lib/errorTracking.ts` for the identical approach and
 * rationale (plain Sentry HTTP envelope, no SDK dependency, no-op without
 * `NEXT_PUBLIC_SENTRY_DSN`).
 */

function parseDsn(dsn: string): { storeUrl: string; publicKey: string } | null {
  try {
    const url = new URL(dsn);
    if (!url.username || url.pathname === "/") return null;
    const projectId = url.pathname.replace(/^\//, "");
    return {
      storeUrl: `${url.protocol}//${url.host}/api/${projectId}/store/`,
      publicKey: url.username,
    };
  } catch {
    return null;
  }
}

export function captureException(error: unknown, context: Record<string, string> = {}): void {
  // eslint-disable-next-line no-console
  console.error("[error-tracking]", error, context);

  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;
  const parsed = parseDsn(dsn);
  if (!parsed) return;

  const message = error instanceof Error ? error.message : String(error);
  const stack = error instanceof Error ? error.stack : undefined;

  fetch(parsed.storeUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Sentry-Auth": `Sentry sentry_version=7, sentry_client=teluguvarta-web/1.0, sentry_key=${parsed.publicKey}`,
    },
    body: JSON.stringify({
      event_id: crypto.randomUUID().replace(/-/g, ""),
      timestamp: Date.now() / 1000,
      platform: "javascript",
      tags: context,
      extra: context,
      exception: { values: [{ type: error instanceof Error ? error.name : "Error", value: message, stacktrace: stack }] },
    }),
  }).catch(() => {
    // Delivery failure must never mask the original error.
  });
}

export function installGlobalErrorTracking(context: Record<string, string> = {}): void {
  if (typeof window === "undefined") return;
  window.addEventListener("error", (event) => captureException(event.error ?? event.message, context));
  window.addEventListener("unhandledrejection", (event) => captureException(event.reason, context));
}
