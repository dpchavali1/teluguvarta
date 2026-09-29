#!/usr/bin/env bash
# Nightly production backup for the single-VPS deploy (deploy.sh installs the
# cron entry once BACKUP_AGE_RECIPIENT is set in .env.prod).
#
#   sudo ./infra/deploy/backup-prod.sh
#
# pg_dump runs inside the postgres container and is piped straight into age,
# so no plaintext dump ever touches disk (P0-2: plaintext would expose
# users.mfa_secret). The age *identity* (private key) must live off this box —
# restore-drill.sh is the only thing that needs it, and only temporarily.
#
# Settings, all read from .env.prod:
#   BACKUP_AGE_RECIPIENT     required; age1... public key
#   BACKUP_STORAGE_BOX       optional; uXXXXXX@uXXXXXX.your-storagebox.de
#                            (off-box copy over SSH port 23; without it, backups
#                            stay on this server only)
#   BACKUP_SSH_KEY           default /root/.ssh/storagebox
#   BACKUP_KEEP_DAYS_LOCAL   default 14
#   BACKUP_KEEP_DAYS_REMOTE  default 30
#   BACKUP_HEALTHCHECK_URL   optional; pinged on success, <url>/fail on failure
#                            (healthchecks.io style), so a silent stop is noticed
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f infra/deploy/docker-compose.prod.yml --env-file "$ENV_FILE")
BACKUP_DIR="${BACKUP_DIR:-/var/backups/teluguvarta}"

env_get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }

recipient="$(env_get BACKUP_AGE_RECIPIENT)"
storage_box="$(env_get BACKUP_STORAGE_BOX)"
ssh_key="$(env_get BACKUP_SSH_KEY)"; ssh_key="${ssh_key:-/root/.ssh/storagebox}"
keep_local="$(env_get BACKUP_KEEP_DAYS_LOCAL)"; keep_local="${keep_local:-14}"
keep_remote="$(env_get BACKUP_KEEP_DAYS_REMOTE)"; keep_remote="${keep_remote:-30}"
healthcheck="$(env_get BACKUP_HEALTHCHECK_URL)"

ping_health() {
  [ -n "$healthcheck" ] && curl -fsS -m 10 --retry 3 "$healthcheck$1" >/dev/null || true
}
on_error() {
  echo "BACKUP FAILED (line $1)" >&2
  rm -f "${partial:-}"
  ping_health /fail
}
trap 'on_error $LINENO' ERR

[ -n "$recipient" ] || { echo "BACKUP_AGE_RECIPIENT is not set in $ENV_FILE — refusing to back up unencrypted" >&2; ping_health /fail; exit 1; }
command -v age >/dev/null || { echo "'age' is not installed (apt-get install age)" >&2; ping_health /fail; exit 1; }

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="teluguvarta_${timestamp}.dump.age"
partial="$BACKUP_DIR/.$name.partial"

# Custom format (-Fc): compressed and what pg_restore expects. pipefail makes a
# pg_dump failure fail the pipeline even though age exits 0.
"${COMPOSE[@]}" exec -T postgres pg_dump -U teluguvarta -d teluguvarta --format=custom \
  | age -r "$recipient" -o "$partial"
# An encrypted empty stream is ~200 bytes; a real dump is far larger.
[ "$(stat -c %s "$partial")" -gt 1024 ] || { echo "dump suspiciously small" >&2; false; }
mv "$partial" "$BACKUP_DIR/$name"
partial=""
echo "Wrote $BACKUP_DIR/$name ($(du -h "$BACKUP_DIR/$name" | cut -f1))"

# Names embed a sortable UTC timestamp, so retention compares names, not mtimes.
cutoff_name() { echo "teluguvarta_$(date -u -d "-$1 days" +%Y%m%dT%H%M%SZ).dump.age"; }

cutoff="$(cutoff_name "$keep_local")"
for f in "$BACKUP_DIR"/teluguvarta_*.dump.age; do
  if [ "$(basename "$f")" \< "$cutoff" ]; then
    rm -f "$f"
    echo "Pruned local $(basename "$f")"
  fi
done

if [ -n "$storage_box" ]; then
  ssh_opts=(-p 23 -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
  ssh "${ssh_opts[@]}" "$storage_box" mkdir -p teluguvarta >/dev/null 2>&1 || true
  # Copy only this run's file: never --delete, so a wiped local dir can't
  # propagate and erase the off-box copies.
  rsync -a -e "ssh ${ssh_opts[*]}" "$BACKUP_DIR/$name" "$storage_box:teluguvarta/"
  echo "Copied to $storage_box:teluguvarta/$name"

  cutoff="$(cutoff_name "$keep_remote")"
  ssh "${ssh_opts[@]}" "$storage_box" ls teluguvarta | tr -d '\r' | while read -r f; do
    case "$f" in teluguvarta_*.dump.age) ;; *) continue ;; esac
    if [ "$f" \< "$cutoff" ]; then
      ssh "${ssh_opts[@]}" "$storage_box" rm "teluguvarta/$f" </dev/null && echo "Pruned remote $f"
    fi
  done
else
  echo "BACKUP_STORAGE_BOX not set — backup kept on this server only"
fi

ping_health ""
