#!/usr/bin/env bash
# Adds api.<DOMAIN> and admin.<DOMAIN> to the host's nginx (own file; existing
# sites are untouched) and gets Let's Encrypt certs via certbot. Idempotent.
# Called by deploy.sh; needs DOMAIN and ACME_EMAIL in the environment.
set -euo pipefail
: "${DOMAIN:?}" "${ACME_EMAIL:?}"

command -v nginx >/dev/null || apt-get install -y -qq nginx
command -v certbot >/dev/null || apt-get install -y -qq certbot python3-certbot-nginx

conf=/etc/nginx/conf.d/teluguvarta.conf
if [ ! -f "$conf" ]; then
  cat > "$conf" <<EOF
server {
    listen 80;
    server_name api.$DOMAIN;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
server {
    listen 80;
    server_name admin.$DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:13001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
fi
nginx -t
systemctl reload nginx

# certbot --nginx adds the 443 blocks + redirect for these two names only.
certbot --nginx --non-interactive --agree-tos -m "$ACME_EMAIL" --redirect \
  -d "api.$DOMAIN" -d "admin.$DOMAIN"
nginx -t && systemctl reload nginx
