#!/usr/bin/env bash
# Collects disaster-recovery and alerting evidence on the VPS (review
# 2026-09-30 R3; the checklist in OPERATIONS.md). Prints no secret values —
# settings are reported as set/unset — so the report can be pasted into
# PROGRESS.md. A copy is saved under /root/.
#
#   sudo ./infra/deploy/ops-evidence.sh                 # read-only report
#   sudo ./infra/deploy/ops-evidence.sh --test-alert    # also fire a test alert
#   sudo BACKUP_AGE_IDENTITY=/root/drill-key.txt ./infra/deploy/ops-evidence.sh --drill
#
# --test-alert posts a TEST failure to MONITOR_HEALTHCHECK_URL, asks whether the
# alert arrived, and records ALERT_TEST in ops_checks only on "y". The next
# monitor cron run (within 5 min) pings success and clears it.
# --drill runs restore-drill.sh against the newest local backup (see BACKUPS.md
# for copying the key over and shredding it afterwards).
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f infra/deploy/docker-compose.prod.yml --env-file "$ENV_FILE")
BACKUP_DIR="${BACKUP_DIR:-/var/backups/teluguvarta}"

test_alert=0; drill=0
for arg in "$@"; do
  case "$arg" in
    --test-alert) test_alert=1 ;;
    --drill) drill=1 ;;
    *) echo "unknown option $arg" >&2; exit 2 ;;
  esac
done

env_get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
set_or_not() { [ -n "$(env_get "$1")" ] && echo set || echo UNSET; }
# Minutes since a teluguvarta_YYYYMMDDTHHMMSSZ.dump.age name's timestamp.
name_age_min() {
  local ts
  ts="$(echo "$1" | sed -E 's/.*teluguvarta_([0-9]{8})T([0-9]{2})([0-9]{2})([0-9]{2})Z.*/\1 \2:\3:\4/')"
  echo $(( ( $(date -u +%s) - $(date -u -d "$ts" +%s) ) / 60 ))
}

report="${OPS_EVIDENCE_REPORT_DIR:-/root}/teluguvarta-ops-evidence-$(date -u +%Y%m%dT%H%M%SZ).txt"
report_status=0
exec > >(tee "$report") 2>&1

echo "# TTE ops evidence — $(date -u +%FT%TZ) — $(git rev-parse --short HEAD)"

echo; echo "## Settings (.env.prod)"
for key in BACKUP_AGE_RECIPIENT BACKUP_STORAGE_BOX BACKUP_HEALTHCHECK_URL MONITOR_HEALTHCHECK_URL; do
  printf '%-24s %s\n' "$key" "$(set_or_not "$key")"
done
printf '%-24s %s\n' "age installed" "$(command -v age >/dev/null && echo yes || echo NO)"
for f in /etc/cron.d/teluguvarta-backup /etc/cron.d/teluguvarta-monitor; do
  printf '%-24s %s\n' "$(basename "$f")" "$([ -f "$f" ] && echo installed || echo MISSING)"
done

echo; echo "## Local backups ($BACKUP_DIR)"
newest_local="$(ls -1 "$BACKUP_DIR"/teluguvarta_*.dump.age 2>/dev/null | sort | tail -1 || true)"
if [ -n "$newest_local" ]; then
  echo "count: $(ls -1 "$BACKUP_DIR"/teluguvarta_*.dump.age | wc -l)"
  echo "newest: $(basename "$newest_local") ($(du -h "$newest_local" | cut -f1)), $(name_age_min "$newest_local") min old"
else
  echo "NONE"
fi
if [ -f /var/log/teluguvarta-backup.log ]; then
  echo "failures in backup log: $(grep -c 'BACKUP FAILED' /var/log/teluguvarta-backup.log || true)"
  echo "last backup log lines:"; tail -4 /var/log/teluguvarta-backup.log | sed 's/^/  /'
else
  echo "no /var/log/teluguvarta-backup.log (cron has not run yet)"
fi

echo; echo "## Offsite backups (Storage Box)"
storage_box="$(env_get BACKUP_STORAGE_BOX)"
if [ -n "$storage_box" ]; then
  ssh_key="$(env_get BACKUP_SSH_KEY)"; ssh_key="${ssh_key:-/root/.ssh/storagebox}"
  if remote="$(ssh -p 23 -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$storage_box" ls teluguvarta </dev/null 2>&1)"; then
    remote="$(echo "$remote" | tr -d '\r' | grep -E '^teluguvarta_.*\.dump\.age$' | sort || true)"
    if [ -n "$remote" ]; then
      echo "count: $(echo "$remote" | wc -l)"
      newest_remote="$(echo "$remote" | tail -1)"
      echo "newest: $newest_remote, $(name_age_min "$newest_remote") min old"
    else
      echo "NONE on the Storage Box"
    fi
  else
    echo "could not list the Storage Box: $(echo "$remote" | tail -1)"
  fi
else
  echo "BACKUP_STORAGE_BOX unset — no offsite copy"
fi

echo; echo "## Monitor"
if [ -f /var/log/teluguvarta-monitor.log ]; then
  echo "unhealthy runs in last 288 (~24h): $(tail -288 /var/log/teluguvarta-monitor.log | grep -c UNHEALTHY || true)"
  echo "last line: $(tail -1 /var/log/teluguvarta-monitor.log)"
else
  echo "no /var/log/teluguvarta-monitor.log"
fi

if [ "$drill" -eq 1 ]; then
  echo; echo "## Restore drill"
  if ! "$repo_root/infra/deploy/restore-drill.sh" </dev/null; then
    echo "(restore drill exited non-zero)"
    report_status=1
  fi
fi

if [ "$test_alert" -eq 1 ]; then
  echo; echo "## Alert test"
  url="$(env_get MONITOR_HEALTHCHECK_URL)"
  if [ -z "$url" ]; then
    echo "MONITOR_HEALTHCHECK_URL unset — cannot test"
    report_status=1
  elif curl -fsS -m 10 --retry 3 --data-raw "TEST from ops-evidence.sh — not a real outage" "$url/fail" >/dev/null; then
    sent="$(date -u +%FT%TZ)"
    echo "Test failure posted at $sent. Check your email/phone for the healthchecks.io alert."
    read -r -p "Did the alert arrive? [y/N] " answer </dev/tty
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
      "$repo_root/infra/deploy/ops-record.sh" ALERT_TEST ok "monitor test alert sent $sent, receipt confirmed by owner"
      echo "ALERT TEST CONFIRMED"
    else
      "$repo_root/infra/deploy/ops-record.sh" ALERT_TEST fail "monitor test alert sent $sent, not received"
      echo "ALERT TEST NOT RECEIVED — check the healthchecks.io integration"
      report_status=1
    fi
    curl -fsS -m 10 --retry 3 "$url" >/dev/null || true
  else
    echo "could not reach MONITOR_HEALTHCHECK_URL"
    report_status=1
  fi
fi

echo; echo "## ops_checks (what admin Observability shows)"
"${COMPOSE[@]}" exec -T postgres psql -U teluguvarta -d teluguvarta -P pager=off -c \
  "SELECT check_name, last_success_at, success_detail, last_failure_at, failure_detail FROM ops_checks ORDER BY check_name" \
  </dev/null 2>&1 || echo "(could not read ops_checks — is migration e7c2a9d4f1b6 deployed?)"

echo; echo "Not checkable from here: a copy of .env.prod kept off the server (password manager)."
echo "Report saved to $report"
exit "$report_status"
