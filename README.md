# Telugu Global

Free, English-first information platform for Telugu people worldwide —
global Telugu identity plus practical information about where the user
lives and the Indian places they call home. Launch wedge: USA Telugu NRIs.

## Status

Planning/scaffolding stage. No application code has been implemented yet —
see `PROGRESS.md` for exactly what's done. Directory skeleton exists under
`apps/` and `packages/` per the target monorepo layout.

## For engineers / Claude Code

Start with `CLAUDE.md`, then `docs/BUILD_ORDER.md` and `PROGRESS.md`. The
full product/architecture spec digest is `docs/SPEC.md`; day-to-day work
should only need `docs/NON_NEGOTIABLES.md` plus the specific
`docs/tickets/Txx.md` file being implemented.

```
docs/
  SPEC.md                 # condensed master spec — the authority
  NON_NEGOTIABLES.md       # hard constraints, stop conditions, workflow (read every session)
  BUILD_ORDER.md           # ticket sequence + dependencies
  CODEX_BUILD_PROMPT.md    # verbatim authoritative build prompt
  tickets/                 # one file per ticket (T01-T20, X1-X4, S1-S2)
  adr/                     # architecture decision records
apps/
  web/       # Next.js public site
  mobile/    # Expo iOS + Android
  api/       # FastAPI
  admin/     # Next.js admin
packages/
  contracts/ # OpenAPI-derived shared types
  ui/        # shared components/design tokens
  config/    # shared lint/tsconfig
  ai/        # AI provider gateway
  domain/    # shared business rules/types
infra/
  migrations/
  scripts/
tests/
  fixtures/
  e2e/
```

## Local setup

Not yet implemented — this section will be filled in by ticket T02 with the
actual clone → install → run instructions. Until then, see `docs/tickets/T01.md`
and `T02.md` for what's being built.

## Before writing product/legal-sensitive code

This spec is an engineering control set, not legal advice. Counsel must
review the operating entity, source licensing, privacy notices, advertising
model, India/U.S. exposure, and app-store submissions before any commercial
launch — see `docs/SPEC.md` §5 and §28.
