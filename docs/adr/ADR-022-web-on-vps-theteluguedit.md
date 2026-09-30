# ADR-022: Public web on the VPS at theteluguedit.com

- **Status**: accepted (2026-09-29): owner picked `theteluguedit.com`, dropped `tte.news`,
  and asked for "all the changes needed"
- **Date**: 2026-09-29
- **Ticket**: automation plan follow-up (web deploy, unblocks mobile `EXPO_PUBLIC_WEB_URL`); amends ADR-007

## Context

ADR-007 put `apps/web` on Vercel. In practice everything else already runs on one Hetzner VPS
(`infra/deploy/`: Postgres, API, worker, admin behind the host's nginx), and the web app was never
deployed anywhere. `deploy.sh` still told the operator to "host it on Vercel". The brand doc named
`tte.news`/`tte.app`, which the owner has now dropped for `theteluguedit.com`.

## Decision

1. `apps/web` runs on the same VPS as a `web` service in `docker-compose.prod.yml` (the admin's
   `next.Dockerfile`, `next start`, port 13000 on localhost). No Vercel account.
2. Hostnames: `theteluguedit.com` (web), `www.theteluguedit.com` (301 to the apex),
   `api.theteluguedit.com`, `admin.theteluguedit.com`. `deploy.sh` defaults `DOMAIN` to it and derives
   every URL (`WEB_URL`, `PUBLIC_WEB_URL`, `NEXT_PUBLIC_*`, CORS) from `DOMAIN` on every run.
3. `nginx-setup.sh` writes one nginx file per domain, so moving domains adds a site and leaves the old
   one (the sslip.io hostnames the installed APK uses) working until it is deleted by hand.
4. Images build one at a time, since two parallel Next.js builds can run the 4 GB box out of memory.

## Consequences

- ISR caching is per process on the VPS, with no CDN edge. Cloudflare in front can cache later.
- The web app shares the box's CPU/RAM with the API. Watch memory after the first deploy.
- Internal identifiers (`teluguvarta` package scope, compose project, DB user, `org.teluguglobal.app`
  bundle id) are unchanged, per `docs/brand/TTE-BRAND.md`.
- Reverting to Vercel means removing the `web` service and pointing `WEB_URL` elsewhere. Nothing else
  depends on where the web app runs.
