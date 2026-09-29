#!/usr/bin/env bash
# One-shot, re-runnable deploy for a single Ubuntu/Debian VPS.
#
#   sudo ACME_EMAIL=you@example.com ./infra/deploy/deploy.sh
#
# The public website (apps/web) is NOT deployed here: host it on Vercel.
# This server runs Postgres, the API, the worker and the admin app in Docker,
# routed through the host's nginx (nginx-setup.sh; certs via certbot).
# Firewall changes are opt-in (UFW_SETUP=1) since the box may be shared.
# DOMAIN is optional: without one, hostnames are derived from the server IP via
# sslip.io (api.1-2-3-4.sslip.io), which still gets real HTTPS certificates.
# After deploying the site on Vercel, tell the API its URL (CORS + share links):
#   sudo WEB_URL=https://your-site.vercel.app ./infra/deploy/deploy.sh
#
# First run: installs Docker, opens ports 22/80/443, generates secrets into
# .env.prod, builds, migrates, seeds an admin user, starts everything.
# Re-runs: git pull, rebuild + migrate + restart with the existing .env.prod (secrets
# are never regenerated). With your own DOMAIN, first point A records for
# api and admin at this server (Cloudflare SSL mode: Full (strict)).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

# Pull the latest main first (skip with NO_PULL=1, or when not a git checkout).
# Re-exec afterwards because this very script may have just been updated.
if [ -d .git ] && [ "${NO_PULL:-0}" != "1" ] && [ -z "${DEPLOY_PULLED:-}" ]; then
  echo "==> Pulling latest from origin/main"
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  echo "    now at $(git log -1 --format='%h %s')"
  DEPLOY_PULLED=1 exec "$repo_root/infra/deploy/deploy.sh" "$@"
fi
ENV_FILE="$repo_root/.env.prod"
COMPOSE=(docker compose -f infra/deploy/docker-compose.prod.yml --env-file "$ENV_FILE")

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)." >&2; exit 1; }

# --- 1. host setup -----------------------------------------------------------
if ! command -v docker >/dev/null; then
  echo "==> Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi

if [ "${UFW_SETUP:-0}" = "1" ] && { command -v ufw >/dev/null || apt-get install -y -qq ufw >/dev/null 2>&1; }; then
  ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null
  echo "==> Firewall: only 22, 80, 443 open"
fi

# Next.js builds need memory; add swap on small boxes.
if [ "$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)" -lt 3500 ] && ! swapon --show | grep -q .; then
  echo "==> Adding 2G swap"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- 2. secrets / config -----------------------------------------------------
first_run=0
needs_seed=0
if [ ! -f "$ENV_FILE" ]; then
  first_run=1
  if [ -z "${DOMAIN:-}" ]; then
    ip="$(curl -4 -fsS https://api.ipify.org)"
    DOMAIN="${ip//./-}.sslip.io"
    echo "==> No DOMAIN given; using $DOMAIN"
  fi
  WEB_URL="${WEB_URL:-http://localhost:3000}"
  : "${ACME_EMAIL:?Set ACME_EMAIL=you@example.com}"
  pg_pass="$(openssl rand -hex 24)"
  admin_pass="$(openssl rand -base64 18 | tr -d '/+=')"
  umask 077
  cat > "$ENV_FILE" <<EOF
DOMAIN=$DOMAIN
ACME_EMAIL=$ACME_EMAIL
APP_ENV=production
POSTGRES_PASSWORD=$pg_pass
DATABASE_URL=postgresql+psycopg://teluguvarta:$pg_pass@postgres:5432/teluguvarta
WEB_URL=$WEB_URL
CORS_ALLOWED_ORIGINS=https://admin.$DOMAIN,$WEB_URL
PUBLIC_WEB_URL=$WEB_URL
NEXT_PUBLIC_WEB_URL=$WEB_URL
NEXT_PUBLIC_API_URL=https://api.$DOMAIN
ADMIN_JWT_SECRET=$(openssl rand -hex 32)
ADMIN_JWT_EXPIRE_MINUTES=30
MFA_SECRET_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
ADMIN_SEED_EMAIL=admin@$DOMAIN
ADMIN_SEED_PASSWORD=$admin_pass
SEED_DEMO_STORY=0
AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH=true
AUTO_PUBLISH_GLOBAL=false
AUTO_PUBLISH_CATEGORY_IMMIGRATION=false
AI_TRANSLATION_ENABLED=false
PUSH_NOTIFICATIONS_ENABLED=false
AI_REVIEW_P1_STORIES=true
MONTHLY_AI_BUDGET_USD=150
DAILY_AI_ALERT_USD=10
MONTHLY_INFRA_BUDGET_USD=200
# Fill in, then re-run this script:
AI_OPENAI_API_KEY=
AI_ANTHROPIC_API_KEY=
AI_GEMINI_API_KEY=
AI_FREE_TIER_ENABLED=0
X_API_BEARER_TOKEN=
SENTRY_DSN=
ALERT_WEBHOOK_URL=
# Backups (infra/deploy/BACKUPS.md): nightly cron is installed once the age key is set.
BACKUP_AGE_RECIPIENT=
BACKUP_STORAGE_BOX=
BACKUP_HEALTHCHECK_URL=
EOF
  chmod 600 "$ENV_FILE"
  echo "==> Wrote $ENV_FILE (secrets generated; back this file up somewhere safe)"
fi

# Point the API/admin at the Vercel site URL (any run with WEB_URL set).
if [ "$first_run" -eq 0 ] && [ -n "${WEB_URL:-}" ]; then
  d="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
  sed -i -e "s|^WEB_URL=.*|WEB_URL=$WEB_URL|" \
         -e "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://admin.$d,$WEB_URL|" \
         -e "s|^PUBLIC_WEB_URL=.*|PUBLIC_WEB_URL=$WEB_URL|" \
         -e "s|^NEXT_PUBLIC_WEB_URL=.*|NEXT_PUBLIC_WEB_URL=$WEB_URL|" "$ENV_FILE"
  echo "==> Web URL set to $WEB_URL"
fi

# --- 3. build, migrate, start ------------------------------------------------
echo "==> Building images (first build takes several minutes)"
"${COMPOSE[@]}" build

echo "==> Starting Postgres"
"${COMPOSE[@]}" up -d --wait postgres

backups_on=0
grep -qE '^BACKUP_AGE_RECIPIENT=.+' "$ENV_FILE" && backups_on=1
if [ "$backups_on" -eq 1 ]; then
  command -v age >/dev/null || apt-get install -y -qq age >/dev/null
  # Snapshot before migrating, so a bad migration is always recoverable.
  if [ -f "$repo_root/.seeded" ]; then
    echo "==> Pre-migration backup"
    "$repo_root/infra/deploy/backup-prod.sh"
  fi
fi

"${COMPOSE[@]}" run --rm api alembic upgrade head

if [ ! -f "$repo_root/.seeded" ]; then
  needs_seed=1
  echo "==> Seeding admin user, topics, starter sources (no demo story)"
  "${COMPOSE[@]}" run --rm api python /srv/infra/scripts/seed.py
  admin_email="$(grep '^ADMIN_SEED_EMAIL=' "$ENV_FILE" | cut -d= -f2-)"
  admin_pass="$(grep '^ADMIN_SEED_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
  # The password now lives hashed in the DB; drop the plaintext copy.
  sed -i '/^ADMIN_SEED_PASSWORD=/d' "$ENV_FILE"
  touch "$repo_root/.seeded"
  echo "Admin login (shown once — save it now; you enroll MFA on first sign-in):"
  echo "  $admin_email / $admin_pass"
fi

echo "==> Starting all services"
"${COMPOSE[@]}" up -d --remove-orphans

if [ "$backups_on" -eq 1 ]; then
  cat > /etc/cron.d/teluguvarta-backup <<EOF
# Managed by infra/deploy/deploy.sh — nightly encrypted backup.
30 3 * * * root $repo_root/infra/deploy/backup-prod.sh >> /var/log/teluguvarta-backup.log 2>&1
EOF
  echo "==> Nightly backup scheduled (03:30 server time, log /var/log/teluguvarta-backup.log)"
else
  echo "==> Backups NOT configured — set BACKUP_AGE_RECIPIENT in .env.prod (infra/deploy/BACKUPS.md)"
fi

# --- 4. verify ---------------------------------------------------------------
echo "==> Configuring nginx + TLS"
DOMAIN="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)" \
ACME_EMAIL="$(grep '^ACME_EMAIL=' "$ENV_FILE" | cut -d= -f2-)" \
  "$repo_root/infra/deploy/nginx-setup.sh"

echo "==> Waiting for API health"
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    echo "API healthy."; break
  fi
  sleep 2
done
"${COMPOSE[@]}" ps

domain="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
echo
echo "API:    https://api.$domain/health"
echo "Admin:  https://admin.$domain"
echo "Vercel (apps/web) env: NEXT_PUBLIC_API_URL=https://api.$domain"
echo "  NEXT_PUBLIC_WEB_URL=<your vercel URL>; then re-run with WEB_URL=<that URL>"
