# ADR-057: Turn on full auto-publish for non-sensitive stories

- **Status**: accepted 2026-10-06 (owner said "set AUTO_PUBLISH_GLOBAL=true and
  AI_REVIEW_P1_STORIES=false", then "write the ADR")
- **Date**: 2026-10-06
- **Ticket**: —
- **Supersedes**: ADR-019's rejection of "Turn on `AUTO_PUBLISH_GLOBAL`"
  (Context and Alternatives). ADR-019's brief lane itself is unchanged.
- **Accepts the risk in**: ADR-011 (claim evidence sufficiency), for non-sensitive stories

## Context

The owner is the only reviewer and the review queue keeps filling. Prod was
already running with `AUTO_PUBLISH_GLOBAL=true` (checked on the worker
2026-10-06; it was turned on during an earlier rollout, see the T14 history).
That overrode ADR-019's rejection without an ADR, and this ADR records it.
With `AI_REVIEW_P1_STORIES=true` (the default), `jobs/generate.py` still holds
every story the model rates urgent as `HIGH_IMPORTANCE`. The owner wants a story
with a verifiable source to publish without review. Low-confidence or off-topic
stories should still go to review.

ADR-019 rejected turning `AUTO_PUBLISH_GLOBAL` on because of the open ADR-011
gap. A claim's `source_refs` prove only that it cites a real `SourceItem`, not
that the item says what the claim says. Under ADR-002 (`LINK_ONLY`) the stored
evidence is just the source's title, URL and publish time. Nothing checks the
AI summary or "why this matters" against the source text. That gap is still
open. This ADR accepts it rather than closing it.

## Decision

1. Prod runs with `AUTO_PUBLISH_GLOBAL=true` and `AI_REVIEW_P1_STORIES=false`,
   set in the VPS `.env.prod`. `infra/deploy/deploy.sh` keeps its conservative
   first-run defaults (`false` / `true`), so a fresh install opts in on purpose.
2. A non-sensitive story that passes every remaining check publishes its full
   AI summary and "why this matters" without a human reading it first. This
   includes urgent (P1) stories.
3. Every other hold stays in place. No code changes:
   - `SENSITIVE_CATEGORY` (immigration, legal, financial, breaking):
     NON_NEGOTIABLES #5, plus the ADR-054 breaking brief route
   - `SOURCE_RIGHTS_REVOKED`, and the source rights gate at ingest
   - `LOW_CONFIDENCE_CLASSIFICATION` and `LOW_CONFIDENCE_GENERATION`
   - `SIMILARITY_TO_SOURCE`
   - `CONTENT_RULES_FAILED` (ADR-026)
   - `NO_PAID_PROVIDER` (ADR-015)
   - stale expiry (ADR-031/032)
   - `AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH`
   - the dashboard `auto_publish` pause (ADR-031)

## Consequences

- The queue mostly holds sensitive, low-confidence and rule-failing stories.
  `AUTO_PUBLISH_DISABLED` items already in the queue get re-swept and published
  if they are still fresh and valid (`resweep_switch_queue`).
- A wrong or unsupported AI claim in a non-sensitive story can reach readers
  under the product's name before anyone sees it. Corrections and takedowns
  (the admin restore/remove tools, ADR-055) become the safety net.
- Urgent stories no longer wait, so ADR-052's alerts for `HIGH_IMPORTANCE` holds
  only fire for holds that come from other routes.
- Rollback needs no deploy: pause `auto_publish` on the dashboard (instant), or
  set `AUTO_PUBLISH_GLOBAL=false` and recreate `api` and `worker`.
- Revisit when ADR-011 gets a real evidence check, such as matching claims
  against fetched source text, or if a published error traces back to this
  path.

## Alternatives considered

- **Keep it off and rely on the brief lane (ADR-019).** The owner rejected
  this: the queue still fills faster than one person can clear it.
- **Close ADR-011 first (claim-vs-source checking).** That's the right long-term
  fix, but it needs stored source text, which ADR-002 forbids for `LINK_ONLY`
  sources. Too large to block on.
- **Lift `SENSITIVE_CATEGORY` too.** Not possible: NON_NEGOTIABLES #5. Breaking
  stories already have their own route (ADR-054).
