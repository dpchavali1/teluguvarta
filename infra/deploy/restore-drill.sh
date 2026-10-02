#!/usr/bin/env bash
# Production restore drill: proves a backup-prod.sh backup actually restores.
#
#   sudo BACKUP_AGE_IDENTITY=/root/drill-key.txt ./infra/deploy/restore-drill.sh [backup.dump.age]
#
# Defaults to the newest local backup. Restores into a throwaway database
# (restore_drill_<random suffix>) inside the running postgres container — never over
# the live one — compares schema version and row counts against live, prints
# the restore time (RTO) and the backup's age (RPO), then drops the drill DB.
#
# The outcome is recorded as RESTORE_DRILL in ops_checks (ops-record.sh), so
# admin Observability shows when the last drill passed and its RTO/RPO.
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

# Reserve a unique name on the host, even when two drills start together.
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/tte-restore-drill.XXXXXXXXXX")"
drill_db="restore_drill_${run_dir##*.}"
dump_path="/tmp/$drill_db.dump"
drill_db_created=0
summary="$(basename "$backup"): did not complete"
psql_in() { "${COMPOSE[@]}" exec -T postgres psql -U teluguvarta -v ON_ERROR_STOP=1 -Atq "$@"; }

cleanup() {
  local status=$? cleanup_failed=0
  trap - EXIT HUP INT TERM
  # A failed CREATE does not give this run ownership of an existing database.
  if [ "$drill_db_created" -eq 1 ]; then
    if ! "${COMPOSE[@]}" exec -T postgres rm -f "$dump_path"; then
      echo "CLEANUP FAILED: could not remove $dump_path" >&2
      cleanup_failed=1
    fi
    if psql_in -d postgres -c "DROP DATABASE \"$drill_db\" WITH (FORCE)"; then
      echo "Dropped $drill_db"
    else
      echo "CLEANUP FAILED: could not drop $drill_db" >&2
      cleanup_failed=1
    fi
  fi
  if ! rmdir "$run_dir"; then cleanup_failed=1; fi
  echo "Now delete the identity file: shred -u $identity"
  if [ "$status" -eq 0 ] && [ "$cleanup_failed" -eq 0 ]; then
    "$repo_root/infra/deploy/ops-record.sh" RESTORE_DRILL ok "$summary"
    echo "RESTORE DRILL PASSED"
  else
    "$repo_root/infra/deploy/ops-record.sh" RESTORE_DRILL fail "$summary; exit $status, cleanup failed=$cleanup_failed"
    echo "RESTORE DRILL FAILED" >&2
    [ "$status" -ne 0 ] || status=1
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

echo "==> Restoring $(basename "$backup") into $drill_db"
psql_in -d postgres -c "CREATE DATABASE \"$drill_db\""
drill_db_created=1
start=$(date +%s)
# backup-prod.sh dumps to a pipe, so the archive has no data offsets; pg_restore
# can only find blocks in it by seeking, i.e. from a file, not from stdin. The
# plaintext lives inside the container for the drill only (removed on exit).
age -d -i "$identity" "$backup" \
  | "${COMPOSE[@]}" exec -T postgres sh -c 'umask 077; cat > "$1"' sh "$dump_path"
"${COMPOSE[@]}" exec -T postgres pg_restore -U teluguvarta -d "$drill_db" --no-owner --exit-on-error "$dump_path"
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
summary="$(basename "$backup"): RTO ${elapsed}s, RPO ${age_min} min, schema $drill_ver"
if [ "$fail" -ne 0 ]; then
  summary="$summary; restored data did not match live"
  exit 1
fi
