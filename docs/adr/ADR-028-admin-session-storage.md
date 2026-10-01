# ADR-028: Admin session storage and revocation

- **Status**: accepted (option A, owner 2026-09-30)
- **Date**: 2026-09-30
- **Ticket**: review #15 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

The admin app keeps its access token (a 30-minute HS256 JWT, `ADMIN_JWT_EXPIRE_MINUTES`)
in `localStorage` (`apps/admin/src/lib/auth.ts`) and sends it as a bearer header. Any
script that runs on the admin origin can read it and use it from anywhere until it expires.
The admin app sends no Content-Security-Policy, so nothing limits where an injected script
can load from or send data to.

Review #15 already changed the API so every admin request re-reads the account: a
deleted or demoted account loses access at once, and the stored role is enforced, not the
token's claim. A stolen token for an account that is still active works until it expires,
and there is no way to revoke a single session or log out server-side.

The spec is silent on admin session mechanics, and each option below changes the
admin/API contract and the deployment's cookie domain, so this isn't a call to make
while implementing.

## Decision (owner chose A, 2026-09-30)

**Recommended: A.** HttpOnly session cookie, with sessions stored server-side.

- Login (after MFA) creates an `admin_sessions` row (id, user, created, last seen,
  expires, revoked_at) and sets `Set-Cookie: tte_admin=<random id>; HttpOnly; Secure;
  SameSite=Strict; Domain=<api host>; Path=/v1/admin`. There is no JWT in the browser.
- `current_admin` looks up the session (the account check already happens per
  request), with an idle timeout (30 min) and an absolute one (12 h).
- Logout and "sign out everywhere" set `revoked_at`. Deleting or demoting an account
  revokes its sessions.
- CSRF: `SameSite=Strict`, plus a required custom header (`X-TTE-Admin: 1`) on
  state-changing requests, which a cross-site form can't send. CORS stays limited to the
  admin origin with credentials.
- Add a CSP to the admin app anyway: `default-src 'self'`, `connect-src` = the API
  origin, `img-src 'self' data:`, `object-src 'none'`, `base-uri 'self'`,
  `frame-ancestors 'none'`, and nonce-based `script-src` through Next middleware (the
  theme-init inline script takes the nonce).

**B.** Keep the bearer token, and harden around it: the nonce CSP above, a TTL cut to
10–15 minutes with refresh, and a `token_version` column on `users`, checked per request
and bumped on logout or demotion.

## Consequences

A: token theft by XSS stops (the cookie can't be read from script). An XSS can still
act from inside the page while it's open, which is why the CSP comes too. This costs
one table and a migration, a CORS-with-credentials setup, and a cookie domain shared by
`admin.` and `api.` (both are on the same site, so `SameSite=Strict` works). Admin API
tests move from bearer headers to cookies.

B: smaller change. A stolen token still works from anywhere until it expires or is
revoked, and the CSP becomes the main defense.

Either way: until one ships, the residual risk is that an XSS on the admin origin can
steal a token that works for up to 30 minutes. Admin renders story text through React
(escaped) and has no `dangerouslySetInnerHTML` apart from the fixed theme-init script,
so this is an exposure path, not a known hole.

## Alternatives considered

- Keep the token in memory only (lost on reload, so the editor re-logs in with MFA on
  every refresh). Rejected: bad editor UX, and an XSS can still read it from memory.
- A Backend-for-Frontend proxy in the admin Next app that holds the token server-side.
  Rejected for now: it adds a hop and state to the admin container, and A gets the same
  result with less.
