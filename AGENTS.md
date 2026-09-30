# TTE — The Telugu Edit — instructions for Codex

**Authority**: `docs/SPEC.md` (V5.2) plus accepted ADRs in `docs/adr/` is the
sole product/architecture authority for this repo. Never load or act on any
V3/V4 spec if one surfaces — it's historical only. The literal
Codex/Codex master build prompt is in `docs/CODEX_BUILD_PROMPT.md` if
you need the verbatim authoritative wording.

## Start here, every session

1. `docs/BUILD_ORDER.md` — the strict ticket sequence and dependencies.
2. `PROGRESS.md` — what's actually done vs. what a ticket file assumes is
   done. Trust this over any assumption.
3. `docs/NON_NEGOTIABLES.md` — the 14 hard constraints, stop conditions, and
   the per-ticket workflow. Read this every session; it's short by design.
4. The one ticket file at `docs/tickets/Txx.md` you're implementing.

Do **not** re-read `docs/SPEC.md` end-to-end by default — it's the full
digest, kept for when a ticket file references a section you need more
detail on, or when you hit a genuine gap the ticket doesn't cover. Reading
it every session wastes context for no benefit once the tickets exist.

## The 5-second version of the hard constraints

Postgres search, no OpenSearch. Postgres job queue, no Redis/Celery. Modular
monolith, no microservices. Source rights default `DISABLED`, never bypass
the gate. Immigration/legal/financial/breaking always human-reviewed.
No UGC/comments in V1. English canonical, Telugu derived. AI only through
the internal gateway, never a provider SDK in domain code. Browsing works
without login. Jobs are idempotent, observable, bounded-retry. Don't invent
requirements — write an ADR and stop. X is discovery only, same rights gate,
no scraping fallback. Students are a first-class profile on the same
backend, not a parallel one. Full list with rationale:
`docs/NON_NEGOTIABLES.md`.

## Workflow

Implement **one ticket per session** in `docs/BUILD_ORDER.md` order, unless
told otherwise. For each ticket: inspect the current repo state → implement
the smallest production-quality change satisfying its acceptance criteria →
add/update tests → run lint/typecheck/tests/build scoped to what you
touched → update `PROGRESS.md` → report files changed, commands run, and
remaining risks. If something is ambiguous or requires a legal/architecture
assumption, stop and write an ADR (`docs/adr/TEMPLATE.md`) instead of
guessing.

## Token discipline for this repo specifically

- Ticket files are written to be self-contained — loading one plus
  `docs/NON_NEGOTIABLES.md` should be enough context to implement it. If you
  find yourself needing to re-read `docs/SPEC.md` repeatedly for the same
  ticket, that's a signal the ticket file is missing something — fix the
  ticket file too, not just the code.
- Don't dump full CI/build/test logs into a report — filter to
  pass/fail and any actual error lines.
- Keep `PROGRESS.md` current. It exists precisely so a new session (or a
  context-cleared one) doesn't have to re-derive project state from git log
  or conversation history.
