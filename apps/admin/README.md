# apps/admin — Next.js admin console. See docs/tickets/T05.md, T06.md, T12.md.

Telugu repair is documented in [the repair runbook](../../docs/TELUGU_REPAIR.md)
and accepted ADR-034. The detail page shows current automated diagnostics beside
stored QA; ADMIN actions use the existing session cookie/CSRF header.

To check confirmation/cancel, stale-error retention and reload, current hashes,
withholding/regeneration, retry caps and EDITOR visibility with synthetic API
responses, start a production admin build on port 3074, then run from the root:

```sh
pnpm --filter @teluguvarta/admin build
pnpm --filter @teluguvarta/admin exec next start -p 3074
# In a separate terminal; reuses the web workspace's existing browser QA tools:
ADMIN_BASE_URL=http://127.0.0.1:3074 pnpm --filter @teluguvarta/web exec node scripts/admin-telugu-repair-check.mjs
```

The check intercepts every API request and blocks other external requests. It
uses role hints and fake session responses, never production credentials or
live repairs. Phone overflow/scoped axe and screenshots are included; output is
the system temp directory by default, or `INTERFACE_OUT_DIR`. This verifies UI
states only; real auth/repair lifecycle is covered by API tests and production
acceptance is recorded separately.
