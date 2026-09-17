#!/usr/bin/env bash
# T19 §16 baseline: the monthly restore test. Restores a backup.sh dump (or
# its .age-encrypted form, given BACKUP_AGE_IDENTITY) into a *freshly
# created* database — never over an existing one, so a restore test can
# never clobber real data by mistake — then runs Alembic against it to
# confirm the restored schema is actually at head (a restore that produces
# an unmigratable database is not a passing restore test).
#
# Usage: infra/scripts/restore.sh <dump-file> <target-db-name>
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dump_file="${1:?Usage: restore.sh <dump-file> <target-db-name>}"
target_db="${2:?Usage: restore.sh <dump-file> <target-db-name>}"

# P0-4: a wrong argument here runs DROP DATABASE ... WITH (FORCE) on whatever
# DATABASE_URL points at. Require an unmistakable restore-test name so a typo
# can't silently resolve to the real database.
if [[ "$target_db" != restore_* ]]; then
  echo "Refusing: target db '$target_db' must start with 'restore_' (restore.sh only ever targets disposable restore-test databases)" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  # shellcheck disable=SC1091
  [ -f "$repo_root/.env" ] && source "$repo_root/.env"
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set (used to reach the Postgres server, not the target db)" >&2
  exit 1
fi

plain_dump="$dump_file"
if [[ "$dump_file" == *.age ]]; then
  if [ -z "${BACKUP_AGE_IDENTITY:-}" ]; then
    echo "Decrypting $dump_file requires BACKUP_AGE_IDENTITY (path to the age identity/key file)" >&2
    exit 1
  fi
  plain_dump="${dump_file%.age}"
  age -d -i "$BACKUP_AGE_IDENTITY" -o "$plain_dump" "$dump_file"
fi

# Derive server connection args from DATABASE_URL (SQLAlchemy's
# "postgresql+psycopg://" scheme, normalized to plain "postgresql://" for
# psql/pg_restore), targeting the "postgres" maintenance db to create the
# fresh restore-test database.
libpq_url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
base_url="${libpq_url%/*}"
server_url="$base_url/postgres"
target_url="$base_url/$target_db"
# migrate.sh runs Alembic via SQLAlchemy, which needs the "+psycopg" scheme
# back — pg_restore/psql above need the plain one.
sqlalchemy_target_url="${target_url/postgresql:/postgresql+psycopg:}"

# The db DATABASE_URL itself points at (strip any "?query" suffix) — the
# thing this script must never DROP, restore_ prefix notwithstanding.
source_db="${libpq_url##*/}"
source_db="${source_db%%\?*}"
if [ "$target_db" = "$source_db" ]; then
  echo "Refusing: target db '$target_db' is the database DATABASE_URL points at — restore.sh must never target it" >&2
  exit 1
fi

psql "$server_url" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$target_db\" WITH (FORCE)"
psql "$server_url" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$target_db\""
pg_restore --dbname="$target_url" --no-owner --no-privileges "$plain_dump"

echo "Restored into '$target_db'. Verifying it is at Alembic head..."
DATABASE_URL="$sqlalchemy_target_url" "$repo_root/infra/scripts/migrate.sh" current | tee /tmp/restore_test_alembic_current.txt
if ! grep -q "(head)" /tmp/restore_test_alembic_current.txt; then
  echo "Restored database is NOT at Alembic head — restore test FAILED" >&2
  exit 1
fi
echo "Restore test passed: '$target_db' is at head."

if [[ "$dump_file" == *.age ]]; then
  rm -f "$plain_dump"
fi
