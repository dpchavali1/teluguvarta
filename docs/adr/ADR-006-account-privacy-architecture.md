# ADR-006: Account/privacy architecture

- **Status**: proposed
- **Date**: 2026-09-08
- **Ticket**: T05 (binds T14, T15, T16, T19, S1, S2)

## Context

NON_NEGOTIABLES #9 requires browsing to work without login, always, and — if
account creation exists — deletion to be implemented both in-app and on the
public site. §16 adds: "no-account browsing by default" and a "cross-system
deletion job." §9.3 (launch checklist) is stricter still: "account deletion
is implemented before account creation is enabled." None of this says
whether end users get an *account* concept at all in V1, or what identifies
a "user" for `/v1/me/*` (preferences, saved stories, push tokens) if not an
account with a login.

This has to be settled now (T05, the admin-auth ticket) because it's a stop
condition under NON_NEGOTIABLES #11 — T04 already shipped `/v1/me/*`
endpoints and a `users` table with nullable `email`/`auth_provider` columns,
and T14/T15/T16/S1 all build on top of "who is this request for" without
resolving it themselves. This ADR is scoped to end-user identity/privacy
only — admin login is implemented directly in this ticket (JWT session,
RBAC, rate limiting; see `apps/api/app/routers/admin_auth.py`), not
gated on this ADR.

## Decision

**V1 ships with device-scoped, anonymous identity only — no end-user
login (no email/password, no OAuth, no magic link).** Concretely:

- On first use, the client (web/mobile) is issued an opaque, unguessable
  user token tied to one `users` row with `email`/`auth_provider(_id)` all
  `NULL`. That token is what `current_user`/`Authorization: Bearer` already
  expects (`apps/api/app/auth.py`) — T05 does not change `current_user`,
  it only resolves what "real verification" means for a later ticket.
- Preferences, saved stories, push tokens, and topic subscriptions
  (`/v1/me/*`) attach to that row. There is no cross-device sign-in in V1:
  losing the device/app storage loses the identity, by design, since there
  is no account to recover.
- **Account deletion** (`DELETE /v1/me/account`, already stubbed in T04) is
  a hard delete of the `users` row. Because `profiles`, `user_topics`,
  `notifications` etc. all declare `ON DELETE CASCADE` to `users.id` (T03
  schema), one row delete is sufficient — no separate "cross-system
  deletion job" needs building for V1's scope (that language in §16
  anticipates a future state with external systems like an email/ESP
  integration that V1 doesn't have yet).
- This is why "account deletion before account creation" (§9.3) is
  satisfied trivially: there is no account *creation* flow to gate — every
  client is auto-provisioned an anonymous identity, and deleting it is one
  cascading delete already covered by the schema.
- Push notification opt-in and topic/geography preferences work the same
  way for anonymous students (S1/S2) as for anyone else per NON_NEGOTIABLES
  #13 — no separate identity system for the student profile.

**Explicitly deferred, not decided here**: real accounts (email/OAuth login,
cross-device sync, account recovery). If product wants that later, it needs
a new ADR — it changes the privacy posture (`email` stops being always-NULL)
and likely needs its own consent/retention design per §16's "separate
analytics consent" language.

## Consequences

- Unblocks T14/T15 (they can issue an anonymous token during onboarding
  without building login UI) and T16 (ranking reads preferences off the
  same anonymous row).
- Simpler privacy story for launch: no passwords/PII to protect for the
  general public, no login-related support burden, satisfies "browsing
  works without login" trivially since there's never a login step.
- Harder later: adding real accounts is additive (new `auth_provider`
  values, a login endpoint analogous to admin's) but migrating *existing*
  anonymous users' data to a new account requires a linking flow this ADR
  doesn't design — revisit when there's an actual product need (e.g. real
  users requesting multi-device sync).
- Revisit this ADR if real usage shows a strong need for cross-device
  continuity before public launch — don't quietly bolt on login without a
  superseding decision. (There is no recruited-user pilot to gate this on —
  see `PROGRESS.md`'s 2026-09-16 pilot-removal entry.)

## Alternatives considered

- **Build full email/password or OAuth accounts now**: rejected — no ticket
  before T20 needs cross-device identity, and it's real scope (password
  reset, email verification, consent copy) NON_NEGOTIABLES #11 says not to
  invent without a requirement driving it.
- **No identity at all — pure stateless client-local storage**: rejected —
  `/v1/me/preferences`, saved stories, and push tokens (already in the T04
  OpenAPI contract) need a server-side row to attach to; some identity,
  even anonymous, is required.
