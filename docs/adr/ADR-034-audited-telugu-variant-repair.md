# ADR-034: Audited repair of existing Telugu variants

- **Status**: accepted — option A, owner 2026-10-01; implemented locally, not deployed
- **Date**: 2026-10-01
- **Ticket**: T13 follow-up / improvement plan item 3 (R2)

## Context

ADR-004 keeps one variant per language and serves Telugu only when its stored
`qa_status` is `PASSED`. New translations and editor drafts run the current
deterministic QA checks, including R2's mixed-script check. Existing PASSED rows
are not revalidated on reads. The September 30 review found examples that would
fail newer checks; this proposal does not claim a fresh production inventory
audit or native-speaker assessment.

The existing translation sweep processes stories with no Telugu row. A FAILED
row therefore stays unavailable without regeneration. ADR-025's manual retry
only resets an EXHAUSTED AI state; it cannot repair an existing PASSED or FAILED
row. Editor-written variants are restricted to `REVIEW_REQUIRED` stories.
English correction deletes Telugu and permits regeneration, but changing
correct English solely to repair Telugu would misrepresent the correction.

Before this decision there was no accepted rule for who may withhold an existing translation, how
that action is audited, or whether it may consume another AI retry allowance.
NON_NEGOTIABLES #11 requires a decision instead of inventing those rules.

## Decision

The owner accepted option A on 2026-10-01. Option B remains a considered alternative.

### Option A — audited withholding and bounded regeneration (accepted)

1. Show the current deterministic Telugu QA issue codes in admin detail,
   separately from the stored QA status. A diagnostic read makes no database
   changes, AI calls or public serving-policy changes. Passing these checks
   does not establish translation fidelity.
2. An ADMIN may withhold an existing Telugu variant with a nonblank reason.
   An English variant must exist. Set Telugu to FAILED and preserve its text
   for inspection; leave English, story status, publication timestamps,
   source rights and review tasks unchanged. Allow a reasoned quality concern
   even when deterministic QA reports no issues. Do not mass-change old rows
   automatically or perform production repairs as part of deployment.
3. Use the existing audit table to record actor, story, reason, observed QA
   issues, prior/new QA status and text/input hashes. No parallel variant
   history table or copied full text in audit metadata.
4. Offer a separate, explicit ADMIN regeneration action for an existing FAILED
   Telugu variant on a story in the translation sweep's existing allowed
   statuses. It deletes that row and resets translation AI work state in the
   same transaction. Record an `AI_RETRY_RESET` event with stage `TRANSLATE`,
   repair origin, reason, hashes and reset number.
5. Share ADR-025's existing **two manual resets per story/stage** cap with this
   action, including earlier exhausted-attempt resets. Reaching the cap must
   not delete the variant or reset work state. Withholding itself does not
   consume a reset or invoke AI. No automatic revalidation/retry loop.
6. Regeneration runs through the existing translation sweep, internal gateway,
   privacy routing, AI pause/translation flags, cost controls, bounded retry,
   glossary, QA and sensitive-category sampling. It grants no publication or
   review approval. Missing/failed Telugu continues to fall back to English.
   Existing human review of sensitive stories remains required.
7. Serialize repair/reset operations on the story and require expected English
   input and Telugu text hashes. Reject stale editor requests; repeated
   withholding of the same already-FAILED text is harmless and consumes no
   retry allowance. Concurrent resets must not spend beyond the shared cap.
   An in-flight translation must not attach output derived from superseded
   English or overwrite a newer editor variant; verify current inputs/row
   state and reset audit history before storing the generated result. This also
   detects a repair that leaves variant and work state absent, as before the call.

### Option B — audited withholding only

Implement Option A's diagnostics and withholding (items 1–3 and corresponding
conflict handling), but defer regeneration. Existing bad translations become
English fallback. Leave published English untouched; published manual Telugu
editing and new retry eligibility remain out of scope pending another decision.

Neither option authorizes production data edits or a bulk repair command.

## Consequences

- A bad translation can be removed from new API responses without retracting
  correct English or abusing the English correction flow.
- Option A can consume AI budget only after an explicit administrator action,
  under existing caps. When AI is paused or translation disabled, regeneration
  waits and readers continue to get English.
- The existing one-row lifecycle means regenerating a withheld row removes its
  text; audit hashes/reasons remain, rather than introducing translation history.
- Existing web ISR/client caches and phone cached copies may show earlier text
  until their normal refresh. This decision does not promise immediate remote
  cache purging or redefine offline expiry. Describe that limit in admin copy
  and the repair runbook; verify new responses fall back correctly.
- QA issue codes are diagnostics, not proof of semantic correctness. A reviewed
  native-speaker sample is still needed for the quality acceptance gate.
- No migration, provider SDK, new infrastructure, source approval or taxonomy
  change is proposed.

## Implementation acceptance

The scoped implementation ticket is `docs/tickets/T13-repair.md`.
API tests must cover RBAC, blank reasons, missing English, existing PASSED/FAILED
variants, public/search English fallback, audit metadata, unchanged English and
publication/review state, repeat/stale requests, and (for A) shared reset caps,
concurrent requests, paused/disabled AI, QA failure and stale in-flight output.
Update generated contracts; verify admin typecheck/lint/build and confirmation,
failure and diagnostic UI states. No provider calls or live repairs in tests.
Record deployment and native-speaker evidence separately.

## Alternatives considered

- Revalidate/mutate every old variant on public reads: adds writes to reader
  requests and changes serving policy implicitly; defer a separately audited
  bulk inventory/repair procedure if needed.
- Delete every flagged row and let the sweep retry automatically: loses useful
  inspection text and can create repeated paid attempts without an explicit
  bounded administrator action.
- Edit English merely to invalidate Telugu: records a misleading English
  correction and obscures the translation-only problem.
- Serve flagged Telugu with a warning: conflicts with ADR-004's fallback rule.
- Add append-only translation history: conflicts with ADR-004's current storage
  choice and has no approved consumer requirement in this scope.
