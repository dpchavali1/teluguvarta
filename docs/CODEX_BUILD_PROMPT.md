# Codex / Claude Code master build prompt (authoritative, verbatim)

This is the literal first-instruction text for any coding agent (Codex or
Claude Code) working on this repo, per spec V5.2 §22. Paste this as-is when
starting a fresh session that has no prior context, or use it to sanity
check that `CLAUDE.md` hasn't drifted from it.

> You are the primary implementation agent for the Telugu Global project.
> Treat this V5 specification as the only product and architecture
> authority. Do not resurrect superseded V3/V4 architecture.
>
> Hard constraints:
> 1. V1 uses PostgreSQL search; no OpenSearch.
> 2. V1 uses PostgreSQL-backed jobs; no Redis/Celery.
> 3. V1 is a modular monolith with managed infrastructure.
> 4. News source rights enforced by DISABLED | LINK_ONLY | LICENSED_METADATA
>    | LICENSED_REPURPOSE. Unknown defaults to DISABLED. Never bypass the
>    rights gate.
> 5. Immigration, legal, financial and breaking stories require human
>    approval in V1.
> 6. No UGC/comments/social features in V1.
> 7. English is canonical; Telugu is a derived variant with explicit status
>    and invalidation on English correction.
> 8. All AI calls go through an internal provider gateway. No provider SDK
>    may leak into domain code.
> 9. Browsing works without login. If account creation exists, implement
>    deletion in-app and through the public website.
> 10. Every background job must be idempotent, observable and bounded in
>     retry.
> 11. Do not invent missing requirements. Create an ADR for ambiguous
>     design choices and stop before implementing material legal/security
>     assumptions.
> 12. V1 supports a curated X official-account adapter through the X API. X
>     is discovery/evidence, not automatic republication permission.
>     Unknown rights default to DISABLED.
> 13. International students are a first-class V1 life-stage profile using
>     the same feed, taxonomy and notification systems.
> 14. X polling must be incremental, rate-limit aware, cost-budgeted and
>     auditable; never fall back to website scraping.
>
> Implementation order: T01→T02→T03→T04→T05→T06→T07→T08→T09→T10→T11→T12→
> T13→T14→T15→T16→T17→T18→T19→T20.
>
> For each ticket: inspect current repo state first; implement the smallest
> production-quality change; add/update tests; run lint, typecheck,
> unit/integration tests and builds relevant to the change; do not silently
> change the architecture; report changed files, commands run, failures and
> remaining risks.
>
> First task: implement T01 only. Do not implement later tickets in the
> same step unless the repository already contains a validated
> T01-equivalent foundation.

In this repo, `CLAUDE.md` operationalizes the same rules with pointers to
`docs/NON_NEGOTIABLES.md`, `docs/BUILD_ORDER.md`, and `docs/tickets/`. Use
whichever is more convenient — they must never diverge in substance. If you
change one, update the other.
