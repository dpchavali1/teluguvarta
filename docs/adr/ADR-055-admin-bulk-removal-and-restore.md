# ADR-055: Admin bulk queue clearing, story deletion/restore, source deletion

- **Status**: accepted (owner request 2026-10-05)
- **Date**: 2026-10-05
- **Ticket**: — (owner request)

## Context

The owner reported that an admin cannot empty the review queue, cannot take
down or delete a published story in bulk, and cannot delete a source. Retract
existed per story but only inside the story page; rejecting one story at a
time does not scale when a bad source floods the queue. The story status
state machine (DB trigger `enforce_story_status_transition`) had no way back
from `ARCHIVED` or `RETRACTED`, so an accidental mass action could not be
undone.

## Decision

1. **Bulk story actions** (`POST /v1/admin/stories/bulk`, ≤200 ids): `reject`
   (to DRAFT), `archive`, `retract`, `restore`, `delete`. Each story is
   checked against the same status rules as the single-story endpoint and
   audited individually; ineligible stories are skipped and reported, never
   forced.
2. **Clear the review queue** (`POST /v1/admin/review-queue/clear`, ADMIN
   only, reason required): archives (default) or rejects-to-draft every
   PENDING task matching the queue's current filters. Archive is the default
   because a story rejected to DRAFT is re-generated and returns to the queue.
   Clearing never publishes anything, so NON_NEGOTIABLES #5 is unaffected.
3. **Restore**: new transitions `ARCHIVED -> REVIEW_REQUIRED` and
   `RETRACTED -> REVIEW_REQUIRED`, opening a fresh PENDING review task with
   reason `RESTORED`. A restored story is never republished directly; it goes
   back through human review (NON_NEGOTIABLES #5).
4. **Hard delete** (`POST /v1/admin/stories/{id}/delete`, ADMIN only, reason
   required, any status): removes the story and its dependent rows (FK
   cascades). The `AuditEvent` keeps the slug, status and English headline so
   the deletion stays traceable. Retract remains the recommended way to take a
   story down; delete is for content that should not exist at all.
5. **Source delete** (`POST /v1/admin/sources/{id}/delete`, ADMIN only, reason
   required): refused with 409 `SOURCE_HAS_STORIES` while any story links to
   one of the source's items — published attribution must never dangle. The
   admin deletes or keeps those stories first (the Stories page filters by
   source), or deactivates the source instead. Unlinked source items are
   deleted with the source; X accounts cascade.
6. **One-click activate/deactivate** for sources in the list, through the
   existing PATCH and its ADR-002 gate (a DISABLED source still cannot be
   activated).

## Consequences

- Removal is fast and reversible except for delete, which needs ADMIN plus a
  typed confirmation in the UI.
- Deleted stories' public URLs 404 rather than showing a retraction notice.
- Revisit if editors (not just ADMIN) need clear/delete.

## Alternatives considered

- Soft delete column on stories: duplicates RETRACTED/ARCHIVED semantics.
- Cascade-deleting a source's stories on source delete: silently removes
  multi-source stories' content; rejected in favour of an explicit two-step.
- Restore straight to PUBLISHED: bypasses review for sensitive categories.
