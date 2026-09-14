# ADR-010: "Folio" visual redesign (supersedes ADR-008's palette)

- **Status**: accepted
- **Date**: 2026-09-13
- **Ticket**: (ad hoc — user-requested redesign, no ticket file)

## Context

ADR-008 (2026-09-10) shipped the first shared visual identity across
`apps/web`, `apps/admin`, `apps/mobile`. ADR-009 (2026-09-10, implemented
2026-09-12/13) then centralized token *values* in
`packages/design-tokens/tokens.json`, generated per surface and
CI-enforced against drift. But the palette itself was revised twice after
ADR-008 shipped (2026-09-12 "modern design foundation", 2026-09-13 contrast
fix) without ever being a deliberate design pass — it drifted toward a
generic blue-SaaS look rather than being designed. The user asked for an
actual fresh redesign, explicitly using the two Vercel design skills
installed the prior session (`web-design-guidelines`, which fetches
Vercel's Web Interface Guidelines live; `vercel-react-native-skills`,
bundled RN/Expo rules).

## Decision

Redesign the token *values* only — keep ADR-009's generation mechanism
(single source `tokens.json` → generated per-surface outputs, CI-enforced,
zero new dependencies in the pipeline) and keep ADR-008/ADR-009's rejection
of a shared component library (`packages/ui` stays an empty stub; web and
mobile can't share JSX without a new cross-platform dependency).

New system, "Folio" — an editorial-print register for a bilingual news
digest instead of a generic blue SaaS look:

- **Color**: warm paper surface pair (light: `#f6f2e8`/`#fffcf5`, dark:
  `#171410`/`#211d16`) instead of cool near-white/near-black; a deep
  indigo-violet accent (`#453d8f` light / `#9c92e6` dark) instead of blue;
  a rust/amber "hot" color (`#a8431d` light / `#e89468` dark) reserved for
  breaking-news and "why this matters" emphasis, distinct from the
  standard-red `danger` semantic role used for form errors. Light and dark
  modes were designed as pairs, not dark-as-inverted-light.
- **Type**: collapsed to a 4-step scale (`display`/`headline`/`body`/
  `meta`) with a new `display` step for hero/home headlines. Applies the
  RN skill's "avoid multiple font sizes — use weight and color for
  hierarchy" rule system-wide, not just on mobile. Telugu-specific
  line-height/letter-spacing overrides extended to cover `display`.
- **Shape/elevation**: kept the existing sharp small-radius geometry
  (`radius.md`/`lg` unchanged). Added the `shadow` token block that ADR-009
  specified but never actually implemented — `build.mjs` previously
  hardcoded the hard-shadow offset (`4px`/`3px`) directly; it now reads
  `tokens.shadow.sm`/`md`, and the mobile RN export gains a `boxShadow`
  string field per the RN skill's "use CSS `boxShadow` syntax, not
  `shadowColor`/`elevation`" rule (kept the legacy RN shadow props
  alongside it since removing them would be a breaking change for any
  consumer relying on native elevation on Android).
- **Motion**: added `motion.duration.fast`/`base` (120ms/200ms) so
  transition durations stop being hardcoded ad hoc per component; kept the
  single `easeOut` easing token.

Web/admin restyle also applied the fetched Web Interface Guidelines
checklist inline while touching each file (focus-visible rings, hover/
active state contrast, `text-wrap: balance` on headings, `tabular-nums` on
numeric table columns, image dimensions/lazy-loading, `prefers-reduced-motion`).
Mobile restyle applied the RN skill's zero-new-dependency UI rules inline
(`Pressable` over `TouchableOpacity`, `borderCurve: 'continuous'`, `gap`-based
spacing, the new shadow tokens, transform/opacity-only animation, hoisted
`Intl.*` construction).

## Consequences

Easier: token file is now internally consistent with what ADR-009 claimed
it would contain (shadow was missing before); duration is no longer
hardcoded per component so future motion tweaks are one-line changes;
palette has actual design intent instead of being a moving target across
three unplanned revisions.

Harder / deferred: the RN skill's dependency-adding rules (`expo-image`,
`FlashList`/`LegendList`, `react-native-bottom-tabs`, `zeego`, `galeria`)
were deliberately **not** applied — they're real value but require new
native dependencies (lockfile + native project changes), which is a
separate, higher-risk decision the user hasn't signed off on. Tracked as a
follow-up in `PROGRESS.md`; needs its own explicit go-ahead (and arguably
its own ADR) before any of those packages are added.

Revisit if: a future ticket wants list virtualization or native menus on
mobile at real scale — that's the trigger to open the dependency-adding
follow-up rather than working around it with more hand-rolled code.

## Alternatives considered

- **Leave the current (2026-09-12) blue palette as-is and only run the
  skills as a compliance audit**: rejected — the user explicitly asked for
  a fresh redesign, not another patch on an accidental palette.
- **Introduce a real shared component library** (e.g. Tamagui, RN Web) so
  web/admin/mobile render from one component tree: rejected, same
  reasoning as ADR-009 — real cross-platform dependency, out of scope for
  a token-level redesign, and V1 doesn't have the volume of shared UI to
  justify the migration cost yet.
- **Add the RN skill's dependency-requiring rules in this same pass**:
  rejected — bundling a visual redesign with new native dependencies makes
  either change harder to review or roll back independently; kept
  restyle-only per the "hard-to-reverse action needs explicit sign-off"
  norm.
