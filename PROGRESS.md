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
| T02 Env + local setup | not started | |
| T03 Database schema | not started | |
| T04 OpenAPI contracts | not started | |
| T05 Admin authentication | not started | |
| T06 Source registry | not started | |
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
| ADR-006 Account/privacy architecture | not started |
| ADR-007 Production hosting/cost limits | not started |

## Changelog

(newest first — one line per ticket completion)

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
