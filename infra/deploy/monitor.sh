#!/usr/bin/env bash
# Health check for the single-VPS deploy, run from the host's cron every 5
# minutes (deploy.sh installs /etc/cron.d/teluguvarta-monitor) and by deploy.sh
# itself as its post-deploy gate. Review 2026-09-29 #9.
#
#   sudo ./infra/deploy/monitor.sh
#
# Checks: API readiness (Postgres reachable), worker liveness
# (`python -m app.jobs.monitor`, run in the api container, not the worker),
# and that the web and admin apps answer. Exits 1 and prints each failure.
#
# Settings, read from .env.prod:
#   MONITOR_HEALTHCHECK_URL  optional; pinged on success, <url>/fail with the
#                            failures on failure (healthchecks.io style). The
#                            service alerts when pings stop, so it also catches
#                            the whole server going down, which nothing on the
#                            server can report.
# MONITOR_NO_PING=1 skips the ping (deploy.sh uses it while it waits).
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f infra/deploy/docker-compose.prod.yml --env-file "$ENV_FILE")

env_get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }

# deploy.sh holds this marker while it rebuilds and restarts; skip cron runs
# then, unless the marker is over 30 minutes old (a deploy that died).
if [ "${MONITOR_NO_PING:-0}" != "1" ] && [ -n "$(find /run/teluguvarta-deploying -mmin -30 2>/dev/null)" ]; then
  echo "$(date -u +%FT%TZ) deploy in progress, skipped"; exit 0
fi

failures=()
check_http() {
  curl -fsS -o /dev/null -m 15 "$2" 2>/dev/null || failures+=("$1: $2 not answering")
}

check_http API_NOT_READY http://127.0.0.1:18000/health/ready
check_http WEB_DOWN http://127.0.0.1:13000/
check_http ADMIN_DOWN http://127.0.0.1:13001/
# </dev/null: under `timeout`, compose is outside the terminal's foreground
# group, so reading the tty (as it does when deploy.sh runs interactively)
# stops it until the timeout fires.
if ! worker_out="$(timeout 60 "${COMPOSE[@]}" exec -T api python -m app.jobs.monitor 2>&1 </dev/null)"; then
  while IFS= read -r line; do [ -n "$line" ] && failures+=("$line"); done <<< "${worker_out:-WORKER_CHECK_FAILED: could not run}"
fi

healthcheck="$(env_get MONITOR_HEALTHCHECK_URL)"
ping_health() {
  [ "${MONITOR_NO_PING:-0}" = "1" ] || [ -z "$healthcheck" ] && return 0
  curl -fsS -m 10 --retry 3 --data-raw "$2" "$healthcheck$1" >/dev/null || true
}

if [ "${#failures[@]}" -gt 0 ]; then
  report="$(printf '%s\n' "${failures[@]}")"
  echo "$(date -u +%FT%TZ) UNHEALTHY"; echo "$report"
  ping_health /fail "$report"
  exit 1
fi
echo "$(date -u +%FT%TZ) ok"
ping_health "" ok
