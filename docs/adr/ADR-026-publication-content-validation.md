# ADR-026: Minimum content for a published story, by format

- **Status**: accepted (2026-09-30): FULL rules (b), (c) and (d), not (a); manual drafts follow the same rules; owner fixes the two live stories by hand
- **Date**: 2026-09-29
- **Ticket**: review 2026-09-29 finding #6 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

Both live stories repeated their headline as the summary and had no
why-matters text. Nothing enforces a minimum today:

- Manual drafting requires only a nonblank headline and summary.
  `why_matters` is optional.
- `GenerationResult` accepts empty strings.
- The full-story similarity check compares the summary with the source title
  only. Nothing compares our headline with our own summary.
- Approval (manual and automatic) and final publication each check different
  things, or nothing.

What a "full story" must contain is a product decision, not something the
spec defines, so it stops here for the owner.

## Decision

Pending. One central `validate_for_publication(story)`, run at manual approve,
auto-approve and `publish_due_stories`, with rules chosen from:

- **FULL** requires:
  - (a) a nonempty why-matters (yes / no);
  - (b) a summary that isn't the headline: normalized similarity below a
    threshold, suggested 0.8 (yes / no);
  - (c) a minimum summary length, suggested ≥ 2 sentences or ≥ 25 words
    (yes / no / other number);
  - (d) a headline not too similar to any source title, using the same 0.6
    title check the summary uses (yes / no).
- **BRIEF**: ADR-019 already defines it (one sentence of at most 30 words, an
  original headline, a "Brief" label). The review saw no Brief badge on the
  live stories. Neither was a brief, so that's consistent, but the label
  should be checked in the web/mobile UI.
- **Manual drafts**: the same rules as AI drafts (yes / no). If yes, admin
  approve gets a 422 with the failed rule, like `NO_ENGLISH_DRAFT`.
- **The two live stories**: edit by hand to meet the rules, or leave them.
  The review suggests manual review.

## Consequences

Stricter rules mean fewer stories publish until drafts improve, and more
editor work on manual drafts.

## Alternatives considered

Prompt-only fixes: the review found the prompt alone didn't prevent a repeated
headline.
