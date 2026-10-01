#!/usr/bin/env bash
# Records the outcome of a host-side operation in the ops_checks table, so
# admin Observability can show its age and failures (review 2026-09-30 R3).
#
#   ./infra/deploy/ops-record.sh CHECK ok|fail [detail]
#
# CHECK is one of BACKUP, OFFSITE_COPY, RESTORE_DRILL, MONITOR, ALERT_TEST
# (apps/api/app/ops_status.py). Best effort: it never fails its caller — a
# backup must not fail because Postgres was unreachable for the bookkeeping,
# and the healthchecks.io pings remain the alerting path.
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f "$repo_root/infra/deploy/docker-compose.prod.yml" --env-file "$ENV_FILE")

check="${1:-}"
outcome="${2:-}"
detail="${3:-}"
detail="${detail:0:500}"

case "$outcome" in
  ok) at=last_success_at; text=success_detail ;;
  fail) at=last_failure_at; text=failure_detail ;;
  *) echo "usage: $0 CHECK ok|fail [detail]" >&2; exit 0 ;;
esac

# psql interpolates :'var' only in SQL read from stdin, not in -c, and quotes
# it as a literal, so the detail text can't break out of the statement.
sql="INSERT INTO ops_checks (check_name, $at, $text, updated_at)
VALUES (:'check', now(), NULLIF(:'detail', ''), now())
ON CONFLICT (check_name) DO UPDATE SET $at = EXCLUDED.$at, $text = EXCLUDED.$text, updated_at = now();"

# timeout: a wedged Docker must not hold up the caller.
if ! printf '%s\n' "$sql" | timeout 30 "${COMPOSE[@]}" exec -T postgres \
    psql -U teluguvarta -d teluguvarta -v ON_ERROR_STOP=1 -q \
    -v check="$check" -v detail="$detail" >/dev/null 2>&1; then
  echo "ops-record: could not record $check $outcome" >&2
fi
exit 0
