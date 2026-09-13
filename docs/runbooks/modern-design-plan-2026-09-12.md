# Modern design plan — 2026-09-12

## Purpose

Make Telugu Global feel like a calm, trustworthy daily briefing: fast to scan,
easy to read in English or Telugu, and unmistakably clear about what is source
material and what is Telugu Global's original summary.

The reliability work preceding this plan is a prerequisite. The next visual
iteration should build on working saving, multilingual search, personalized
ranking, paging, and accessible reading surfaces rather than masking broken
journeys with a redesign.

## Design direction

Keep the existing **Ink & Signal** character, but use it with more restraint.
Ink is for reading and structure. The lime signal appears only for the current
choice, a primary action, or important status. The result should feel editorial
rather than like a marketing splash page.

Use the following hierarchy everywhere:

1. Story headline and short summary.
2. Context: freshness, topic, country, correction state, and why it matters.
3. Source attribution and the original-source action.
4. Personal actions: language, save, share, report.

Telugu needs first-class typography: larger effective glyph space, no negative
letter spacing, generous line height, and an explicit English fallback state.
The interface remains English-first in V1; story-language preference is not a
claim that every navigation or system label is localized.

## Product surfaces

| Surface | Desired experience | First implementation slice |
| --- | --- | --- |
| Web home | A useful story appears in the first phone viewport. | Compact briefing header, five-topic rail, current story metadata, browse-all route. |
| Story detail | Read without distraction, then act with confidence. | Reading width, clear source treatment, correction banner, persistent enough actions without obstructing text. |
| Search and saved | Recovery-oriented utilities, not dead ends. | Current empty/loading/error/retry states and clear unavailable-bookmark copy. |
| Mobile home/detail | Native, comfortable long-form reading. | Stable list loading, scrollable detail, 44pt actions, large-text QA. |
| Admin queue | Editorial triage before opening a record. | Headline and source context beside sensitivity and status. |

## System work before restyling every screen

ADR-009 is already proposed for a single generated token source. Accept it
before changing palette, typography, or component spacing again. Then build
the zero-dependency token generator it describes:

```text
packages/design-tokens/tokens.json
        │
        ├── web/admin CSS custom properties
        └── mobile typed token module
```

Tokens must cover both light and dark themes, surface/text/border contrast,
spacing, radii, shadows, motion, English typography, and Telugu typography.
CI should regenerate tokens and fail on drift. This fixes the recurring issue
where web, mobile, and admin visually diverge after a local improvement.

## Rollout sequence

### 1. Foundation

- Accept ADR-009 and generate the shared token outputs.
- Add a small semantic component inventory in each app: page frame, section
  heading, story metadata row, source action, status badge, empty/error state,
  and button styles.
- Include reduced-motion, high-contrast, focus, and text-scale behavior in the
  component acceptance checks.

### 2. Reading-first public experience

- Refine home, topic, country, search, saved, and story pages around the
  hierarchy above.
- Keep story cards text-only and source-linked, respecting ADR-002. Do not add
  article images, copied headlines, or branded social cards in this phase.
- Make personalisation visible only when it is factual: show the ranking
  explanation, not a generic "for you" label.

### 3. Mobile-native polish

- Apply the same semantic hierarchy with platform-appropriate density.
- Replace emoji action glyphs once the workspace React type-version conflict
  is resolved; use a single accessible icon source and text labels where an
  icon alone is ambiguous.
- Test dynamic type, small phones, long Telugu content, poor network, restart,
  and deep-link handoff.

### 4. Editorial productivity

- Restyle the review queue and story review screen around decision context:
  story, sources, rights, sensitivity, reason, and the required confirmation.
- Preserve all human-review gates. Visual simplification must never make an
  approval/retraction/correction action easier to trigger accidentally.

### 5. Evidence before broad rollout

- Run real-browser regression and axe checks in CI; Playwright and axe support
  have been added to the web workspace for this purpose, but browser binaries
  could not be installed in the current restricted environment.
- Test five representative journeys with Telugu speakers, students,
  professionals, and parents: find a story, switch language, open the source,
  save and reopen after restart, and report a problem.
- Measure useful-story time, source-link use, saved-story recovery, Telugu
  search success, and repeat visits. Use results to tune density and ranking,
  not taste alone.

## Definition of done for the design refresh

- A first useful headline and context are visible in the initial phone viewport.
- English and Telugu stories are readable at enlarged text size without clipping.
- Light and dark themes meet contrast and focus requirements on all three apps.
- A screen’s loading, empty, offline, unavailable, corrected, and retracted
  states are designed deliberately.
- Web, mobile, and admin consume the same generated token values.
- Keyboard, screen-reader, and real-browser regression checks run in CI.
- An editorial reviewer can make a safe decision using the queue context.

This plan intentionally does not introduce a new UI framework, account model,
content-rights exception, or content-republication feature.
