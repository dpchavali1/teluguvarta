# ADR-009: Single design-token source, generated per surface

- **Status**: accepted
- **Date**: 2026-09-10
- **Ticket**: T22 (proposed follow-up to T21)

## Context

ADR-008 shipped a shared design language as three hand-copied token
sources: CSS custom properties in `apps/web/src/app/globals.css`, a
duplicate set in `apps/admin/src/app/globals.css`, and a JS mirror in
`apps/mobile/src/theme/tokens.ts`. It explicitly accepted the duplication
and deferred a shared package: *"revisit with a `packages/ui` package if a
4th surface or major redesign happens later."*

That bet lost on the very first non-trivial change, before the ticket was
even committed. `apps/web` was redesigned to the "Ink & Signal" palette
(bone `#f2f0e8`, ink `#14140f`, signal-lime `#c8f03f`, 2px radii, offset
hard shadows). Admin and mobile were never rolled forward and still carry
the earlier "dusk-teal ground, marigold accent" palette (`#eef1f0`,
`#b8791f`, `#1f7d6f`, soft radii, blurred shadows). Both files carry
comments asserting they mirror `apps/web` — comments that are now false.

The failure mode is the point: this was not carelessness that a more
diligent session would have avoided. There is no linkage between the three
files, so nothing — not the type checker, not lint, not CI, not a
reviewer reading a diff of one app — could have flagged that a palette
swap in one surface failed to propagate to the other two. The divergence
was found only because a design review read all three files side by side.
Left alone, the next redesign drifts exactly the same way.

`docs/SPEC.md` does not cover visual design at all, so this is an open
architecture decision under non-negotiable #11 (don't invent requirements
— write an ADR and stop) and needs a written decision rather than an
implicit one taken inside a future ticket.

## Decision

Introduce a workspace package holding the design values **once**, and
generate each surface's token file from it. Explicitly *not* a component
library — components cannot be shared across Next.js and React Native
anyway, and ADR-008's judgment that a `packages/ui` is oversized for V1
still stands. What is shared is values, not JSX.

```
packages/design-tokens/
  tokens.json      # single source: color (light + dark), spacing, radius,
                   # shadow, type scale
  build-css.mjs    # tokens.json -> CSS custom properties partial
  build-rn.mjs     # tokens.json -> typed `as const` TS module
  package.json     # private, workspace-only, no dependencies
```

Generated outputs, each with a `GENERATED — DO NOT EDIT` header naming
the source file:

- `apps/web/src/app/tokens.css` and `apps/admin/src/app/tokens.css`,
  each `@import`-ed at the top of that app's `globals.css`.
- `apps/mobile/src/theme/tokens.ts`, keeping today's exported shape
  (`colors`, `radius`, `spacing`, `shadow`, `typography`, `typographyTe`)
  so no consumer changes.

Constraints this stays inside:

- **Zero new dependencies.** Both generators are plain Node using only
  `node:fs` and `JSON` — no build tool, no bundler, no style-dictionary.
  The pnpm lockfile is untouched, which was ADR-008's main objection to
  the framework alternatives.
- **No new UI framework**, per ADR-008 — unchanged.
- Generation runs from each app's existing `prebuild` script, so pnpm
  workspaces pick it up with no new orchestration.
- **CI enforces it**: regenerate, then `git diff --exit-code`. A hand-edit
  to a generated file, or a value that drifted, fails the build. This is
  the part that actually prevents a repeat — the generator alone would
  not have.

Telugu-specific type metrics (`typographyTe`, and web's `[lang="te"]`
cascade) are part of the token source, not per-surface additions. English
canonical / Telugu derived applies to content, not to type: both scales are
first-class here, since Telugu conjuncts and stacked vowel signs need
looser tracking and taller leading than the Latin display scale.

## Consequences

**Easier**: one place to change a palette; drift becomes a failing build
instead of a silent brand mismatch; a 4th surface is a new generator
target rather than a fourth hand-copy; the light/dark pairing is defined
once, so dark mode stays correct by construction across all surfaces
rather than just web.

**Harder**: a build step now sits between editing a token and seeing it,
which is friction during design iteration — mitigated by keeping the
generators trivial (~40 lines, readable in one screen) and runnable
directly. Generated files are committed, so diffs get noisier on a palette
change. Contributors must learn not to edit the generated files; the
header plus the CI check should make that self-correcting.

**Revisit if**: a surface needs a token the others genuinely should not
have, and per-surface overrides start accumulating in the source — at that
point the flat `tokens.json` should grow explicit per-surface scopes rather
than being quietly forked again.

**Sequencing**: this ADR does not itself fix the palette divergence. Roll
admin and mobile forward to Ink & Signal by hand first, ship that, and only
then extract the token source — coupling a visual change with new build
tooling in one change makes both harder to review.

## Alternatives considered

- **Leave the three copies, fix the palette by hand, rely on discipline.**
  Rejected: this is precisely what ADR-008 chose, and it failed within one
  ticket. Nothing about the next attempt would be structurally different.
- **`packages/ui` with shared components.** Rejected, same reasoning as
  ADR-008 — Next.js and React Native can't share components without a
  cross-platform layer (React Native Web, Tamagui), which is a large
  dependency and a migration, disproportionate to keeping colors in sync.
- **style-dictionary** (the standard tool for exactly this). Rejected for
  now only because it adds a dependency to solve a problem two ~40-line
  scripts solve at this scale. Worth revisiting if token needs grow past
  flat values (theming per tenant, platform-specific overrides).
- **CSS custom properties as the single source, parsed for mobile.**
  Rejected: parsing CSS to produce JS means a fragile regex or a real CSS
  parser dependency, and it privileges web's format for no reason. A
  neutral JSON source treats both consumers equally.
- **Runtime token fetch from the API.** Rejected outright: design tokens
  are build-time constants; this would add a network dependency to
  rendering and break the non-negotiable that browsing works without
  login.
