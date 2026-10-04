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

1. **Separation of duties.** Tracker entries (visa bulletin, exam dates) can be
   approved by their own author; approval queues pushes. Options: (a) require a
   different admin to approve (409 when `approved_by == entered_by`), with an
   explicit documented single-admin override; (b) keep as is for a one-person
   team and rely on the audit log. Same question for sensitive stories and
   corrections.
2. **Dependency-advisory policy.** `package.json` `auditConfig.ignoreGhsas`
   (commit e8c0762) suppresses the node-forge and braces advisories, which
   ADR-038 says must not be suppressed. Either revert the ignore, or supersede
   ADR-038 with a dated expiry, an owner, and a rule for when an ignore is
   allowed.
3. **Perimeter.** If Cloudflare (or any CDN) fronts the VPS: origin firewall to
   CDN ranges, `real_ip_header CF-Connecting-IP` in nginx, uvicorn
   `--forwarded-allow-ips` limited to the proxy, otherwise per-IP rate limits
   collapse into one bucket. Security headers (HSTS, CSP) for web and API.
4. **Public expensive endpoints.** Rate limit and cache `/story/*/card`;
   per-IP limit on admin login (today per email only).
5. **MFA lifecycle.** Lost-authenticator recovery (operator reset), TOTP replay
   protection (store last-used step).
6. **Exam source links.** Per-exam official-domain allowlist (current rule:
   https, no userinfo/backslash, parsed host with a dot).
7. **Retraction cache bound.** Share cards cache 60 s; state the maximum time a
   retracted story may remain visible in caches.
8. **Secrets.** Where `.env.prod` and the Firebase server key live and how they
   are rotated. Restrict the client Firebase API key to the app bundle IDs.

## Consequences

Until decided, 1–5 remain open risks recorded in the review doc.

## Alternatives considered

Implementing each unilaterally — rejected: these are policy/architecture
choices (NON_NEGOTIABLES: don't invent requirements).
