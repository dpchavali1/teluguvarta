# ADR-047: Dated, owned exceptions for unpatched dev-tooling advisories

- **Status**: accepted (owner chose option B on 2026-10-04; the expiry date and
  wording below were drafted by Claude Code and should be confirmed)
- **Date**: 2026-10-04
- **Ticket**: T19 release hardening; resolves ADR-046 §2
- **Supersedes**: the "do not suppress" part of [ADR-038](ADR-038-unpatched-expo-cli-advisory.md)

## Context

`pnpm audit --audit-level=high` exits 1 on two advisories that have no patched
version published (checked 2026-10-04; npm latest is still the affected one):

| Advisory | Package | Path | Ships in a runtime? |
|---|---|---|---|
| GHSA-86w9-cpqp-85rv | node-forge 1.4.0 | `apps/mobile` > `@expo/cli` (build-time CLI, code-signing certs) | No: not in the app bundle, API or web |
| GHSA-vfj7-8cjw-p6xm | braces 3.0.3 | `apps/admin` ESLint plugin; `apps/mobile` jest | No: lint/test tooling only |

ADR-038 kept the gate blocking and forbade any suppression, which leaves `main`
CI red with nothing to upgrade to. Commit e8c0762 had already added
`auditConfig.ignoreGhsas` without a decision record, contradicting ADR-038.

## Decision

An advisory may be ignored in `package.json` `pnpm.auditConfig.ignoreGhsas`
only when **all** hold:

1. No patched version exists (re-checked with `npm view <pkg> version`).
2. It is reachable only through build, lint or test tooling, never a runtime
   (API, web server, mobile app bundle); the path is recorded here.
3. It is listed in the table below with an owner and an expiry date.
4. CI fails once the expiry has passed (`.github/workflows/ci.yml`), forcing a
   re-check: upgrade if a fix exists, otherwise renew here with a new date.

A high-severity advisory in a runtime dependency may never be ignored.

| Advisory | Owner | Expires |
|---|---|---|
| GHSA-86w9-cpqp-85rv | product owner | 2026-11-04 |
| GHSA-vfj7-8cjw-p6xm | product owner | 2026-11-04 |

The two existing `ignoreGhsas` entries stay; each new entry needs a row above.
`.github/workflows/ci.yml` carries the expiry date in `AUDIT_EXCEPTIONS_EXPIRE`.
Update both together.

## Consequences

CI can go green while the advisories remain, and cannot stay green past
2026-11-04 without a recorded re-check. The risk accepted is a vulnerable
`node-forge`/`braces` running on a developer or CI machine during a build.

## Alternatives considered

- Keep ADR-038 as written (option A): `main` CI red until upstream patches, with
  no date at which anyone must look again. Rejected by the owner.
- Ignore without a date: this is what e8c0762 did; rejected.
