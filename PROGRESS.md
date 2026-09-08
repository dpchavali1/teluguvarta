# Progress tracker

Update this file at the end of every ticket. This is the source of truth for
"what's actually done" — trust it over assumptions, git log archaeology, or
prior conversation history.

**Pre-build validation gate** (product decision, not a ticket — see
`docs/BUILD_ORDER.md`): NOT STARTED.

## Main spine

| Ticket | Status | Notes |
|---|---|---|
| T01 Initialize monorepo | **done** | pnpm workspaces (web/admin/mobile/packages) + FastAPI api; CI on push/PR |
| T02 Env + local setup | **done** | `.env.example`, docker-compose Postgres 16 + pg_trgm, Alembic wired into `infra/migrations/`, seed placeholder, README local-setup rewritten |
| T03 Database schema | **done** | Single migration `0c23c235e618` creates all 17 §12 entities + `alembic_version`; `sources.rights_status` and `stories.status` are native Postgres enums; story transitions enforced by a `BEFORE UPDATE` trigger; `pnpm run migrate` + pytest against real Postgres (Homebrew, local only) both pass |
| T04 OpenAPI contracts | **done** | All 21 §13 endpoints live in FastAPI (stub data), standard error envelope via shared exception handlers, `packages/contracts` types generated from the OpenAPI schema with a CI drift check |
| T05 Admin authentication | **done** | JWT login (`POST /v1/admin/auth/login`), `role` column on `users` (EDITOR/ADMIN) with RBAC, rate-limited via `admin_login_attempts`; ADR-006 written (proposed) |
| T06 Source registry | **done** | `sources` expanded to full §6.2 field list via migration `69110b7cfd3d`; `/v1/admin/sources` CRUD enforces ADR-002 (only DISABLED/LINK_ONLY reachable, `RIGHTS_TIER_NOT_ENABLED` otherwise) and requires rights evidence (`rights_evidence_url`/`rights_reviewed_at`/`reviewer`) plus `ADMIN` role to enable a source (`RIGHTS_EVIDENCE_REQUIRED`/`FORBIDDEN`); every create/update writes an `AuditEvent`; read-only `GET /v1/admin/kill-switches` surfaces the §15 `AUTO_PUBLISH_*` env flags (no publish logic to gate yet — T12); ADR-002 addended with the approval-role/second-approver/evidence-expiry decisions |
| T07 First source adapters | not started | |
| T08 Ingestion worker | not started | |
| T09 Dedup + clustering | not started | |
| T10 AI provider gateway | not started | |
| T11 Story generation | not started | |
| T12 Editorial workflow | not started | |
| T13 Bilingual variants | not started | |
| T14 Web MVP | not started | |
| T15 Mobile MVP | not started | |
| T16 Personalization | not started | |
| T17 Push notifications | not started | |
| T18 Observability | not started | |
| T19 Hardening | not started | |
| T20 Pilot | not started | |

## X adapter

| Ticket | Status | Notes |
|---|---|---|
| X1 X source registry fields | not started | |
| X2 Incremental X fetch | not started | |
| X3 X post to story pipeline | not started | |
| X4 X monitoring/budget guard | not started | |

## Student experience

| Ticket | Status | Notes |
|---|---|---|
| S1 Student life-stage profile | not started | |
| S2 Student topics/alerts | not started | |

## ADR status

Mirrors `docs/adr/README.md` — keep both in sync.

| ADR | Status |
|---|---|
| ADR-001 AI provider selection | not started |
| ADR-002 Source-rights approval policy | **accepted** |
| ADR-003 Database job queue strategy | not started |
| ADR-004 Bilingual content lifecycle | not started |
| ADR-005 Personalization model | not started |
| ADR-006 Account/privacy architecture | **proposed** |
| ADR-007 Production hosting/cost limits | not started |

## Changelog

(newest first — one line per ticket completion)

- 2026-09-08: T05 done — admin auth is real, replacing T04's stub. New
  migration `infra/migrations/versions/8f1a2c9d4b3e_admin_auth.py` adds
  `role`/`password_hash`/`mfa_secret`/`last_login_at` to `users` (staff use
  the same table as everyone else, since `review_tasks.reviewer_id` /
  `corrections.created_by` already reference `users.id` — a `NULL` role
  means an ordinary end user) plus `admin_login_attempts` for rate
  limiting. `POST /v1/admin/auth/login` (`apps/api/app/routers/
  admin_auth.py`, no `current_admin` dependency — that's how you get the
  token that dependency checks) verifies a bcrypt password hash and issues
  a short-lived (`ADMIN_JWT_EXPIRE_MINUTES`, default 30 min) HS256 JWT
  carrying a `role` claim; `current_admin` (`apps/api/app/auth.py`) now
  decodes and verifies that JWT and requires `role` in `{EDITOR, ADMIN}`
  instead of just checking a bearer token is present. Rate limiting is a
  plain indexed Postgres query over `admin_login_attempts` (5 attempts /
  15 min per email) — deliberately not Redis, per NON_NEGOTIABLES. Added
  `app/db.py` (lazy per-request `DATABASE_URL` → engine, cached by URL —
  this is the first ticket needing a live DB connection from the API
  process itself) and `app/models.py` (SQLAlchemy ORM for `User`,
  `AdminLoginAttempt` — only the columns app code touches, not a mirror of
  every migration column). `infra/scripts/seed.py` now seeds one admin
  user from `ADMIN_SEED_EMAIL`/`ADMIN_SEED_PASSWORD` (idempotent — updates
  the password hash if the row exists). New deps: `pyjwt`, `bcrypt`.
  **ADR-006 (account/privacy architecture)** written as `proposed`
  (`docs/adr/ADR-006-account-privacy-architecture.md`): V1 end users get
  device-scoped anonymous identity only (no login/OAuth), so
  `DELETE /v1/me/account` is a single cascading row delete and "account
  deletion before account creation" is satisfied trivially — no login flow
  exists to gate. `current_user`/`/v1/me/*` remain the T04 stub;
  implementing that anonymous-token issuance is for T14/T15, not this
  ticket, which is admin-only per its own scope note. New tests
  (`apps/api/tests/test_admin_auth.py`, 7 cases): login success + the
  issued token unlocking `/v1/admin/*`, wrong password, unknown email, a
  token forged with a non-admin role rejected 403, an expired token
  rejected 401, and rate-limiting (both that the 6th attempt in the window
  is rejected 429, and that it doesn't leak across different emails) —
  seeded via direct DB inserts rather than real wall-clock waits or firing
  5 real requests. Also added `POST /v1/admin/auth/login` to
  `test_api_contract.py`'s expected-endpoints list. Verified: `pytest` (22
  passed, real Postgres via the existing `migrated_database` fixture,
  including a manual `alembic upgrade head` / `downgrade -1` / `upgrade
  head` round-trip against local Postgres), `ruff check .` clean, `pnpm run
  lint`/`typecheck` clean repo-wide, `packages/contracts` regenerated
  (`openapi.json`/`types.gen.ts`) and committed. Not yet done/risks: MFA
  itself is deferred (ticket explicitly allows "MFA-ready" over MFA this
  round) — `mfa_secret` column exists but nothing reads/writes it yet, so a
  later ticket must add the actual second factor before this fully
  satisfies §16's "MFA for admin sessions" baseline; no admin login UI in
  `apps/admin` yet (out of scope — the ticket's acceptance criterion is
  "a seeded admin user can log in and reach `apps/admin`" via the API, and
  `apps/admin` has no pages built yet at all, pre-dating this ticket).
- 2026-09-08: T04 done — all 21 §13 endpoints implemented in FastAPI with
  final request/response shapes (`apps/api/app/schemas.py`) but stub data,
  since T06+ (source registry, ingestion, story generation) haven't landed:
  public (`home`, `stories`, `stories/{slug}`, `stories/{slug}/share-meta`,
  `topics/{slug}`, `search`, `config`), authenticated `/v1/me/*`, and
  `/v1/admin/*`. Auth is intentionally stubbed (`apps/api/app/auth.py`) —
  both `current_user`/`current_admin` only check for a bearer token, no
  real verification or role check; a comment flags that T05 must replace
  the body of both before ship. Standard error envelope
  (`{"error": {"code","message","request_id"}}`) is one set of exception
  handlers (`apps/api/app/errors.py`) covering `APIError` (raised from
  routes), 404s, 422 validation errors, and unhandled 500s, plus a
  `X-Request-ID` middleware — not per-endpoint code. `packages/contracts`
  now has real generated output (`openapi.json`, `types.gen.ts` via
  `openapi-typescript`) instead of the `export {}` stub; regenerate with
  `pnpm run contracts:generate` (`infra/scripts/generate_contracts.sh`).
  Added a `contracts` CI job that regenerates and `git diff --exit-code`s
  the committed files, plus typechecks the package — fails the build on
  drift per the ticket's acceptance criteria. New tests
  (`apps/api/tests/test_api_contract.py`): OpenAPI schema validates
  (`openapi-spec-validator`), every §13 endpoint is registered, and the
  error envelope/auth-gate behavior is exercised end-to-end via
  `TestClient`. Verified: `pytest` (15 passed), `ruff check .` clean,
  `pnpm run lint`/`typecheck` clean repo-wide (now includes
  `packages/contracts`'s own `tsc --noEmit`). Added a
  `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` entry so
  FastAPI's idiomatic `Depends()`-in-default-args pattern doesn't trip
  B008. Not yet done: `apps/web`/`apps/mobile`/`apps/admin` don't call the
  API or import `@teluguvarta/contracts` yet (no page needs it before T14/
  T15) — the rule to import types only from there is for when they do.
- 2026-09-08: T03 done — one Alembic migration
  (`infra/migrations/versions/0c23c235e618_core_data_model.py`) implements
  every §12 entity (`users` through `audit_events`, plural table names to
  dodge the `user` reserved word). `sources.rights_status` and
  `stories.status` are native Postgres enums; `rights_status` defaults to
  `DISABLED` at the column level (NON_NEGOTIABLES #4). Legal `stories.status`
  transitions (`DRAFT -> AI_READY -> REVIEW_REQUIRED -> APPROVED ->
  SCHEDULED -> PUBLISHED -> UPDATED`, `PUBLISHED -> RETRACTED`, `UPDATED ->
  CORRECTION_PENDING -> UPDATED`) are enforced by a `BEFORE UPDATE` trigger
  (`enforce_story_status_transition`) rather than app code, since there's no
  app/domain layer yet for a guarded transition function to live in — a
  choice noted in the migration's docstring per the ticket's instruction.
  Required indexes present: unique `stories.canonical_slug`, unique
  `source_items(source_id, external_id)`, `jobs(status, run_after)`, and
  `gin`/`pg_trgm` indexes on `story_variants.headline`/`summary`. Added
  `jobs.lock_expiry`/`dedupe_key` and `notifications.notification_key`
  beyond the bare §12 field list because the ticket text and §14's stated
  dedupe rule require them. New pytest suite
  (`apps/api/tests/{conftest.py,test_schema.py}`) spins up throw-away
  Postgres databases per test (via a new `scratch_database`/
  `migrated_database` fixture pair) to verify: all tables exist after
  `alembic upgrade head`; upgrade+downgrade round-trips cleanly to empty;
  `rights_status` defaults to `DISABLED` and rejects invalid enum values;
  illegal story transitions raise `CheckViolation` and legal ones succeed.
  Tests skip (not fail) when no Postgres is reachable. CI's `api` job now
  runs a `postgres:16-alpine` service container so these run in CI, not
  just locally. Verified end-to-end this session by installing
  `postgresql@16` via Homebrew locally (with the user's explicit go-ahead,
  since that's a persistent change to their machine) — `alembic upgrade
  head`, `alembic downgrade base`, and `pytest` (7 passed) all ran clean
  against it; `ruff check .` clean. The Homebrew Postgres install and the
  `teluguvarta` role/db it created were left in place on the user's machine
  (not uninstalled) since T02's docker-compose Postgres is the intended
  long-term local setup — either works going forward.
- 2026-09-08: T02 done — `.env.example` at repo root covers every var named
  in `docs/SPEC.md` (`_USD`/`_ENABLED`/`_GLOBAL`) plus DB, AI provider
  (placeholder key, name only — ADR-001 not yet decided), push (FCM/APNs/
  Expo), object storage, and Sentry. `docker-compose.yml` runs Postgres 16
  with `pg_trgm` created via `infra/postgres/init/01-extensions.sql`.
  Alembic is wired into `infra/migrations/` (`apps/api/alembic.ini`,
  `script_location` points there); `infra/migrations/env.py` loads
  `DATABASE_URL` from repo-root `.env` via `python-dotenv` and fails fast
  with a clear message if unset — no schema/revisions yet, that's T03.
  `infra/scripts/migrate.sh` wraps `alembic` (activates the api venv);
  `infra/scripts/seed.py` is a no-op placeholder until T03/T06. Root
  `package.json` gained `pnpm run migrate` / `pnpm run seed`. README local
  setup section rewritten with the full clone→env→compose→install→migrate
  flow. Verified: `ruff check .` and `pytest` clean in `apps/api`; `pnpm run
  lint`/`typecheck` clean repo-wide; `migrate.sh` correctly loads `.env` and
  reaches the DB-connect step (confirmed via clean connection-refused error)
  — **not fully end-to-end verified**, since this sandbox has neither
  Docker nor a local Postgres and installing Postgres via Homebrew would be
  a persistent change to the user's machine outside repo scope; a real dev
  machine with Docker should run `docker compose up -d && pnpm run
  migrate` to confirm before trusting this blindly.
- 2026-09-08: T01 done — pnpm workspace root (`package.json`,
  `pnpm-workspace.yaml`), shared `packages/config` (base tsconfig +
  eslint), stub `packages/{contracts,domain,ai,ui}`. `apps/web` and
  `apps/admin` are minimal Next.js 14 App Router apps (build + lint +
  typecheck clean). `apps/mobile` is a minimal Expo/React Native app
  (typecheck clean; not build-tested, no native toolchain in this
  environment). `apps/api` is FastAPI with `/health` (verified 200 via
  uvicorn) + one pytest test + ruff clean; requires Python 3.11+ (local env
  only had 3.10, used the 3.13 install instead). CI
  (`.github/workflows/ci.yml`) runs pnpm install/lint/typecheck and
  pip install/ruff/pytest on push+PR. Fixed a stray leading `\` in
  `.gitignore` that broke `ruff check .`. README local-setup section
  filled in with real install/run/test commands (T02 will still add
  Postgres/env/seed).
- 2026-09-08: ADR-002 accepted — V1 restricted to `LINK_ONLY` sources only
  (AI-written original summary + why-matters + attribution + source link;
  no reproduced headlines/text/images). `LICENSED_METADATA`/
  `LICENSED_REPURPOSE` and the Share Card image feature are deferred.
  Threaded into `NON_NEGOTIABLES.md`, `SPEC.md`, and tickets T06/T07/T11/
  T14/T15.
- 2026-09-08: Repo scaffolded — planning docs, ticket breakdown, monorepo
  directory skeleton, ADR template created. No implementation tickets
  started yet.
