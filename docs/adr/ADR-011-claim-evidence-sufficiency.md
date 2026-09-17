# ADR-011: Claim evidence sufficiency for unattended publish

- **Status**: proposed
- **Date**: 2026-09-16
- **Ticket**: P0-1 (`docs/plans/gemini-hetzner-telugu-plan.md`)

## Context

P0-1 fixed the two parts of the prompt-injection vulnerability in
`jobs/generate.py`/`jobs/translate.py` that a crafted feed title could
actually exploit today: unescaped interpolation into the prompt (now
JSON-encoded inside a random boundary) and the gateway's evidence check
accepting any non-empty `source_refs` without checking the ids named real
`SourceItem`s in the cluster (now `AiGateway._check_claims` HOLDs the whole
result on a fabricated ref, rather than silently stripping and publishing).

What P0-1 did **not** implement: even a claim whose `source_refs` all name
real cluster items isn't thereby *true* — `SourceItem` only ever stores
`title`/`url`/`published_at` (ADR-002, LINK_ONLY grants no right to store
article text), so there is no source passage to check a claim's content
against. Ref-membership proves "this id is real," not "this item supports
what the claim says happened."

The pre-existing plan under review proposes closing that gap with a
corroboration/title-match sufficiency rule: a claim is auto-publishable only
if (a) a cited item's title contains both the claim's key entity/number
*and* a matched event keyword from a fixed vocabulary, or (b) the claim is
corroborated by two cited items from distinct `Source` rows; otherwise it
routes to `REVIEW_QUEUE`, never silent auto-publish. This is a real product
tradeoff, not just a bug fix: most single-source, single-outlet clusters
(the common case per `PROGRESS.md`'s current story mix) would fail both
checks and go to review, which measurably raises the review-queue rate and
narrows "unattended publish" (§19) to "unattended for clusters meeting the
corroboration bar."

Per `NON_NEGOTIABLES.md` #11, a judgment call with product consequences like
this gets an ADR, not an implicit choice buried in a gateway helper.

## Decision

Not yet made — this ADR exists to record the choice that must be made
before the sufficiency rule ships, and to keep `main`'s claim-evidence
behavior (ref-membership only, per P0-1) legible as an intentional interim
state rather than an oversight. Candidates, none yet accepted:

1. **Adopt the plan's rule as written** (entity+event-keyword title-match OR
   outlet-diversity corroboration, else `REVIEW_QUEUE`) — closes the
   epistemic gap fully but accepts a materially higher review-queue rate for
   single-source stories.
2. **Ship ref-membership only, permanently** — accept that a real-but-content-
   unverified claim can auto-publish, on the theory that title/URL/date
   membership plus human review of `SENSITIVE_CATEGORY`/`HIGH_IMPORTANCE`
   stories already covers the highest-risk cases (NON_NEGOTIABLES #5).
3. **A narrower corroboration-only rule** (drop the title-match branch,
   keep only outlet-diversity ≥2) — simpler to audit, but forces every
   single-source cluster to review even when its title obviously supports
   the claim.

## Consequences

Until this is accepted, `_generate_story` publishes on ref-membership alone
for real refs (P0-1's fix), which is strictly safer than the pre-P0-1
behavior but not the full protection the reviewed plan describes. Revisit
before any of T22-T28 (which assume the corroboration rule exists) begins,
per `PROGRESS.md`'s 2026-09-16 entry.

## Alternatives considered

Deferred to whichever option this ADR eventually accepts — see Decision.
