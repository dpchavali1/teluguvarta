# ADR-020: Store public-domain government feed descriptions as evidence

- **Status**: accepted (2026-09-29; owner chose every proposed default)
- **Date**: 2026-09-29
- **Ticket**: automation plan step 4 (`PROGRESS.md`); amends ADR-002 / NON_NEGOTIABLES #15

## Context

Under ADR-002 (`LINK_ONLY`), a `SourceItem` keeps only the source's `title`,
`url` and `published_at`. So AI drafting, the ADR-015 privacy classification
and the ADR-011 claim checks all see only the headline. ADR-019 left "store
government RSS descriptions as evidence" as a separate rights decision.

The State Dept travel-advisory feed (`travel.state.gov/_res/rss/TAsTWs.xml`)
puts the whole advisory in `<description>`. Measured 2026-09-29: 216 items;
the HTML runs from 421 to 39,270 characters, with a median of 3,058. That text
is a work of the U.S. federal government, so it has no copyright
(17 U.S.C. §105). SPEC §5 lists "government/public-domain material" as preferred
and allows "store source snapshots only when permitted and needed for
provenance".

The FEMA feed returns 403 to the worker, so it ingests nothing today. NPR is not
a government work.

## Decision

1. **No new rights tier.** Sources stay `LINK_ONLY`. A new per-source flag,
   `sources.description_evidence` (default `false`), allows storing the item's
   feed description. `LICENSED_METADATA`/`LICENSED_REPURPOSE` stay unreachable.
2. **Who can turn it on:** `ADMIN` only (`FORBIDDEN` otherwise). The source must
   be `LINK_ONLY`, and `rights_evidence.public_domain_basis` must say why the
   text is public domain (for example, "U.S. federal government work,
   17 U.S.C. §105"). If either is missing, the request is refused with
   `DESCRIPTION_EVIDENCE_NOT_ALLOWED`. Every change is audited through
   `SOURCE_UPDATED`. Turning the flag off deletes every description already
   stored for that source.
3. **What is stored:** `source_items.description`. HTML is stripped, entities
   are decoded and whitespace is collapsed. The text is capped at **4,000
   characters**, cut at a word boundary. It is stored only while the source
   has the flag on and is `LINK_ONLY`. A re-fetch overwrites the text, and an
   empty description is stored as `NULL`.
4. **Internal evidence only.** The description is:
   - added to the evidence block for classification and full-story drafting;
   - passed to `classify_privacy` together with the titles, which can only
     tighten the decision;
   - shown to reviewers on the admin story page.

   Readers never see it: no public schema, feed, page or push includes it.
   **The ADR-019 brief lane stays title-only:** its prompt and its
   deterministic checks use titles alone, as ADR-019 decided.
5. **Copy guard.** Published text must stay original (ADR-002). A draft
   summary that shares a run of **12 or more consecutive words** with a
   stored description gets the existing `SIMILARITY_TO_SOURCE` review
   reason, the same as a summary too close to a source title.
6. **Scope now:** only the State Dept travel-advisory source gets the flag.
   `infra/scripts/seed.py` sets it for new installs. Prod needs an admin to set
   it once, because the seed runs only on the first deploy. FEMA stays off
   until it moves to the OpenFEMA API.

## Consequences

- Drafts of travel advisories can use the reason and level details from the
  advisory, not only the headline. Reviewers can check claims against the
  text without opening the link.
- More prompt tokens per State Dept story: up to 4,000 characters, roughly
  1,000 tokens, per item, within the ADR-018 budget.
- Advisories longer than 4,000 characters are cut off, and the full text is
  still at the link. A claim about the tail of a long advisory has no stored
  support. The ADR-011 checks treat that like any other unsupported claim.
- The description is untrusted feed content. It goes inside the same
  JSON-encoded, boundary-marked untrusted-data block as titles.
- The ADR-019 brief lane gains nothing from this. Letting briefs use
  description facts would need a new decision.

## Alternatives considered

- **Move gov sources to `LICENSED_METADATA`.** Rejected. It supersedes ADR-002
  for what is a public-domain question, not a licence.
- **Store the full description with no cap.** Rejected. Up to about 39k
  characters per item costs tokens with little extra evidence value.
- **Let briefs state description facts.** Rejected for now. It would widen the
  auto-publish lane that ADR-019 deliberately kept title-bounded.
