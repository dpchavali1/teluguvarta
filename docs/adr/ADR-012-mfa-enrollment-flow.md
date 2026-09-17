# ADR-012: First-login MFA enrollment flow

- **Status**: accepted
- **Date**: 2026-09-16
- **Ticket**: P0-3 (`docs/plans/gemini-hetzner-telugu-plan.md`)

## Context

MFA is enforced today only if `users.mfa_secret` happens to be set
(`app/routers/admin_auth.py`'s `login`); nothing forces enrollment, so an
admin who never ran `/mfa/setup` + `/mfa/enroll` logs in with password alone
and gets a full session token. The plan's naive fix — reject login outright
for EDITOR/ADMIN accounts with no `mfa_secret` — is not implementable as
stated: `/mfa/setup` and `/mfa/enroll` both require `current_admin`, and the
only way to obtain the token that dependency checks is the login endpoint
itself (`admin_auth.py`'s own module docstring says so). Rejecting login
before enrollment permanently locks out every existing admin the day it
ships, with no path to self-service recovery.

Per `NON_NEGOTIABLES.md` #11, this is exactly the kind of judgment call
(a session-scoping mechanism, not a one-line check) that gets an ADR rather
than an implicit choice buried in the login handler.

## Decision

Add a restricted **enrollment-scoped token**, issued instead of a full
session token when password verification succeeds for an account with no
`mfa_secret`:

- `create_admin_enrollment_token` mints a JWT carrying `"scope":
  "mfa_enrollment"` with a short TTL (5 minutes — long enough to scan a QR
  code and enter one TOTP code, short enough that a leaked token is not a
  standing credential).
- `current_admin` (the dependency guarding every other `/v1/admin/*` route)
  rejects any token with `scope == "mfa_enrollment"` with 403
  `MFA_ENROLLMENT_REQUIRED` — it never grants `AdminPrincipal` access to a
  route outside the enrollment flow.
- A new `current_admin_for_enrollment` dependency accepts *either* a full
  session token or an enrollment-scoped one, and is used only by
  `POST /mfa/setup` and `POST /mfa/enroll`. This is the only way an
  enrollment token is useful, and it's also how an already-enrolled admin
  re-enrolls a new device with a full session token — unchanged from today.
- Login for an account that already has `mfa_secret` set is unchanged: TOTP
  code required before any token issues.
- `AdminLoginResponse` gains `mfa_enrollment_required: bool` so the admin UI
  can route straight to the enrollment screen instead of treating the
  response as a normal successful login.

This closes the lockout gap without weakening the original intent (an
account with a TOTP secret can never skip the code) and without granting
the enrollment token any capability beyond finishing enrollment.

## Consequences

- Every admin without `mfa_secret` now gets a token that can only reach two
  endpoints, not a full session — this is an intentional behavior change
  from today's "password alone is a full session" and will require an admin
  UI update to handle `mfa_enrollment_required` (tracked outside this
  ticket; the API change ships regardless since it's the security fix).
- The enrollment token's 5-minute TTL means an admin who is interrupted
  mid-setup must log in again — acceptable friction for a rare, one-time
  flow.
- `GET /mfa` (status) and `DELETE /mfa` (disable) still require a full
  session token, per the plan's explicit "except /mfa/setup and
  /mfa/enroll" — an enrollment token cannot check status or disable MFA
  (there is nothing to disable yet).

## Alternatives considered

1. **Reject login outright with no fallback** (revision 4's fix) — rejected:
   locks out every existing admin permanently, no self-service recovery.
2. **Allow login through unauthenticated, add MFA later out-of-band** (e.g.
   an admin-only CLI script to seed `mfa_secret`) — rejected: reintroduces
   the exact bypass this ticket exists to close, and depends on a human
   remembering to run it before an admin's first login.
3. **A single token type with a "needs enrollment" claim, checked ad hoc by
   each route** — rejected in favor of a dedicated dependency: scattering
   the check across every route handler is easy to miss on a new route,
   where a shared dependency fails closed by construction.
