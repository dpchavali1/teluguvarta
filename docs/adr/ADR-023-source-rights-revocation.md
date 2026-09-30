# ADR-023: What revoking a source's rights does to its stories

- **Status**: proposed (owner decision needed)
- **Date**: 2026-09-29
- **Ticket**: review 2026-09-29 finding #7 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

Finding #7's code fix (commit `d3d09b5`, `app/content/rights.py`) rechecks
current source rights before every approval and publication:

- an `AI_READY` story with a non-`LINK_ONLY` source goes to review
  (`SOURCE_RIGHTS_REVOKED`) instead of auto-publishing or trying the brief lane;
- admin approve returns 409 `SOURCE_RIGHTS_REVOKED`;
- a `SCHEDULED` story is held unpublished and audited
  (`STORY_PUBLISH_BLOCKED_RIGHTS`), and publishes if rights are restored.

The review also says not to invent removal rules, and not to treat an inactive
(not polled) source as revoked. Three cases have no rule in the spec or ADR-002:

1. **Already-published stories.** A story is live when its source's rights
   drop to `DISABLED`. Today nothing happens to it.
2. **Mixed-source stories.** One source is revoked and the others are still
   `LINK_ONLY`. Today the whole story is blocked before publication.
3. **`SCHEDULED` stories.** The status trigger allows only
   `SCHEDULED → PUBLISHED`, so a blocked scheduled story can't go back to
   review. It waits in `SCHEDULED`, and editors don't see it in the queue.

## Decision

Pending. Options for each case:

**1. Published stories**
- (a) Leave them live. Revocation applies only to future publication. This is
  what happens today. (Recommended as the default; revisit if a source's
  terms require removal.)
- (b) Retract automatically (`PUBLISHED → RETRACTED`) and audit it. This makes
  a revocation a hard takedown, including of original summaries that only
  link to the source.
- (c) File a review task per affected story, so an editor retracts or keeps
  each one.

**2. Mixed-source stories**
- (a) Block the whole story until an editor acts. This is what happens today.
- (b) Drop the revoked source's evidence link and publish on the rest, if the
  remaining claims still cite a permitted source. This needs per-claim
  re-validation.

**3. Scheduled stories**
- (a) Hold in `SCHEDULED` and surface the hold on the admin dashboard. This is
  what happens today, minus the dashboard.
- (b) Add a `SCHEDULED → REVIEW_REQUIRED` transition (migration to the
  status trigger), so a blocked story returns to the queue.

**Cache invalidation**: whichever option removes or changes a live story must
also invalidate the web/mobile caches for its pages. That isn't wired to rights
changes today.

## Consequences

Until this is decided, the code fails safe: nothing new publishes from a
revoked source, and nothing already live changes.

## Alternatives considered

Treating `active = false` as revocation was rejected in the review. Pausing
polling (for cost or health) must not unpublish anything.
