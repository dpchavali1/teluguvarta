import { NextResponse, type NextRequest } from "next/server";

// Nonce-based CSP for every admin page (ADR-028, review R11). Next reads the
// nonce from the request's Content-Security-Policy header and puts it on its
// own scripts; layout.tsx reads `x-nonce` for THEME_INIT_SCRIPT.
//
// style-src keeps 'unsafe-inline': React `style={...}` props render as inline
// style attributes, which a style nonce can't cover. Scripts are the XSS risk
// and those are nonce-only.

function originOf(url: string | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

function buildCsp(nonce: string): string {
  const connect = ["'self'", originOf(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")];
  // A DSN is https://<key>@<ingest host>/<project>; the error reporter posts to that host.
  connect.push(originOf(process.env.NEXT_PUBLIC_SENTRY_DSN));
  const dev = process.env.NODE_ENV === "development";
  return [
    "default-src 'self'",
    // Dev only: React Refresh needs eval.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src ${connect.filter(Boolean).join(" ")}${dev ? " ws:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = buildCsp(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Pages only: static assets and prefetches don't need a fresh nonce.
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|manifest.webmanifest).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
