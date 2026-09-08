# packages/contracts — OpenAPI-generated shared types. See docs/tickets/T04.md.

`openapi.json` and `types.gen.ts` are generated — do not hand-edit them.
Regenerate with `infra/scripts/generate_contracts.sh` (or `pnpm run
contracts:generate` from the repo root) after changing any FastAPI
request/response model in `apps/api/app/schemas.py`. CI fails the build if
the committed files are stale relative to the current API code.

`apps/web`, `apps/mobile`, and `apps/admin` should import API types only
from here (`import type { paths } from "@teluguvarta/contracts"`) — never
hand-roll parallel type definitions for API shapes.
