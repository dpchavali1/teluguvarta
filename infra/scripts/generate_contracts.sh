#!/usr/bin/env bash
# Regenerates packages/contracts/{openapi.json,types.gen.ts} from the FastAPI
# app's OpenAPI schema. CI runs this and then `git diff --exit-code` on the
# output to fail the build if someone changed an API model without
# regenerating (docs/tickets/T04.md).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
api_dir="$repo_root/apps/api"
contracts_dir="$repo_root/packages/contracts"

if [ ! -d "$api_dir/.venv" ]; then
  echo "apps/api/.venv not found — run: cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$api_dir/.venv/bin/activate"
(
  cd "$api_dir"
  python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))"
) > "$contracts_dir/openapi.json"

pnpm --filter @teluguvarta/contracts run generate
