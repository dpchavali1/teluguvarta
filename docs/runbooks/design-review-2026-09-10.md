# Design review — 2026-09-10 (T21 follow-up)

**Status: all 8 findings addressed** in the same-day follow-up session —
see the second 2026-09-10 entry in `PROGRESS.md`'s changelog for exactly
what changed per finding, and `git log` for the commit. Verification below
is unchanged (still static-source only); re-run a live browser pass before
treating this as fully closed.

Three-agent review (UI Designer, UX Architect, Accessibility Auditor) of
`apps/web`, `apps/admin`, `apps/mobile` against T21's partial rollout of
the "Ink & Signal" design system. See `PROGRESS.md`'s T21 entry and
`docs/adr/ADR-009-single-token-source.md` for the architecture decision
this review feeds.

**Method / caveat**: the claude-in-chrome browser extension was not
connected during this review. All findings are static source verification
(reading token files, component source, computing contrast ratios by
hand) — not a live screenshot, axe-core, or keyboard/screen-reader pass.
Re-run live before treating any WCAG conformance claim (including T19's
prior "axe pass across 12 pages") as still valid.

## Top-line

All three agents independently converged on the same root issue: `apps/web`
moved to the new "Ink & Signal" system (bone/ink/signal-lime, hard edges,
offset shadows) while `apps/admin` and `apps/mobile` are still on the old
"dusk-teal/marigold" palette (soft radii, blurred shadows) — and both
files carry comments falsely claiming they mirror web. This is exactly
the divergence ADR-009 was written to structurally prevent; ADR-009's
sequencing note says fix the palette by hand first, then extract the
token source.

## P0 — fix before further visual work

1. **Port palette + shape tokens to admin/mobile** (UI Designer).
   `apps/admin/src/app/globals.css` and `apps/mobile/src/theme/tokens.ts`
   still have the old hex values (`#eef1f0`/`#b8791f`/`#1a6d61`), rounded
   radii (`--radius-lg:0.65rem`, `radius.pill:999`), and blurred shadows.
   Web's target values are already written down at
   `apps/web/src/app/globals.css:27-56` — this is a port, not new design
   work. Fix the stale "mirrors apps/web" comments in the same pass.

2. **No display/mono font stack on admin** (UI Designer).
   `apps/admin/src/app/layout.tsx` / `globals.css:30` only load
   `system-ui`. Web loads four fonts (`Bricolage_Grotesque`,
   `Inter_Tight`, `JetBrains_Mono`, `Noto_Sans_Telugu`) — see
   `apps/web/src/app/layout.tsx:3,18-42`. Single largest "looks like an
   older product" signal on admin screens (login card, story tables).

3. **Mobile buries the language toggle** (UX Architect).
   Web: one-tap, persistent header (`apps/web/src/components/SiteHeader.tsx:34`,
   `LanguageToggle.tsx`), broadcasts a live update to all visible cards.
   Mobile: two taps deep in Settings (`apps/mobile/src/screens/SettingsScreen.tsx:17`
   → `LanguageScreen`), and `StoryCard` only picks up the change on next
   mount, not live. For a bilingual-content product this is the biggest
   cross-surface IA inconsistency found.

4. **Web light-mode accent-as-border contrast ~1.2:1** (Accessibility,
   Serious, WCAG 1.4.11). `--color-accent:#c8f03f` used as a border on
   `.story-card__why` (`globals.css:896`) and `.student-briefing`
   (`globals.css:1191`) in light mode is ~1.15–1.26:1 against
   `--color-bg`/`--color-surface` (need 3:1). Dark mode is fine (14.9:1).
   Fix: use `--color-accent-strong`/`--color-rule` for these borders in
   light mode; keep raw `--color-accent` only for background+contrast-text
   pairs (already done correctly elsewhere).

## P1 — real friction, worth a ticket

5. **Admin correction form skips the sensitive-category confirm step**
   (UX Architect). `apps/admin/src/app/review/[id]/page.tsx` correctly
   gates approve/reject for `ALWAYS_REVIEWED_SENSITIVITIES` (immigration/
   legal/financial/breaking/obituary-accusation) behind a two-step confirm
   (line ~167), but the "Correct this story" form (line 292+) submits on
   one click regardless of sensitivity — a correction to a published LEGAL
   story gets the same friction as a typo fix. Extend the existing
   `isAlwaysReviewed` gate to the correction form's confirm step.

6. **Admin/mobile divider and input borders fail 3:1** (Accessibility,
   Moderate, WCAG 1.4.11). `--color-border:#c9d2cf` on white ≈ 1.54:1, on
   `--color-bg` ≈ 1.36:1 (need 3:1 for UI-component boundaries). Affects
   every input/select/textarea border in `apps/admin/src/app/globals.css:93-102`
   and table cell borders, plus unselected pill borders in
   `apps/mobile/src/components/StoryCard.tsx` using the same token. Darken
   the border token (≥3:1 against both backgrounds) or rely on background
   differentiation plus a stronger `:focus` border.

7. **Review-queue "danger only" filter doesn't persist** (UX Architect).
   `apps/admin/src/app/review/page.tsx:42` — `dangerOnly` resets on every
   page load, undercutting a queue whose design intent is surfacing
   highest-stakes items first. Persist to `localStorage` at minimum.

8. **No "Topics" nav entry outside the home feed** (UX Architect).
   Consistent between web and mobile (both only expose topic chips on
   Home), but a user who navigates to Search/Saved first has no path to
   topic browsing except returning Home.

## Verified fine — no action needed

- No non-negotiable violations found: browsing/search/saved require no
  login on either surface, mobile onboarding is skippable
  (`OnboardingScreen.tsx:21`), no UGC/comment surface exists anywhere
  (UX Architect).
- Telugu `lang="te"` handling is correct and thorough on web — applied
  per content block (not just `<html>`), with a dedicated
  `[lang="te"]` font/line-height cascade (`globals.css:159-173`) that
  correctly beats the generic class rule by specificity. Use as the
  template when porting to admin/mobile (Accessibility).
- Most existing admin/mobile text/background color pairs already pass AA
  (4.4–6.7:1) despite the outdated palette. The one pairing that fails on
  paper (white `accentContrast` text on raw `accent` = 3.63:1) is never
  actually used together in any component — worth a token-naming
  safeguard so a future component doesn't make that pairing live
  (Accessibility).
- No Tailwind config in web or admin — both are hand-rolled CSS,
  consistent with ADR-008's "no new UI framework" constraint (UI Designer).

## Recommended sequencing

1 → 2 (palette + font port), then 4 and 6 together (both contrast fixes),
then 3, 5, 7, 8 as a follow-up ticket. This matches ADR-009's own
sequencing note (fix admin/mobile by hand first, extract the shared token
source only after). Re-run a live browser/axe/keyboard pass before
sign-off — item 5 under "P0" (contrast) and the skip-link/focus-order
check flagged by the Accessibility Auditor were verified statically only.
