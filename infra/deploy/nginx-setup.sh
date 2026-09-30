#!/usr/bin/env bash
# Adds <DOMAIN> (public web), www.<DOMAIN> (redirects to <DOMAIN>), api.<DOMAIN>
# and admin.<DOMAIN> to the host's nginx in their own file (existing sites are
# untouched) and gets Let's Encrypt certs via certbot. Idempotent.
# Called by deploy.sh; needs DOMAIN and ACME_EMAIL in the environment.
set -euo pipefail
: "${DOMAIN:?}" "${ACME_EMAIL:?}"

command -v nginx >/dev/null || apt-get install -y -qq nginx
command -v certbot >/dev/null || apt-get install -y -qq certbot python3-certbot-nginx

# One file per domain, so a domain change adds a site instead of rewriting the
# old one (older installs used teluguvarta.conf; delete it once nothing uses it).
conf="/etc/nginx/conf.d/teluguvarta-$DOMAIN.conf"
# X-Forwarded-For is set to the peer address, never appended to: uvicorn runs
# with --forwarded-allow-ips "*" and takes the first entry as the client, so an
# appended header let a client pick its own IP and dodge the per-IP limits.
proxy_headers='
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;'
if [ ! -f "$conf" ]; then
  cat > "$conf" <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:13000;$proxy_headers
    }
}
server {
    listen 80;
    server_name www.$DOMAIN;
    return 301 https://$DOMAIN\$request_uri;
}
server {
    listen 80;
    server_name api.$DOMAIN;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:18000;$proxy_headers
    }
}
server {
    listen 80;
    server_name admin.$DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:13001;$proxy_headers
    }
}
EOF
fi
# Existing installs keep their file (certbot has edited it), so fix the header in place.
sed -i 's/X-Forwarded-For \$proxy_add_x_forwarded_for;/X-Forwarded-For $remote_addr;/' "$conf"
nginx -t
systemctl reload nginx

# certbot --nginx adds the 443 blocks + redirect for these names only.
certbot --nginx --non-interactive --agree-tos -m "$ACME_EMAIL" --redirect --expand \
  -d "$DOMAIN" -d "www.$DOMAIN" -d "api.$DOMAIN" -d "admin.$DOMAIN"
nginx -t && systemctl reload nginx
