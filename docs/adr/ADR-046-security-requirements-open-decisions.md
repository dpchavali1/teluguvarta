# ADR-046: Security requirements — decisions needed from the owner

- **Status**: proposed (nothing below is implemented; owner decision required)
- **Date**: 2026-10-04
- **Ticket**: review 2026-10-04 (security requirements pass)

## Context

The security pass found requirements that NON_NEGOTIABLES and the ADRs do not
state. Code-level fixes that needed no policy were made separately (source-URL
parsing, MFA re-enrollment guard, `.env.*` ignore). The items below change
policy, so they are recorded rather than guessed.

## Decisions needed

1. **Separation of duties.** *(Tracker entries: implemented 2026-10-04 as option
   (a), override `ALLOW_SELF_APPROVAL=true`; stories and corrections still open.)* Tracker entries (visa bulletin, exam dates) can be
   approved by their own author; approval queues pushes. Options: (a) require a
   different admin to approve (409 when `approved_by == entered_by`), with an
   explicit documented single-admin override; (b) keep as is for a one-person
   team and rely on the audit log. Same question for sensitive stories and
   corrections.
2. **Dependency-advisory policy.** *(Resolved 2026-10-04 by [ADR-047](ADR-047-dated-audit-exceptions.md).)* `package.json` `auditConfig.ignoreGhsas`
   (commit e8c0762) suppresses the node-forge and braces advisories, which
   ADR-038 says must not be suppressed. Either revert the ignore, or supersede
   ADR-038 with a dated expiry, an owner, and a rule for when an ignore is
   allowed.
3. **Perimeter.** If Cloudflare (or any CDN) fronts the VPS: origin firewall to
   CDN ranges, `real_ip_header CF-Connecting-IP` in nginx, uvicorn
   `--forwarded-allow-ips` limited to the proxy, otherwise per-IP rate limits
   collapse into one bucket. Security headers (HSTS, CSP) for web and API.
4. **Public expensive endpoints.** *(Implemented 2026-10-04: share card 20/min per
   client + 300/min global, in-process, 60 s cache already present; admin login
   20 failed attempts per IP per 15 min. Client key depends on §3.)* Rate limit and cache `/story/*/card`;
   per-IP limit on admin login (today per email only).
5. **MFA lifecycle.** *(Implemented 2026-10-04: `users.mfa_last_step` single-use
   codes; `infra/scripts/reset_admin_mfa.py` operator reset.)* Lost-authenticator recovery (operator reset), TOTP replay
   protection (store last-used step).
6. **Exam source links.** Per-exam official-domain allowlist (current rule:
   https, no userinfo/backslash, parsed host with a dot).
7. **Retraction cache bound.** *(Bounds derived from code 2026-10-04; the owner
   still has to accept them as the stated limit. They were not measured against
   production headers.)* A retracted story's API response is live (the public
   API sets no cache lifetime), but the web layers add up, because both the
   rendered page and its API fetch revalidate every 60 s (`apps/web/src/lib/api.ts`,
   each page's `revalidate`):
   - Story page and listings (home, latest, topic, country): up to about 120 s
     (60 s page + 60 s fetch), plus one stale response served to the first
     visitor after expiry. A CDN or browser that holds a copy longer extends
     this; no CDN is configured yet (§3).
   - Share card PNG: up to about 180 s (adds the 60 s `max-age` already sent to
     browsers).
   - Sitemap (3600 s revalidate): a retracted URL can stay listed up to about
     1 h 1 min. The story page itself returns 404 within the story-page bound.
   - Not recallable: push notifications and WhatsApp shares already sent, and
     copies other sites made. Mobile saves keep an ID only (ADR-044), so no
     story text outlives a retraction on the device.
   Proposed limit to accept: **3 minutes for story pages and cards; 1 hour for
   sitemap listings.** Shortening means a lower `revalidate`, or on-demand
   revalidation at retraction, which would be a new requirement.
8. **Secrets.** Where `.env.prod` and the Firebase server key live and how they
   are rotated. Restrict the client Firebase API key to the app bundle IDs.

## Consequences

Until decided, 1–5 remain open risks recorded in the review doc.

## Alternatives considered

Implementing each unilaterally — rejected: these are policy/architecture
choices (NON_NEGOTIABLES: don't invent requirements).
