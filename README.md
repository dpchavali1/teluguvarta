# Telugu Global

Free, English-first information platform for Telugu people worldwide —
global Telugu identity plus practical information about where the user
lives and the Indian places they call home. Launch wedge: USA Telugu NRIs.

## Status

Monorepo skeleton stood up (T01) — placeholder apps that boot, shared
tooling, and CI. No business logic yet. See `PROGRESS.md` for exactly
what's done.

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

Full local dev (Postgres, env vars, seed data) lands in T02. For now:

**Node workspaces** (web, admin, mobile, packages) — pnpm 10.x, Node 20+:

```
pnpm install
pnpm run lint        # all workspaces
pnpm run typecheck   # all workspaces
pnpm --filter @teluguvarta/web dev     # http://localhost:3000
pnpm --filter @teluguvarta/admin dev   # http://localhost:3001
pnpm --filter @teluguvarta/mobile start
```

**API** (FastAPI, Python 3.11+):

```
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload   # GET /health -> {"status": "ok"}
pytest
ruff check .
```

## Before writing product/legal-sensitive code

This spec is an engineering control set, not legal advice. Counsel must
review the operating entity, source licensing, privacy notices, advertising
model, India/U.S. exposure, and app-store submissions before any commercial
launch — see `docs/SPEC.md` §5 and §28.
