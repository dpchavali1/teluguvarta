# Telugu Global

Free, English-first information platform for Telugu people worldwide —
global Telugu identity plus practical information about where the user
lives and the Indian places they call home. Launch wedge: USA Telugu NRIs.

## Status

Monorepo skeleton (T01), local env/Postgres/migration-runner scaffolding
(T02), the full V1 core database schema (T03), and the typed API contract
(T04) are done — every `docs/SPEC.md` §13 endpoint exists in FastAPI (stub
data, final shapes) with a standard error envelope, and `packages/contracts`
has generated TypeScript types other apps can import. No real business
logic yet (source ingestion, story generation, auth, editorial workflow —
T05+). See `PROGRESS.md` for exactly what's done.

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

```
cp .env.example .env          # fill in real values; never commit .env
docker compose up -d          # local Postgres 16 with pg_trgm enabled

cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd ../..

pnpm install
pnpm run migrate               # alembic upgrade head (infra/migrations/) — applies the full V1 schema
pnpm run seed                  # placeholder until T06 lands source/topic/user seed data
```

**Node workspaces** (web, admin, mobile, packages) — pnpm 10.x, Node 20+:

```
pnpm run lint        # all workspaces
pnpm run typecheck   # all workspaces
pnpm --filter @teluguvarta/web dev     # http://localhost:3000
pnpm --filter @teluguvarta/admin dev   # http://localhost:3001
pnpm --filter @teluguvarta/mobile start
```

**API** (FastAPI, Python 3.11+):

```
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload   # GET /health -> {"status": "ok"}
pytest
ruff check .
```

Migrations live in `infra/migrations/` (Alembic, wired via
`apps/api/alembic.ini`) and read `DATABASE_URL` from the repo-root `.env` —
run them with `pnpm run migrate` (or `infra/scripts/migrate.sh <alembic-args>`
for anything beyond `upgrade head`, e.g. `revision --autogenerate`). Seed
scripts live in `infra/scripts/`.

**API contract** (`packages/contracts`): request/response shapes are
Pydantic models in `apps/api/app/schemas.py`; TypeScript types are generated
from the live OpenAPI schema, never hand-written. After changing a model,
regenerate and commit:

```
pnpm run contracts:generate    # writes packages/contracts/{openapi.json,types.gen.ts}
```

CI fails the build if the committed files are stale relative to the API
code. `apps/web`, `apps/mobile`, `apps/admin` should import API types only
from `@teluguvarta/contracts` — never redeclare them.

## Before writing product/legal-sensitive code

This spec is an engineering control set, not legal advice. Counsel must
review the operating entity, source licensing, privacy notices, advertising
model, India/U.S. exposure, and app-store submissions before any commercial
launch — see `docs/SPEC.md` §5 and §28.
