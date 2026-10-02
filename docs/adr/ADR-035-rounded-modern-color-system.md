# ADR-035: Rounded controls and paired modern colors

- **Status**: accepted — owner's 2026-10-01 app redesign request
- **Date**: 2026-10-01
- **Tickets**: UI15, T19-maintenance

## Context

ADR-009 centralizes values in `packages/design-tokens/tokens.json`; ADR-010's
Folio palette and sharp small-radius geometry were the prior design choice.
The owner now wants a visibly more modern app, rounded buttons and strong light
and dark colors. A generator mismatch makes the mobile `radius.pill` zero even
though the single source defines 999, so many existing controls render square.

## Decision

Keep ADR-009's single source and generation/check mechanism. Supersede
ADR-010's color and shape values with a paired cool canvas/ink/indigo palette:
soft blue-gray canvas and white surfaces in light mode; deep navy canvas and
slate surfaces in dark mode; indigo/violet primary controls. Preserve the
semantic roles in ADR-014: indigo for navigation/actions, rust for editorial
emphasis, and green/amber/red for success/warning/error. Check contrast in
both modes with the existing token checker; retain visible focus and 44pt
native targets. Choose md/lg/card/pill radii of 8/12/16/999 respectively.

Generate the mobile radius values from the source instead of hardcoding
`pill: 0`. Apply rounded primary/secondary controls and grouped surfaces on
mobile through those tokens. Generated CSS rolls the same color/shape values
through web and admin, preserving visual coherence; no new UI framework,
dependency, content layout or interaction policy. Mobile app styling gets the
focused implementation/verification pass. Deployment and native-device visual
acceptance remain separate.

## Consequences

The visual change crosses all three surfaces because their token values are
intentionally shared. Existing reading and role gates stay intact. A native
device check is needed for final appearance, dynamic type and screen readers;
typechecks/browser fixtures and exports establish only local behavior.
