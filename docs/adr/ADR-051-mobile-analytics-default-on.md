# ADR-051: Mobile usage analytics on by default

- **Status**: proposed (owner requested default-on, 2026-10-04; awaiting option choice)
- **Date**: 2026-10-04
- **Ticket**: —

## Context

ADR-039 made Firebase Analytics opt-in: collection is off in `firebase.json`,
`app.json` and `Info.plist` before JS starts, and only the Privacy-screen
"Usage analytics" switch turns it on. `docs/SPEC.md` (privacy section) requires
"separate analytics consent". The owner sees no activity in the Firebase
console because nobody has opted in, and wants analytics on by default.

Default-on collection conflicts with the SPEC's separate-consent requirement
and may conflict with consent law for readers in the EU/UK or other opt-in
regions (the diaspora audience is not US-only). That is a legal assumption, so
it is the owner's call, not an implementation detail.

## Decision

Option **A** (default-on everywhere, no prompt). Privacy toggle, safe-event allowlist, no
advertising signals, no user ID and deletion reset all stay. Prior explicit opt-outs
are respected. Owner accepts the consent-law risk noted above for opt-in regions.
Options considered:

- **A. Default-on everywhere.** Amends SPEC consent wording. Highest data, highest
  legal risk. Needs privacy-policy copy updated first.
- **B. Default-on with a first-launch notice and an easy off switch** (the
  Privacy toggle stays; ships on, notice says so). Middle ground; still opt-out.
- **C. First-run consent prompt, defaulting the choice to "Share"** (reader
  taps once). Keeps "consent" real; most defensible; some drop-off.
- **D. Keep opt-in** and instead use DebugView / a test device for visibility.

Recommendation: **C**. Whichever is chosen, advertising signals stay off, the
Privacy toggle remains, and deletion still resets analytics data.

## Consequences

If A/B/C: remove the "disabled before SDK startup" native defaults (or flip to
JS-controlled), update `mobileAnalytics.ts` default, update privacy copy and
the consent tests, and amend ADR-039 point 3 and the SPEC privacy line. Existing
installs with a stored `false` must be treated as an explicit opt-out and not
overridden.

## Alternatives considered

See options above.
