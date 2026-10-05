# ADR-054: Auto-publish breaking and death stories as source-text briefs

- **Status**: accepted 2026-10-04 (owner said "proceed"; owner-chosen defaults below)
- **Date**: 2026-10-04
- **Ticket**: —
- **Amends**: NON_NEGOTIABLES #5 and #15 (for BREAKING and death stories only); builds on
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

## Accepted settings (2026-10-04)

- Headline: #15's "never reproduced headline text" is relaxed for this lane only. The
  source's own headline is shown verbatim with attribution and a link; no article text or images.
- Bar: 2 independent publishers (`BREAKING_MIN_SOURCES`, default 2), counted by distinct
  registrable domain. Trusted list: `BREAKING_TRUSTED_SOURCES` (source ids or names, empty).
- Daily cap 10 (`AUTO_PUBLISH_BREAKING_DAILY_CAP`), New York day like ADR-019.
- Switches: env `AUTO_PUBLISH_BREAKING` (default off) and the dashboard `breaking` switch
  (migration `d4a8c2e6f1b3`); the dashboard `auto_publish` pause also stops this lane.
- Implementation: `app/jobs/breaking_lane.py`. Needs no AI. Takes over stories already in
  `REVIEW_REQUIRED` that are BREAKING, or sensitivity NONE held as RESTRICTED/AI-unclassifiable
  with a death term in a source title (the ADR-052 rule). Items older than 24h stay in review.
  The AI draft is replaced; it is kept in the audit event. Undo is the existing retract action.
- English headline comes from a non-Telugu source title; with none, the story stays in review.
  Telugu is a Telugu-language source's own headline, else no Telugu variant (English fallback).
  `source_text` variants are skipped by `ai_translate`.

## Consequences

- Faster breaking and death coverage; a human decides only the single-source,
  untrusted and sensitive-category cases.
- A coordinated or erroneous report across two approved sources would publish.
  The alert, unpublish and kill switch bound the exposure; they do not remove it.
- Two-source matching reuses clustering, so a wrong merge could count one
  publisher twice or two events as one. Needs a publisher-independence check
  (distinct source domains) and tests.
- Implementation touches `publish.py`, `translate.py` and the switches, adds
  `breaking_lane.py`, and amends the NON_NEGOTIABLES text. It needs
  tests for the hoax case (one source only), the two-source case, and the
  kill switch. 
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

## Open questions (resolved 2026-10-04 with the defaults above; owner populates the trusted list)

1. Which sources, if any, go on the single-source trusted list?
2. Is 2 independent sources the right bar, or 3?
3. Daily cap value (suggest 10)?
4. Accept the amended wording for NON_NEGOTIABLES #5?
