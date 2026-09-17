#!/usr/bin/env bash
# T19 §16 baseline: encrypted backups. Dumps DATABASE_URL with pg_dump's
# custom format (-Fc — required for restore.sh's selective/parallel restore
# and much smaller than plain SQL) into $BACKUP_DIR (default ./backups),
# then encrypts it at rest with age (a modern, auditable alternative to
# gpg — a single static binary, no keyring state) if BACKUP_AGE_RECIPIENT is
# set. Without a recipient configured this still produces a usable backup
# (dev/CI default) but is not "encrypted backups" per the release gate —
# ADR-007 is where production's actual key-management answer lives.
#
# P0-2: with APP_ENV=production, BACKUP_AGE_RECIPIENT is mandatory and this
# script refuses to run without it (fail closed) — an unencrypted dump is a
# permanent admin-MFA bypass (plaintext `users.mfa_secret`) sitting on disk.
# The matching age *identity* (private key) must be escrowed off-box (a
# secrets manager or password manager, never this repo, never the same host
# as the database/backups) — restore.sh is the only place that ever needs it.
#
# Usage: BACKUP_AGE_RECIPIENT=age1... infra/scripts/backup.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_dir="${BACKUP_DIR:-$repo_root/backups}"
mkdir -p "$backup_dir"

if [ -z "${DATABASE_URL:-}" ]; then
  # shellcheck disable=SC1091
  [ -f "$repo_root/.env" ] && source "$repo_root/.env"
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

if [ "${APP_ENV:-}" = "production" ] && [ -z "${BACKUP_AGE_RECIPIENT:-}" ]; then
  echo "APP_ENV=production requires BACKUP_AGE_RECIPIENT — refusing to write an unencrypted backup (P0-2)" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dump_path="$backup_dir/teluguvarta_${timestamp}.dump"

# DATABASE_URL uses SQLAlchemy's "postgresql+psycopg://" scheme — pg_dump
# only understands plain "postgresql://".
libpq_url="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

pg_dump --format=custom --file="$dump_path" "$libpq_url"
echo "Wrote $dump_path"

if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  if ! command -v age >/dev/null 2>&1; then
    echo "BACKUP_AGE_RECIPIENT is set but 'age' is not installed — see https://age-encryption.org" >&2
    exit 1
  fi
  age -r "$BACKUP_AGE_RECIPIENT" -o "${dump_path}.age" "$dump_path"
  rm "$dump_path"
  echo "Encrypted to ${dump_path}.age"
fi
