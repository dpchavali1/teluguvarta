# ADR-008: Visual design refresh (web/mobile/admin), no new UI framework

- **Status**: accepted
- **Date**: 2026-09-10
- **Ticket**: T21

## Context

T14/T15/T18 shipped functional, accessible (WCAG 2.2 AA) UI across
`apps/web`, `apps/mobile`, and `apps/admin`, but with no shared visual
identity: plain unstyled CSS in web/admin (`globals.css`) and ad-hoc
`StyleSheet.create` values per screen in mobile. Product owner asked for a
"trendier," more polished look and easier-to-use UI across all three apps.
The spec doesn't cover visual design at all, so scope/approach is an
open decision per non-negotiable #11.

## Decision

Ship a shared, hand-rolled design language rather than pulling in a UI
framework (no Tailwind/shadcn/MUI/NativeBase):

- A small set of CSS custom-property tokens (`apps/web/src/app/globals.css`,
  mirrored in `apps/admin`) for color, spacing, radius, shadow, and type
  scale, covering both light and dark themes (`ThemeToggle` already exists).
- A matching JS token module for mobile (`apps/mobile/src/theme/tokens.ts`)
  consumed by `StyleSheet.create` calls, since React Native can't read CSS
  variables.
- Restyle existing components/screens in place (headers, story cards,
  buttons, forms, admin tables) using these tokens — no new pages, no
  content/IA changes, no new routes.
- One small dependency addition where it meaningfully improves feel:
  `next/font` (already built into Next.js, zero extra install) for
  typography, and CSS transitions/`Animated` API (already available) for
  motion — deliberately avoiding `framer-motion`/icon-library installs to
  keep the pnpm lockfile untouched across three apps edited in the same
  session.

## Consequences

Easier: consistent look across apps, faster future styling since tokens
are centralized, dark mode stays correct by construction. Harder: no
component library means some primitives (buttons, inputs) are hand-built
and duplicated per app rather than shared — acceptable at V1 scale;
revisit with a `packages/ui` package if a 4th surface or major redesign
happens later.

## Alternatives considered

- **Tailwind + shadcn/ui for web/admin**: rejected for this pass — adds a
  build-tool dependency and a large one-time migration cost for existing
  plain-CSS pages, disproportionate to "make it look trendier."
- **NativeBase/Tamagui for mobile**: rejected, same reasoning; mobile
  screens are few enough to restyle directly.
- **Do nothing / defer to a dedicated design ticket with mockups first**:
  rejected per explicit product decision to go straight to code.
