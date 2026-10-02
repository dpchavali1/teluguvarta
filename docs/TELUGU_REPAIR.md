# Existing Telugu translation repair — ADR-034 A

Available to ADMIN accounts in a story's admin detail (`/review/<story-id>`).
Editors can inspect current diagnostics but cannot perform these actions.
Deployment of the API and admin changes together is required; no migration.

## Review and withhold

Compare the English and Telugu text, stored QA status and the current automated
issue codes. Current checks make no read-time changes. A clean diagnostic list
is not proof of fidelity; an administrator may record a reviewed semantic
quality concern even when automated checks find nothing.

Enter a specific translation repair reason, choose **Withhold Telugu**, review
the confirmation and confirm. The API sets Telugu to FAILED, retaining text for
editor inspection, and records actor, reason, issue codes, statuses and hashes.
New API responses use English fallback and Telugu-only search matches disappear.
English, story status/publication, rights and existing review tasks are unchanged.
Repeated withholding of the same already-FAILED text consumes no retry reset.

## Regenerate explicitly

After withholding, enter a reason and choose **Regenerate Telugu**, then confirm.
The API deletes the withheld Telugu row and translation work state atomically,
recording an `AI_RETRY_RESET` with repair origin. This shares the existing two
manual resets per story/TRANSLATE stage with exhausted-AI retries. The UI reports
the remaining allowance. At the cap, text and work state are retained; there is
no automatic reset or database-edit workaround.

The ordinary translation sweep generates the replacement. Existing AI/translation
flags, privacy routing, cost controls, retry backoff, glossary, QA and sensitive
review sampling apply. A paused or disabled pipeline waits; a failed replacement
remains English fallback. Repair grants no publication or review approval.
Archived/retracted and other non-translatable story states cannot regenerate.

Regeneration removes the old Telugu text under ADR-004's one-row policy. Audit
hashes/reasons remain; there is no parallel translation-history store. Review
the new output, including native-speaker assessment where needed.

## Failure and freshness

- A stale-text error means another action changed the English/Telugu text.
  **Reload translation status**, review the new text and enter a new reason.
  The submitted request carries both observed text hashes.
- A missing-variant response after an attempted regeneration may mean another
  administrator completed it. Reload before deciding the next action.
- Failed requests retain the reason and show an error. Confirmation/cancel and
  disabled busy controls protect against accidental requests; server locking
  and the shared cap also serialize concurrent repair/reset requests.
- An in-flight model response is discarded if English, Telugu, retry state or
  the manual-reset audit history changed while it was running. This includes
  repairs that leave both variant and work state absent. An obsolete failure
  cannot restore reset state.
  Actual gateway costs already incurred remain logged.
- Website ISR/client caches and cached phone stories may show earlier text
  until their normal refresh. Withholding does not remotely purge devices or
  define a new offline expiry policy. Verify new server responses separately
  from cached presentation.

## Verification and production evidence

API regressions: `cd apps/api && .venv/bin/pytest -q tests/test_telugu_repair.py`
(local scratch Postgres databases and fake AI responses). Admin browser fixture
reproduction is in `apps/admin/README.md`; it intercepts all API traffic.

Deployments do not automatically quarantine or regenerate older variants.
Production repairs are explicit administrator actions with a reviewed reason.
Record deployed API/admin revision, a reviewed quality sample and any repair
outcome separately in PROGRESS; unit/browser fixtures do not establish native
language fidelity or production inventory health.
