# ADR-014: Editorial component contract for web/mobile/admin coherence

- **Status**: accepted
- **Date**: 2026-09-17
- **Ticket**: (ad hoc — user-requested coherence redesign, no ticket file)

## Context

ADR-010 ("Folio") gave web, mobile, and admin a shared *token* identity —
warm paper, indigo accent, rust "hot" color, Telugu-aware type scale — but
never defined shared *component* identity. Each surface has since
implemented the same editorial concepts (a lead/brief story treatment, a
"why this matters" callout, save/share/report actions, a language switch, a
topic browse entry point) independently, and they have drifted apart:

- **Web** (`apps/web`) mixes several visual registers on one page: a
  newspaper masthead, rounded pills (this session's round-3 pass, commit
  `4e181de`), card-grid layout, and older "ledger" CSS (numbered dispatch
  list, hairline rules) that round 3 didn't fully remove. Every story card
  exposes Share/Save/Report as equal-weight actions regardless of whether
  the reader is scanning a list or reading one story, which makes the list
  itself harder to scan.
- **Mobile** (`apps/mobile`) is close in spirit but differs materially in
  execution: filled "Why this matters" blocks (web uses a bordered/ruled
  treatment), a colored rail web doesn't have, and emoji used as tab icons
  (not a deliberate icon system). Five bottom tabs plus a header-level
  language control reads as busy, and Topics — a first-class destination
  per product intent — has no dedicated tab or equivalent prominence.
- **Admin** (`apps/admin`) should share type and semantic status color with
  the reader-facing surfaces but stay quieter/denser; this hasn't been
  explicitly designed either way, so it's drifted toward whatever each
  admin screen's author did locally.
- **Dark mode** is a real functional gap, not a styling one: the mobile
  navigation chrome currently reads only the light token values, so it
  doesn't respond to system dark mode at all. This needs a functional
  parity fix, independent of any visual redesign.

ADR-009/ADR-010 both explicitly rejected introducing a real shared
component library (Tamagui, RN Web, etc.) across web and mobile — "V1
doesn't have the volume of shared UI to justify the migration cost yet."
That decision was about *code sharing* and isn't reopened here. But the
absence of any shared component library left a gap this ADR closes: there
was never a shared *definition* of what each editorial concept is
supposed to look like and behave like per platform, so each surface's
author made independent, reasonable-looking local choices that compounded
into visible drift. A written contract — names, responsibilities, and one
visual treatment per surface, without shared runtime code — was the
missing piece, not a component library.

## Decision

Establish a compact, named component contract that every surface
implements natively (React/CSS on web and admin, React Native primitives
on mobile) against the existing Folio tokens — no new shared package, no
new cross-platform dependency:

- **EditionHeader** — masthead + edition date + EN/తెలుగు language control
  (global header, once, not per-story) + theme control. One visual
  treatment; platform-specific chrome (sticky top bar on web, top bar +
  status bar theming on mobile).
- **StoryLead** — the first, richest story in a feed: context line,
  headline, short deck, "Why this matters," source. Always visible in the
  initial viewport on both web and mobile home.
- **StoryBrief** — every subsequent story in a list/grid: compact,
  action-light. Only Save is inline; Share and Report live in the story
  detail view, not the list. This is the single biggest scanability fix
  the user's review calls out on web, and mobile's card list should match
  it rather than exposing its own action set.
- **StoryActions** — the actual Save/Share/Report control group, used by
  StoryLead and story-detail views (full set) and StoryBrief (Save only).
  One set of states (default/pressed/saved) and one set of accessible
  labels, implemented as real platform buttons per surface — not shared
  JSX.
- **LanguageControl** — lives in EditionHeader as an edition-level control.
  A per-story language override is a explicit exception path (e.g. a
  story-detail affordance for a reader who wants just that story in the
  other language), not a per-card control repeated on every list item —
  this is what removes the density/lookahead cost on web's story cards and
  mobile's header.
- **EditorialStatus** — the "updated"/"retracted"/"under review" notice
  treatment; one visual language (ruled/tinted, matching the "why this
  matters" treatment's register) shared by web, mobile, and admin's
  moderation views, using only the existing green/amber/red semantic
  tokens (never indigo or rust, which are reserved per the color-discipline
  rule below).
- **TopicControl** — topic chips/rail on web, and an unmistakable Topics
  destination on mobile (not buried inside a fifth-tab overflow). Exact
  mobile IA (dedicated tab vs. prominent entry in Home/More) is left to the
  mobile implementation ticket, not fixed here.

Semantic color discipline, made explicit as a rule these components must
follow (previously implicit in ADR-010's token design, not stated as a
cross-surface rule):

- Indigo = navigation / selected / primary action.
- Rust ("hot") = consequential editorial context or breaking emphasis only
  — never a generic accent.
- Green/amber/red = saved/review/error states only.
- Neutral backgrounds and high-contrast rules carry most of the reading
  experience; color is not the primary hierarchy signal.

Mobile's emoji tab icons are replaced by a deliberately chosen
cross-platform icon set — deferred until the React-type dependency
conflict blocking new mobile packages (tracked in `PROGRESS.md`) is
resolved, since adding an icon library is itself a new native dependency
and per ADR-010's own precedent that's a separate, explicit go-ahead, not
something to bundle into a visual pass.

The mobile dark-mode navigation bug (nav chrome only reading light tokens)
is a functional fix, tracked and fixed independently of this contract —
it doesn't need this ADR's sign-off, just correct token wiring.

Implementation order (separate sessions, per this repo's one-ticket-per-
session norm): shared primitives/contract (this ADR) → web home/feed
rebuilt around reading priority (StoryLead always above the fold, StoryBrief
everywhere else) → mobile navigation/cards/theme parity → admin
density/status refinement → cross-surface visual regression pass (390px/
768px/desktop, light/dark, 200% zoom + large mobile text, long Telugu
headlines; user journeys: first-story visibility, topic discovery,
language switching, save/reopen).

## Consequences

Easier: every future story-related screen on any surface has a named
target to implement against instead of a fresh local decision; the
Share/Report-only-in-detail rule directly fixes the "too many equal-weight
actions" scanability complaint without a layout rewrite; color discipline
is now a checkable rule (a reviewer can ask "is this rust use consequential
editorial context, or did someone reach for it as decoration") instead of
a matter of taste.

Harder / deferred: this is a contract, not enforced code — nothing stops a
future change from drifting again the way the current state did, since
there's still no compiler-checked shared component. Revisit introducing a
real shared library (reopening ADR-009/ADR-010's rejection) only if drift
recurs after this contract ships, or if a 4th reader-facing surface is
added and the duplication cost clearly exceeds the migration cost. The
icon system and the mobile dark-mode nav bug are explicitly out of this
ADR's scope (icon system blocked on a dependency conflict; the dark-mode
bug is a plain fix, not a decision) — tracked separately in `PROGRESS.md`
so this ADR isn't gating either one.

## Alternatives considered

- **A real shared component library across web/mobile** (Tamagui, RN Web):
  rejected again, same reasoning as ADR-009/ADR-010 — still no volume to
  justify the migration cost, and the actual problem (undocumented drift)
  is solved by writing the contract down, not by forcing shared runtime
  code.
- **Fix each surface independently without a written contract**: rejected
  — this is exactly how the current drift happened; each surface's author
  made a locally reasonable choice with no shared definition to check
  against.
- **Bundle the icon-system replacement into this pass**: rejected — it
  requires a new native dependency, currently blocked by an existing
  React-type conflict; per ADR-010's precedent, dependency-adding changes
  get their own explicit go-ahead and their own change, not a ride-along
  in a visual/coherence pass.
