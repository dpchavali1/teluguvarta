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

## Addendum (2026-09-08, T06): approval role, second approver, evidence expiry

T06 asked this ADR to record three operational decisions rather than open a
new ADR for them:

- **Who can move a source off `DISABLED`**: only the `ADMIN` role (not
  `EDITOR`). Enabling a source is the actual rights-gate decision, not
  routine content-registry upkeep — an `EDITOR` can create/edit every other
  source field (name, URLs, refresh cadence, etc.) but the API rejects a
  rights-status change off `DISABLED` from a non-`ADMIN` token
  (`FORBIDDEN`). `LICENSED_METADATA`/`LICENSED_REPURPOSE` stay unreachable
  for anyone in this build phase regardless of role.
- **Second approver**: not required in this build phase. A single `ADMIN`
  approval, with the required evidence fields (`rights_evidence_url`,
  `rights_reviewed_at`, `reviewer`) populated and an `AuditEvent` recorded,
  is sufficient given the low source count and `LINK_ONLY`-only scope. If
  the source list grows past the handful planned for V1, or a future ADR
  reopens `LICENSED_METADATA`/`LICENSED_REPURPOSE`, revisit this — dual
  control is a reasonable next step then.
- **Evidence expiration tracking**: the evidence record has an optional
  `expires_at` field, but nothing yet reads it to auto-disable a source or
  alert an admin — there is no scheduled/health-check job in the codebase
  before T08. Until that exists, expiration is a manually-reviewed field
  visible via the admin API, not an enforced control. Wiring an expiry
  check into the health/job system (T08 or T18) is a known follow-up, not
  a gap being silently accepted long-term.

## Alternatives considered

- **Pursue `LICENSED_METADATA` deals before building anything**: rejected —
  open-ended timeline, blocks all engineering progress on something outside
  engineering's control.
- **Allow `LICENSED_REPURPOSE`/images opportunistically per source**:
  rejected for now — inconsistent policy is harder to reason about and
  audit than one clear rule applied to every source.
