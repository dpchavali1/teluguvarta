# ADR-002: Source-rights approval policy

- **Status**: accepted
- **Date**: 2026-09-08
- **Ticket**: T06 (also binds T07, T11, T14, T15, X3)

## Context

`docs/SPEC.md` §5.1 defines four source-rights tiers (`DISABLED |
LINK_ONLY | LICENSED_METADATA | LICENSED_REPURPOSE`) but leaves it open how
aggressively V1 should actually use the upper tiers. `LICENSED_METADATA` and
`LICENSED_REPURPOSE` require negotiated rights/API agreements per source —
real legal and business-development work with no fixed timeline.
`LINK_ONLY` requires only that a source be publicly readable and not
prohibit linking/factual reporting, which is the normal, low-risk pattern
every news aggregator (Google News, Apple News, Feedly) already operates
under: write an original summary of the facts, link to the original for the
full story.

The product owner has decided to build and launch on `LINK_ONLY` only, to
avoid being blocked on licensing negotiations before shipping.

## Decision

**V1 (and this build phase) uses `LINK_ONLY` as the only enabled rights
tier, alongside `DISABLED` for anything not yet reviewed.**
`LICENSED_METADATA` and `LICENSED_REPURPOSE` remain in the schema/enum
(don't remove them — the data model shouldn't need a migration when this
changes) but no source may be moved into either tier without a new decision
that supersedes this ADR.

Concretely, for every enabled source:

- The published artifact is **always**: an original AI-drafted summary
  (2-4 sentences, written from the facts — not a close paraphrase of the
  source's sentences), an original "why this matters" line, prominent
  source attribution, and a clickable link to the original article/post.
- **No reproduction** of the source's own headline text, full article
  text, or images. Story cards are text-only in this phase — the "Share
  Card" branded-image feature (`docs/SPEC.md` §3.3) is **deferred**; it
  requires rights-safe imagery that `LINK_ONLY` doesn't provide, and it's
  explicitly optional in the spec ("if an image cannot be used lawfully,
  generate a text-only card").
- Rights evidence is still required before enabling a source (§5.1) — for
  `LINK_ONLY` this means confirming the source is publicly accessible and
  its terms don't prohibit linking/factual summarization, not a licensing
  agreement.
- The V1 publication rules table (§5.2) is unchanged by this ADR:
  immigration/legal/financial/breaking/obituary stories still always
  require human approval regardless of rights tier.

## Consequences

- Faster to ship: no source needs a licensing deal to be usable.
- Lower legal exposure: this is the best-established, lowest-risk reuse
  pattern (facts + original commentary + link, not reproduced expression).
- Story cards can't show a source's own photo or a branded share image yet
  — text-only sharing until a future ADR revisits `LICENSED_REPURPOSE`.
- Revisit this ADR (open a new one that supersedes it) if/when there's an
  actual licensing agreement with a specific source, or if product wants
  the branded Share Card feature back — don't quietly start using a higher
  tier without recording that decision.

## Alternatives considered

- **Pursue `LICENSED_METADATA` deals before building anything**: rejected —
  open-ended timeline, blocks all engineering progress on something outside
  engineering's control.
- **Allow `LICENSED_REPURPOSE`/images opportunistically per source**:
  rejected for now — inconsistent policy is harder to reason about and
  audit than one clear rule applied to every source.
