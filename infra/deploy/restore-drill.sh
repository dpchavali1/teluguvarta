#!/usr/bin/env bash
# Production restore drill: proves a backup-prod.sh backup actually restores.
#
#   sudo BACKUP_AGE_IDENTITY=/root/drill-key.txt ./infra/deploy/restore-drill.sh [backup.dump.age]
#
# Defaults to the newest local backup. Restores into a throwaway database
# (restore_drill_<epoch>) inside the running postgres container — never over
# the live one — compares schema version and row counts against live, prints
# the restore time (RTO) and the backup's age (RPO), then drops the drill DB.
#
# BACKUP_AGE_IDENTITY is the age private key. It is escrowed off this box; copy
# it here for the drill only and delete it afterwards (the script reminds you).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f infra/deploy/docker-compose.prod.yml --env-file "$ENV_FILE")
BACKUP_DIR="${BACKUP_DIR:-/var/backups/teluguvarta}"

identity="${BACKUP_AGE_IDENTITY:?Set BACKUP_AGE_IDENTITY=/path/to/age-identity.txt}"
[ -f "$identity" ] || { echo "No identity file at $identity" >&2; exit 1; }
backup="${1:-}"
if [ -z "$backup" ]; then
  backup="$(ls -1 "$BACKUP_DIR"/teluguvarta_*.dump.age 2>/dev/null | sort | tail -1 || true)"
fi
[ -n "$backup" ] && [ -f "$backup" ] || { echo "No backup found (looked in $BACKUP_DIR)" >&2; exit 1; }

drill_db="restore_drill_$(date +%s)"
psql_in() { "${COMPOSE[@]}" exec -T postgres psql -U teluguvarta -v ON_ERROR_STOP=1 -Atq "$@"; }

cleanup() {
  "${COMPOSE[@]}" exec -T postgres rm -f /tmp/restore-drill.dump || true
  psql_in -d postgres -c "DROP DATABASE IF EXISTS \"$drill_db\" WITH (FORCE)" || true
  echo "Dropped $drill_db. Now delete the identity file: shred -u $identity"
}
trap cleanup EXIT

echo "==> Restoring $(basename "$backup") into $drill_db"
psql_in -d postgres -c "CREATE DATABASE \"$drill_db\""
start=$(date +%s)
# backup-prod.sh dumps to a pipe, so the archive has no data offsets; pg_restore
# can only find blocks in it by seeking, i.e. from a file, not from stdin. The
# plaintext lives inside the container for the drill only (removed on exit).
age -d -i "$identity" "$backup" \
  | "${COMPOSE[@]}" exec -T postgres sh -c 'umask 077; cat > /tmp/restore-drill.dump'
"${COMPOSE[@]}" exec -T postgres pg_restore -U teluguvarta -d "$drill_db" --no-owner --exit-on-error /tmp/restore-drill.dump
elapsed=$(( $(date +%s) - start ))

# Backup names carry their UTC timestamp: teluguvarta_YYYYMMDDTHHMMSSZ.dump.age
ts="$(basename "$backup" | sed -E 's/teluguvarta_([0-9]{8})T([0-9]{2})([0-9]{2})([0-9]{2})Z.*/\1 \2:\3:\4/')"
age_min=$(( ( $(date -u +%s) - $(date -u -d "$ts" +%s) ) / 60 ))

echo "==> Comparing against live"
fail=0
live_ver="$(psql_in -d teluguvarta -c 'SELECT version_num FROM alembic_version')"
drill_ver="$(psql_in -d "$drill_db" -c 'SELECT version_num FROM alembic_version')"
printf '%-22s live=%-14s restored=%s\n' alembic_version "$live_ver" "$drill_ver"
[ "$live_ver" = "$drill_ver" ] || { echo "   ^ schema differs (a migration ran after this backup?)"; fail=1; }

for table in users sources stories story_variants audit_events; do
  live="$(psql_in -d teluguvarta -c "SELECT count(*) FROM $table")"
  restored="$(psql_in -d "$drill_db" -c "SELECT count(*) FROM $table")"
  printf '%-22s live=%-14s restored=%s\n' "$table" "$live" "$restored"
  # Rows written since the backup are expected; a restored table that is
  # empty while live has data is not.
  if [ "$restored" -eq 0 ] && [ "$live" -gt 0 ]; then fail=1; fi
done

echo
echo "Restore time (RTO data point): ${elapsed}s"
echo "Backup age at drill (RPO data point): ${age_min} min"
if [ "$fail" -eq 0 ]; then echo "RESTORE DRILL PASSED"; else echo "RESTORE DRILL FAILED"; exit 1; fi
