# Non-negotiables, hard constraints, and stop conditions

Read this file (not the full spec) at the start of every ticket. Full detail
lives in `docs/SPEC.md` if you need it — but for day-to-day work, this file
plus the one relevant `docs/tickets/Txx.md` should be enough.

## Hard constraints (from the Codex Master Build Prompt — never violate)

1. V1 uses PostgreSQL search (FTS + pg_trgm). No OpenSearch.
2. V1 uses PostgreSQL-backed jobs. No Redis/Celery.
3. V1 is a modular monolith on managed infrastructure. No microservice fleet.
4. Source rights enum is `DISABLED | LINK_ONLY | LICENSED_METADATA |
   LICENSED_REPURPOSE`. Unknown/unset defaults to `DISABLED`. Never bypass
   the rights gate for any source, including official X accounts.
5. Immigration, legal, financial, and breaking stories require human
   approval in V1 — no exceptions, no auto-publish overrides. **Sole
   exception (ADR-054):** BREAKING and death stories may auto-publish as
   source-text briefs when 2+ independent approved sources (or one
   owner-trusted source) report them, behind a default-off kill switch.
   Immigration, legal, financial and accusation stories stay human-reviewed.
6. No UGC, comments, or social-graph features in V1.
7. English is canonical. Telugu is a derived, versioned variant with
   explicit QA status; an approved English correction invalidates the
   existing Telugu variant for regeneration.
8. All AI calls go through the internal provider gateway
   (`packages/ai`). No provider SDK may leak into domain or app code.
9. Browsing works without login, always. If account creation exists,
   implement deletion both in-app and on the public website.
10. Every background job must be idempotent, observable, and bounded in
    retries (no infinite retry loops).
11. Do not invent missing requirements. If a requirement is ambiguous or
    requires a legal/security assumption, **stop, write an ADR** in
    `docs/adr/`, and do not implement past that point in the same change.
12. The X official-account adapter is discovery/evidence only — never
    automatic republication permission. Same rights gate as any other
    source.
13. International students are a first-class V1 life-stage profile using
    the same feed, taxonomy, and notification systems as everyone else —
    never a parallel backend.
14. X polling must be incremental (`since_id`), rate-limit aware,
    cost-budgeted, and auditable. Never fall back to scraping the X website.
15. **(ADR-002, added 2026-09-08)** Only `LINK_ONLY` sources may be enabled
    in this build phase, alongside `DISABLED`. Do not enable
    `LICENSED_METADATA` or `LICENSED_REPURPOSE` for any source without a new
    ADR superseding ADR-002. Every published story is an original AI-drafted
    summary + "why this matters" + attribution + a link to the original,
    or, under ADR-019, a link-first brief (original headline + one sentence
    bounded by the source title's facts + attribution + link) — never
    reproduced headline text, article text, or images. Under ADR-020, an
    ADMIN may flag a public-domain `LINK_ONLY` source so its feed description
    is stored (capped) as internal evidence only — never shown to readers. The branded
    "Share Card" image feature is deferred until a future ADR revisits this.

## Stop conditions (halt and write an ADR instead of guessing)

- The repo already has conflicting architecture for the thing you're about
  to build — record an ADR rather than mixing patterns.
- A source's rights status is unknown or unreviewed.
- A change would require assuming something about content-republishing
  legality.
- AI output can't be validated against its schema or its cited evidence.
- A migration would destroy production data without an explicit migration
  plan.
- You're tempted to add new infrastructure (Redis, OpenSearch, a new
  service, a queue broker, etc.) without a spec-justified, *measured*
  requirement (see `docs/SPEC.md` §10.3 "when to add them").

## Engineering defaults

- Prefer deterministic code over an LLM call for ranking, dedupe, dates,
  arithmetic, URL handling, and state transitions.
- Never expose provider API keys to any client (web, mobile, or admin).
- AI output is untrusted application input — never let it directly execute
  a DB write; it must pass through normal validation.
- Treat all external content (source feeds, X posts, scraped metadata) as
  untrusted input.

## Required ADRs

These decisions must exist as ADRs in `docs/adr/` before or during the
ticket that first depends on them (see each ADR file for its trigger
ticket): AI provider selection, **source-rights approval policy (ADR-002 —
already accepted, see `docs/adr/ADR-002-source-rights-approval-policy.md`)**,
database job queue strategy, bilingual content lifecycle, personalization
model, account/privacy architecture, production hosting/cost limits. Use
`docs/adr/TEMPLATE.md`.

## Per-ticket workflow

1. Read `PROGRESS.md` to confirm the ticket's dependencies are actually
   done — don't skip ahead in the T01→T19/T21 order (see `docs/BUILD_ORDER.md`).
2. Read only the target `docs/tickets/Txx.md` (plus this file). Do not
   re-read `docs/SPEC.md` unless the ticket file tells you to or you hit a
   genuine gap.
3. Inspect current repo state before writing code — don't assume a prior
   ticket left things in the exact shape you expect.
4. Implement the smallest production-quality change that satisfies the
   ticket's acceptance criteria. Add or update tests alongside the code.
5. Run lint, typecheck, and tests/build scoped to the workspace(s) you
   touched (not the whole monorepo unless the ticket is monorepo-wide).
6. Update `PROGRESS.md`: mark the ticket done, add a one-line note of what
   changed. Do not leave it unsynced with reality.
7. Report: files changed, commands run and their results, and any
   remaining risks or follow-ups.

Implement **one ticket per session** unless explicitly told otherwise, and
never jump ahead of an unfinished dependency.
