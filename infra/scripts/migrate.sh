#!/usr/bin/env bash
# Runs Alembic migrations (infra/migrations/) against DATABASE_URL.
# Usage: infra/scripts/migrate.sh [alembic-args...]  (defaults to "upgrade head")
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
api_dir="$repo_root/apps/api"

if [ ! -d "$api_dir/.venv" ]; then
  echo "apps/api/.venv not found — run: cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$api_dir/.venv/bin/activate"
cd "$api_dir"
if [ "$#" -eq 0 ]; then
  alembic upgrade head
else
  alembic "$@"
fi
