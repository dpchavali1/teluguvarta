# ADR-025: Recovering stories held by AI failures

- **Status**: accepted (2026-09-30): owner chose options 1 and 3; add 2 after the first outage that needs it
- **Date**: 2026-09-29
- **Ticket**: review 2026-09-29 findings #1 and backlog item 1 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

Review #1 (commit `d23d70b`, `app/jobs/ai_retry.py`) bounds AI retries per
story. When the retries run out:

- **generation**: the story goes to `REVIEW_REQUIRED` with reason
  `AI_RETRIES_EXHAUSTED`. The editor can reject it or draft it by hand.
- **translation**: `ai_work_state` is marked `EXHAUSTED` and the story keeps
  serving English. Nothing in admin shows it.

There are also older holds: `NO_PAID_PROVIDER` holds from before ADR-018, and
stories an editor would like the AI to try again once a provider or budget
problem is fixed. Today the only ways to retry are deleting the
`ai_work_state` row, or making a change that alters the stage's input. Neither
is audited, and the review asks for "audited manual recovery" and says not to
bypass review.

## Decision

Pending. Options:

1. **Admin "Retry AI" action on a held story.** Deletes the story's
   `ai_work_state` row for that stage. For generation, it also moves the story
   `REVIEW_REQUIRED → DRAFT` (an allowed transition) with its items back to
   `CLUSTERED`. Writes an `AI_RETRY_RESET` audit event with the editor and
   reason. The story comes back through normal generation and review routing,
   so review isn't bypassed. ADMIN only, and capped per story (e.g. 2 resets)
   so it can't become an unbounded loop by hand.
2. **Bulk reset after an incident.** The same reset for every `EXHAUSTED` row
   whose last status was transient (provider outage, budget), run by an ADMIN
   with a reason. Invalid-output exhaustion is excluded.
3. **Translation visibility.** List `EXHAUSTED` translations in admin next to
   the Telugu draft form, so an editor can write the Telugu or use option 1.
4. **Do nothing.** Editors reject or hand-draft exhausted stories, and
   translations stay English.

Suggested: 1 and 3; 2 once there's an outage that needs it.

## Consequences

Option 1 needs one admin endpoint, one audit action and a small admin UI
button. It adds paid calls only when an editor asks for them.

## Alternatives considered

Automatic reset after a cool-down: this is an unbounded retry loop spread
across days, which NON_NEGOTIABLES #10 rules out.
