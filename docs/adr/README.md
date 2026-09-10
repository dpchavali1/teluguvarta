# Architecture Decision Records

Copy `TEMPLATE.md` to `ADR-0NN-short-title.md` when you hit a stop condition
in `docs/NON_NEGOTIABLES.md` or make a decision the spec leaves open.

## Required ADRs (per spec §23) — create when their trigger ticket is reached

| ADR | Topic | Trigger ticket | Status |
|---|---|---|---|
| ADR-001 | AI provider selection | T10 | **accepted** — see [ADR-001](ADR-001-ai-provider-selection.md) |
| ADR-002 | Source-rights approval policy | T06 | **accepted** — see [ADR-002](ADR-002-source-rights-approval-policy.md) |
| ADR-003 | Database job queue strategy | T08 | **accepted** — see [ADR-003](ADR-003-database-job-queue-strategy.md) |
| ADR-004 | Bilingual content lifecycle | T13 | **accepted** — see [ADR-004](ADR-004-bilingual-content-lifecycle.md) |
| ADR-005 | Personalization model | T16 | **accepted** — see [ADR-005](ADR-005-personalization-model.md) |
| ADR-006 | Account/privacy architecture | T05 | **proposed** — see [ADR-006](ADR-006-account-privacy-architecture.md) |
| ADR-007 | Production hosting/cost limits | T19 | **accepted** — see [ADR-007](ADR-007-production-hosting-cost-limits.md) |
| ADR-008 | Visual design refresh (no new UI framework) | T21 | **accepted** — see [ADR-008](ADR-008-visual-design-refresh.md) |
| ADR-009 | Single design-token source, generated per surface | T22 | **proposed** — see [ADR-009](ADR-009-single-token-source.md) |

Update the Status column when an ADR file is created, and again when it's
accepted. Add ad-hoc ADRs below this table as they're written.

## Ad-hoc ADRs

(none yet — ADR-002 above was written ahead of T06 per an explicit product
decision to launch on `LINK_ONLY` sources only; see the ADR for context)
