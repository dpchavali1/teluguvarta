# ADR-017: Web "modern newsroom" redesign

- **Status**: accepted (product owner request, 2026-09-28: "make entire website much modern looking news website … best experience, best performance and ease of use")
- **Date**: 2026-09-28
- **Ticket**: none (owner-requested design pass; ADR-016 is reserved by `docs/plans/gemini-hetzner-telugu-plan.md`)

## Context

After ADR-010 (Folio) and three listing-page "rounds", `apps/web/src/app/globals.css`
had grown to 1,844 lines of layered overrides (sections 13 and 14 re-styling
what sections 3–9 had set up), and the site still read as a sparse text ledger:
thin hierarchy, mono micro-labels everywhere, and on phones a wrapped header link
row for navigation. Stories carry no images by design (ADR-002 rights rules:
never reproduce source images), so a modern look has to come from type, layout
and surfaces rather than photography.

## Decision

Web-only, presentation-layer redesign; no API, data, or rights behaviour changes.

- **Stylesheet rewritten**, not layered: one `globals.css` organised in ten
  sections, colours only from generated tokens (ADR-009), with tints and shadows
  derived through `color-mix()`. It keeps the round-3 near-white light canvas
  override and the Folio dark pair.
- **Two new tokens** in `packages/design-tokens/tokens.json`: `radius.card` (14)
  and `radius.pill` (999), emitted as `--radius-card` / `--radius-pill` in the
  CSS output only. The mobile `tokens.ts` output is unchanged.
- **EditionHeader (ADR-014)**: sticky, translucent header (brand mark, primary
  nav, search, language, single-button theme toggle) plus a horizontally
  scrollable topic bar sourced from `/v1/config`. At ≤900px the header scrolls
  away and primary nav moves to a fixed **bottom tab bar**
  (Home/Latest/Topics/Search/Saved).
- **StoryLead / StoryBrief / StoryActions (ADR-014)**: the contract is unchanged
  (Brief = Save only; Lead and detail = Share/Save/Report; the per-story language
  override appears only on detail). The Lead is a card with an accent wash. Each
  Brief is a card whose whole surface links to the story, with the source link
  and Save button layered above. The home rail is a numbered "Top stories" list.
  Truthful badges only: Breaking (sensitivity), Human-reviewed, status notices.
- **Story page**: breadcrumb, display headline, dek, meta row, "Why this matters"
  callout, an "Original reporting" card listing every source, a "More in
  {topic}" section, and schema.org `NewsArticle` JSON-LD (no image, no author).
- **Perceived performance**: `loading.tsx` skeletons for all routes and the story
  page, and relative times ("3h ago") applied after hydration.
- **Fonts**: JetBrains Mono is dropped. Inter Tight and Noto Sans Telugu load as
  variable fonts. The Telugu faces are no longer preloaded (they load via
  unicode-range only when Telugu renders), so only one font file is preloaded.

## Consequences

- CSS goes from 47 KB to 34 KB, and there is one place to change any given style.
- `scripts/visual-regression.mjs`' topic journey now navigates via the bottom
  tab bar at 390px (the header link row is desktop-only) and waits past the new
  loading skeleton. All 88 checks and the axe pass are green.
- The admin app imports the same `tokens.css`; the two new variables are
  additive and unused there.
- Revisit: `force-dynamic` on listing routes still disables ISR (pre-existing,
  presumably so builds don't need a live API); making those routes ISR is the
  next real performance win but changes the deploy/build contract.

## Alternatives considered

- **Another override round on top of the old stylesheet** — rejected; the
  override stacking was the root cause of the inconsistency.
- **Changing the Folio palette** — rejected. It is contrast-checked and shared
  with mobile, and the dated feel came from layout, not colour.
- **Generated or stock imagery for cards** — rejected (ADR-002; no rights to
  source images, and decorative stock photos would misrepresent the news).
