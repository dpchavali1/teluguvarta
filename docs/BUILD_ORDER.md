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
| 20 | T21 | T14, T15, T18 | Visual design refresh: shared design tokens + restyle web/mobile/admin for a trendier, easier-to-use UI (no IA/content changes) — see ADR-008 |

**Parallel/insertable tickets** (not in the strict spine, but gated by the
step named in "insert after"):
| Ticket | Insert after | Goal |
|---|---|---|
| X1 | T06 | X source registry fields (handle, priority, cadence, since_id, budget_class) |
| X2 | T07 | Incremental X fetch via `GET /2/users/{id}/tweets`, since_id, backoff |
| X3 | X2, T09 | X post → SourceItem → normal pipeline, dedupe by X post ID |
| X4 | X3, T18 | X account health/budget monitoring + guard in admin |
| X5 | X4, T14/T15, ADR-037 | Owner-requested official X updates in reader surfaces; placement/account approval pending. |
| S1 | T03/T14/T15 | Student life-stage profile + onboarding + Student Briefing view |
| S2 | S1 | Student topic taxonomy + independent student alerts |
| T13-repair | T13 | Accepted ADR-034 A: audited existing-Telugu withholding and separately requested bounded regeneration; production quality evidence remains separate. |
| T14-search | T14/T15 | Owner-authorized R12 follow-up: bounded newest-first search paging across API/contracts/web/app; relevance and regional tagging remain separate. |
| T19-maintenance | T19 | Owner-authorized mypy reduction and concise progress handoff; historical evidence retained. |
| UI15 | T21/UI14 | Owner-authorized rounded mobile controls and paired modern colors through shared tokens; device/release acceptance separate. |
| UI16 | T17/UI15 | Owner-authorized single Alerts setting, replacing duplicate notification destinations and clarifying controls; device acceptance separate. |
| UI17 | T12/T21 | Owner-authorized phone-first admin review layout: compact navigation, queue cards and safe evidence-before-decision ordering. |
| T19-release | T19/UI17 | Owner-authorized deployed-revision and route smoke checks for the VPS release gate. |
| T17-firebase | T17/ADR-039 | Owner-selected Firebase for native mobile push and separately consented mobile analytics; activate only after credentials, device proof, and the release gate. |
| UI01–UI14 | T14/T15 | Owner-authorized 2026-10-01 interface follow-ups, implemented sequentially; scope/status in `docs/reviews/2026-10-01-improvement-plan.md` and individual `docs/tickets/UIxx.md`. Device/release evidence remains separate from local implementation. |
| P01 | S1/S2/UI16 | Persona presets over explicit preferences. |
| P02 | UI16/T17-firebase | Digest, per-topic urgency, keyword follows, dual-timezone quiet hours, saved-story updates. |
| P03 | ADR-027/T16, ADR-043 | Multi-place location follows (done locally, see PROGRESS). |
| P04 | UI15 | Font size, Telugu font choice, short-summary mode. |
| P05 | ADR-040, P01, P03 | My Edit feed from explicit signals only. |
| P06 | T15 | Saved collections, reminders, notes, offline reading. |
| P07 | ADR-041 (per tracker), P02 | Visa bulletin, then exam/deadline trackers. |
| P08 | T15/UI15 | WhatsApp share card. |

## Vertical-slice milestone (before broadening scope)

After T09 (dedup/clustering) but conceptually validated once T11-T14 land for
a single source: one permitted source must produce a rights-approved story
that passes relevance/validation, gets EN+Telugu variants, appears in the
web feed, and can be opened/saved/attributed/corrected/retracted — all with
audit events. Don't add a second source or a new feature surface until this
slice works end-to-end.

## Pilot removed (2026-09-16)

There is no pre-build validation pilot and no post-hardening pilot ticket.
Product owner decided the product ships on engineering/editorial judgment
without a recruited-user validation phase — see the 2026-09-16 pilot-removal
entry in `docs/history/PROGRESS-through-T14-search-2026-10-01.md`. T20 (pilot)
no longer exists; do not reintroduce it or
gate any ticket on pilot data.
