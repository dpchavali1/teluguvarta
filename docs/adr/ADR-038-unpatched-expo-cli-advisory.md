# ADR-038: Handle the unpatched Expo CLI node-forge advisory

- **Status**: proposed — security/release decision pending
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

## Decision needed

Choose one documented release policy after assessing where Expo CLI runs and
whether any vulnerable verification path processes untrusted input:

1. Keep the full audit gate failing and defer a release until an upstream
   patched package is available. Upgrade and rerun the full mobile build/test
   matrix then.
2. Accept a time-bounded, narrowly scoped exception for the Expo CLI advisory
   with an owner, expiry, explicit exposure analysis, compensating controls and
   a separate production-runtime audit gate. Continue to report the exception
   as an open risk.

No CI gate change or security exception is implemented by this ADR proposal.

## Consequences

Option 1 preserves the current security standard but blocks green CI and
formal release proof. Option 2 may allow unrelated changes to ship while the
upstream patch is pending, but needs explicit risk acceptance and continued
tracking; it is not a vulnerability fix.

## Alternatives considered

- Override to a nonexistent patched `node-forge` release: impossible.
- Suppress all high-severity audits: rejected because it would hide unrelated
  vulnerabilities.
- Vendor an unmerged cryptographic patch: rejected without a focused security
  review and regression suite.
