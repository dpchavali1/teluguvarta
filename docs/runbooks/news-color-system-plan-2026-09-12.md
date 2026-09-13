# News color-system plan — 2026-09-12

## Goal

Build a calm, credible color system for Telugu Global that helps readers scan
news, understand control states, and recognize editorial warnings without
turning every chip or button into a brand-colored object. The system must work
for English and Telugu, light and dark mode, web, mobile, and admin.

## Current problems

1. `accent` is overloaded. It currently controls links, focus, selected chips,
   hover fills, primary calls to action, saved state, language state, headline
   decoration, and status treatments. These elements do not have the same
   meaning and should not have the same visual weight.
2. Topic chips and action chips are visually too similar. A topic is
   navigation; Save is a persistent toggle; Share is a momentary action; Report
   is a low-frequency utility. Their colors and selected states should differ.
3. The current light border `#a8b0c2` is about 2.18:1 against white, below the
   WCAG 2.2 non-text contrast target of 3:1 when the border is the only visible
   control boundary.
4. The current faint text `#6f778d` is about 4.47:1 against white, narrowly
   below the 4.5:1 normal-text target. It should be decoration-only or darkened.
5. Mobile still contains one-off colors such as `#ccc`, `#444`, `#0645ad`, and
   `#0a0`, so onboarding, settings, notifications, search, and privacy can drift
   from story screens.
6. Status color and interaction color are mixed. “Updated” should not look
   identical to “selected,” and a report action should not look dangerous until
   there is an error or destructive confirmation.

## Color philosophy

- **Neutral carries the news.** Headlines, summaries, metadata, surfaces, and
  inactive controls use ink and slate neutrals.
- **Blue carries interaction.** Indigo is reserved for links, focus, primary
  actions, and confirmed selections.
- **Status colors carry editorial meaning.** Green means success/verified,
  amber means attention/pending, and red means correction/retraction/error.
- **Color never works alone.** Selected controls also use a checkmark, filled
  icon, label change, border change, or `aria-pressed`; statuses always include
  text.
- **Topic identity stays neutral.** V1 topics do not get a rainbow category
  palette. That would add noise and create an unsupported meaning system.

## Proposed semantic tokens

Exact values remain in the shared `packages/design-tokens/tokens.json`. The
names below become the API used by components; components stop consuming raw
palette values such as `accent` and `hot`.

| Role | Light | Dark | Intended use |
| --- | --- | --- | --- |
| `canvas` | `#F7F8FC` | `#10131D` | App/page background |
| `surface` | `#FFFFFF` | `#181D2C` | Cards, menus, fields |
| `surface-subtle` | `#ECEFF5` | `#222B42` | Hover, grouped sections |
| `text-primary` | `#151827` | `#F4F6FF` | Headlines and body |
| `text-secondary` | `#525A70` | `#BCC3D4` | Metadata and supporting copy |
| `text-tertiary` | `#687086` | `#A0A9C1` | Nonessential labels; never disabled-only meaning |
| `border-subtle` | `#D5DAE5` | `#3E4962` | Dividers and decorative boundaries |
| `border-control` | `#737D94` | `#66708A` | Inputs, chips, buttons; ≥3:1 adjacent contrast |
| `interactive` | `#3657D6` | `#91A6FF` | Links, focus, primary action |
| `interactive-hover` | `#2748B8` | `#B2BFFF` | Hover/pressed foreground |
| `interactive-soft` | `#E7ECFF` | `#202958` | Selected chip/toggle background |
| `interactive-on-solid` | `#FFFFFF` | `#11162B` | Text/icon on filled primary action |
| `success` | `#147A55` | `#62D3A5` | Completed, verified, saved confirmation |
| `success-soft` | `#E2F5EC` | `#153A30` | Success background |
| `warning` | `#8A5200` | `#F2BD61` | Pending review, attention |
| `warning-soft` | `#FFF0CE` | `#3B2B12` | Warning background |
| `danger` | `#B42318` | `#FF907F` | Error, retraction, destructive action |
| `danger-soft` | `#FDE8E7` | `#341411` | Error/status background |

Verified example contrast pairs: indigo/white 6.02:1,
indigo-text/indigo-soft 7.13:1, secondary-text/white 6.87:1,
success/success-soft 4.69:1, warning/warning-soft 5.66:1,
danger/danger-soft 5.60:1, and dark control-border/dark surface 3.40:1.

## Component rules

| Component/state | Background | Text/icon | Border and additional cue |
| --- | --- | --- | --- |
| Topic chip, idle | Surface | Primary text | Control border; no brand fill |
| Topic chip, hover | Surface subtle | Primary text | Stronger control border |
| Topic chip, selected/current | Interactive soft | Interactive text | Interactive border + check/current marker |
| Share | Transparent/surface | Secondary text | Neutral control border; blue only on hover/focus |
| Save, unsaved | Transparent/surface | Secondary text | Outline bookmark + neutral border |
| Save, saved | Success soft | Success text | Filled bookmark + “Saved” label |
| Report issue | Transparent | Secondary text | Text-style utility; no red at rest |
| Report error | Danger soft | Danger text | Error icon + explicit message |
| Primary CTA | Interactive solid | On-solid text | Solid fill; one per visual region |
| Secondary CTA | Surface | Primary text | Control border |
| Language toggle, selected | Interactive soft | Interactive text | Check/pressed state + strong border |
| Status: updated | Interactive soft | Interactive text | “Updated” text + info icon |
| Status: review pending | Warning soft | Warning text | “Review pending” text + icon |
| Status: human reviewed | Success soft or neutral | Success/primary text | Check icon + label |
| Status: retracted | Danger soft | Danger text | Retraction label; never color alone |
| Disabled | Surface subtle | Tertiary text | No shadow; reduced border; disabled attribute |
| Keyboard focus | Unchanged | Unchanged | 3px interactive outline + 2px surface offset |

## Surface-specific application

### Web

- Keep the dark briefing hero, but replace decorative accent-heavy shadows
  with a restrained indigo edge or neutral elevation.
- Topic navigation stays neutral until hover/current state.
- Story action buttons use neutral borders. Save alone gains green after it is
  saved; Share never remains highlighted.
- Links use indigo plus underlines. Headline hover uses an underline or subtle
  background sweep that does not obscure Telugu marks.
- Metadata pills use neutral surfaces. Only editorial status badges use status
  colors.

### Mobile

- Replace every remaining raw hex value in screen/component StyleSheets with
  semantic generated tokens.
- Give topics, actions, and language toggles the same state meanings as web,
  while retaining 44pt minimum targets.
- Use platform pressed opacity/elevation in addition to color.
- Saved state uses green with a filled bookmark and changed label; active tab
  and keyboard/accessibility focus use indigo.
- Verify system dark mode at app launch and after live appearance changes.

### Admin

- Keep most of the interface neutral so story content and sources dominate.
- Use green only for completed/healthy, amber for review-required or paused,
  and red for failed/retracted/destructive.
- Approval buttons use the primary interaction color; rejection/retraction use
  danger only inside the confirmed action area.
- Table-row hover remains neutral rather than blue.

## Implementation sequence

1. Expand the shared source from raw palette names to semantic tokens, keeping
   temporary aliases so existing screens compile during migration.
2. Add an automated contrast script covering every foreground/background and
   border/adjacent pair. Fail CI below 4.5:1 for normal text, 3:1 for large text
   and required UI boundaries, and 3:1 for focus indicators.
3. Migrate web primitives first: topic chip, action button, language toggle,
   status badge, link, input, and focus ring. Remove the late CSS overrides
   that currently redefine the same component in several places.
4. Migrate mobile primitives and remove all raw screen-level color literals.
   Add light/dark visual tests for StoryCard, onboarding, search, saved, and
   settings.
5. Migrate admin status pills, tables, forms, and decision actions.
6. Run browser axe checks plus screenshot comparisons at 390, 768, and 1440px;
   test 200% text zoom, forced-colors mode, reduced motion, and both themes.
7. Test on iOS and Android with large text and one representative long Telugu
   headline. Confirm that selected state, focus, error, and disabled state are
   understandable in grayscale.

## Acceptance criteria

- No component imports a generic `accent` token directly; it consumes a
  semantic interaction or status role.
- No user-facing mobile StyleSheet contains a raw hex color.
- Topic, Share, Save, Report, language selection, and editorial statuses are
  visually distinct without relying on color alone.
- All normal text pairs meet at least 4.5:1; essential boundaries and focus
  indicators meet at least 3:1.
- Light and dark screenshots exist for the core web, mobile, and admin paths.
- Telugu at large text sizes remains unclipped and its vowel signs are not
  crossed by background/underline effects.

WCAG targets follow the current [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/), especially 1.4.3 Contrast (Minimum), 1.4.11 Non-text Contrast, and visible focus requirements.
