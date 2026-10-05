# ADR-054: Auto-publish breaking and death stories as source-text briefs

- **Status**: proposed (owner request 2026-10-04; not accepted, no code changes)
- **Date**: 2026-10-04
- **Ticket**: —
- **Amends**: NON_NEGOTIABLES #5 (for BREAKING and death stories only); builds on
  ADR-019 (brief lane), ADR-052 (priority review holds)

## Context

NON_NEGOTIABLES #5 requires immigration, legal, financial and breaking stories
to be human-reviewed. Today the brief lane (ADR-019) skips any story whose
sensitivity is not NONE or whose privacy decision is RESTRICTED, so a famous
person's death or a breaking event waits for a human. ADR-052 keeps those holds
from expiring and alerts the reviewer, but a story is still late whenever the
reviewer is not watching. The owner wants breaking news with a source link to
post without approval.

Risks that make a blanket removal unsafe: death hoaxes about living public
figures are common; one source can be wrong; and the AI summary has both hidden
a death (the Singeetham obituary published as a career feature) and could
invent one. A false "X has died" under the product's name is the costly failure.

## Decision

Allow **auto-publish without human review for BREAKING and death stories only**,
when all of these hold. Anything else stays human-reviewed.

1. **Scope.** Sensitivity BREAKING, or a death signal (ADR-052 death terms).
   IMMIGRATION, LEGAL, FINANCIAL and accusation stories are unchanged:
   always human-reviewed.
2. **Brief lane, source text only.** Published as `format=BRIEF` using the
   source item's own headline and a link to the source. No AI-written headline
   or summary is shown for these stories, so the AI cannot invent or hide a
   death. The Telugu variant is the source's own Telugu headline where one
   exists; no machine translation is shown as fact.
3. **Trust condition (either):** (a) at least **2 independent approved sources**
   (different publishers, both `LINK_ONLY` and enabled) report the same story;
   or (b) a single source on a short **trusted-source list** the owner
   maintains (owner to provide; empty by default, so nothing qualifies until
   set). A death or breaking report from one untrusted source stays in review.
4. **Alert and undo.** Every auto-published story sends the ADR-052 alert
   channel a message (headline, link, sources, reason) and is recorded in the
   audit log. The admin gets a one-click **unpublish**.
5. **Kill switch.** A runtime switch (like `auto_publish_paused`), plus an env
   flag defaulting to **off**. Nothing changes in production until the owner
   turns it on.
6. **Rate cap.** A separate daily cap on auto-published breaking briefs, to
   limit the damage of a bad feed. Excess goes to review.

Rights are unchanged: only `LINK_ONLY` sources, the rights gate is still
re-checked at publish time, and nothing outside approved sources is used (the
ADR-053 reference feeds remain monitor-only and never feed this path).

## Consequences

- Faster breaking and death coverage; a human decides only the single-source,
  untrusted and sensitive-category cases.
- A coordinated or erroneous report across two approved sources would publish.
  The alert, unpublish and kill switch bound the exposure; they do not remove it.
- Two-source matching reuses clustering, so a wrong merge could count one
  publisher twice or two events as one. Needs a publisher-independence check
  (distinct source domains) and tests.
- Implementation touches `brief_lane.py`, `generate.py`, `publish.py`, the
  alert path, an admin unpublish action, and the NON_NEGOTIABLES text. It needs
  tests for the hoax case (one source only), the two-source case, and the
  kill switch. No work starts until this ADR is accepted.
- Revisit after 30 days: count auto-published briefs, unpublishes and any
  corrections; narrow or switch off if any false death report went out.

## Alternatives considered

- **Keep full human review (ADR-052 only).** Safest; slower when the reviewer
  is away. Remains the fallback if this ADR is not accepted.
- **Auto-publish with the AI summary.** Rejected: the summarizer is the failure
  we already saw, and a wrong death is not recoverable by an alert.
- **Auto-publish any breaking story with one source link.** Rejected: one
  hoaxing or mistaken source would publish a false death or event.
- **Remove NON_NEGOTIABLES #5 entirely.** Rejected: immigration, legal and
  financial errors harm readers directly and are not time-critical in the same way.

## Open questions for the owner

1. Which sources, if any, go on the single-source trusted list?
2. Is 2 independent sources the right bar, or 3?
3. Daily cap value (suggest 10)?
4. Accept the amended wording for NON_NEGOTIABLES #5?
