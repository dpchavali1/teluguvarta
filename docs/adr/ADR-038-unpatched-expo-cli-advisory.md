# ADR-038: Handle the unpatched Expo CLI node-forge advisory

- **Status**: accepted
- **Date**: 2026-10-02
- **Ticket**: T19 release hardening

## Context

The latest `main` CI node job passes lint, typecheck, mobile/web tests and
web/admin builds, then fails its high-severity `pnpm audit` gate. The reported
path is `apps/mobile > expo@57.0.21 > @expo/cli@57.0.23 > node-forge@1.4.0`
(also via `@expo/code-signing-certificates`). GitHub's
[GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv)
lists all published versions through 1.4.0 as affected and no patched
version. The upstream [fix PR](https://github.com/digitalbazaar/forge/pull/1152)
is open as of this date. A routine dependency override cannot select a
published safe version.

The repo requires a real dependency-scan gate. Silencing this one advisory,
forking cryptographic verification, or claiming a clean release changes the
security posture and cannot be inferred from the build passing.

## Decision

The owner chose to keep the full audit gate blocking releases on 2026-10-02.
Do not suppress the advisory or create a scoped exception. Wait for a
published, reviewed upstream fix; then upgrade the dependency, rerun the
full audit and mobile build/test matrix, and resume the release gate only
when they pass. Safe local implementation and verification may continue.

## Consequences

This preserves the current security standard but blocks green CI and formal
production deployment while the advisory remains unresolved.

## Alternatives considered

- Override to a nonexistent patched `node-forge` release: impossible.
- Suppress all high-severity audits: rejected because it would hide unrelated
  vulnerabilities.
- Vendor an unmerged cryptographic patch: rejected without a focused security
  review and regression suite.
- Time-bounded exception for the Expo CLI path: rejected by the owner for this
  release; it would not fix the vulnerability.
