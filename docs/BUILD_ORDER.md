# Build order

Strict sequence — do not start ticket N without N-1 (and any listed
cross-dependency) marked done in `PROGRESS.md`. Each ticket file lives at
`docs/tickets/Txx.md`.

| # | Ticket | Depends on | One-line goal |
|---|---|---|---|
| 1 | T01 | — | Initialize monorepo, workspaces, CI skeleton |
| 2 | T02 | T01 | Env/local setup, local Postgres, seed scripts |
| 3 | T03 | T02 | Full V1 DB schema + migrations + migration tests |
| 4 | T04 | T03 | OpenAPI contracts + generated TS client types |
| 5 | T05 | T04 | Admin authentication (roles, MFA-ready) |
| 6 | T06 | T03, T05 | Source registry CRUD + rights enum + kill switch |
| 7 | T07 | T06 | First 3-5 source adapters (seed config only) |
| 8 | T08 | T07 | Ingestion worker: Postgres job queue, retries, idempotency |
| 9 | T09 | T08 | Dedup + clustering |
| 10 | T10 | T04 | AI provider gateway (routing, schemas, cost telemetry) |
| 11 | T11 | T09, T10 | Story generation: classify, summarize, why-matters, evidence |
| 12 | T12 | T11 | Editorial workflow: review queue, approve/reject/retract/correct, audit |
| 13 | T13 | T11 | Bilingual EN/Telugu variants + QA + invalidation |
| 14 | T14 | T12, T13 | Web MVP (public site) |
| 15 | T15 | T12, T13 | Mobile MVP (Expo, iOS + Android) |
| 16 | T16 | T14, T15 | Personalization / ranking |
| 17 | T17 | T16 | Push notifications |
| 18 | T18 | T08..T17 | Observability: logging/metrics/alerts/AI cost dashboard |
| 19 | T19 | T18 | Hardening: security, accessibility, performance, deletion, app-store readiness |
| 20 | T20 | T19 | Pilot: 50-100 users, collect data, go/no-go for public launch |
| 21 | T21 | T14, T15, T18 | Visual design refresh: shared design tokens + restyle web/mobile/admin for a trendier, easier-to-use UI (no IA/content changes) — see ADR-008 |

**Parallel/insertable tickets** (not in the strict spine, but gated by the
step named in "insert after"):
| Ticket | Insert after | Goal |
|---|---|---|
| X1 | T06 | X source registry fields (handle, priority, cadence, since_id, budget_class) |
| X2 | T07 | Incremental X fetch via `GET /2/users/{id}/tweets`, since_id, backoff |
| X3 | X2, T09 | X post → SourceItem → normal pipeline, dedupe by X post ID |
| X4 | X3, T18 | X account health/budget monitoring + guard in admin |
| S1 | T03/T14/T15 | Student life-stage profile + onboarding + Student Briefing view |
| S2 | S1 | Student topic taxonomy + independent student alerts |

## Vertical-slice milestone (before broadening scope)

After T09 (dedup/clustering) but conceptually validated once T11-T14 land for
a single source: one permitted source must produce a rights-approved story
that passes relevance/validation, gets EN+Telugu variants, appears in the
web feed, and can be opened/saved/attributed/corrected/retracted — all with
audit events. Don't add a second source or a new feature surface until this
slice works end-to-end.

## Pre-build validation gate (before T01, product-owner responsibility)

Not a Claude Code ticket — a product decision gate: landing page + 3 example
personalized feeds → recruit 50-100 target USA Telugu NRI users → 14-day
manual/semi-automated digest pilot → measure opens/clicks/saves/opt-in/
recommend-willingness → only proceed to full V1 build (T01+) if repeat
weekly usage and qualitative utility are shown. If this hasn't happened yet,
flag it — don't silently skip it.
