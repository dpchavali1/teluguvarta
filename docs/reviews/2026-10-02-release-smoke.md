# Deployed release smoke check — 2026-10-02

At 12:40 UTC, after the owner reported deploying, the public API, web, and
admin revision endpoints each returned HTTP 200 and the exact expected commit
`50483858c2e64321f17a331d5d3e7e2a5af635e2`.

| Public check | Result |
| --- | --- |
| API `/health/ready` | HTTP 200 |
| Web `/search` | HTTP 200 |
| Admin `/review` | HTTP 200 |
| Admin `/coverage` | HTTP 200 |

[CI for that commit](https://github.com/dpchavali1/teluguvarta/actions/runs/37007381518)
completed with API and contracts jobs passing. The Node job failed at
`pnpm audit --audit-level=high` on the known high-severity `node-forge`
advisory. [ADR-038](../adr/ADR-038-unpatched-expo-cli-advisory.md) keeps this
release gate blocking pending an upstream fix and validation.

These external checks do not prove the VPS monitor ran, backup freshness,
restore RPO/RTO, alert delivery, rollback, admin MFA/logout, or mobile device
performance. Those require managed-environment and owner device evidence.
