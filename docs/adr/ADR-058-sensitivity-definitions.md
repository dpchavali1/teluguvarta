# ADR-058: Define the sensitive categories in the classifier prompt

- **Status**: accepted 2026-10-06 (owner: "system should be sensible enough to decide if we
  have a verifiable link its ok to publish .. if confidence is low and topic does not seems
  good that can be sent to review"; then "start making changes and complete all that is needed")
- **Date**: 2026-10-06
- **Ticket**: —
- **Clarifies**: NON_NEGOTIABLES #5 (scope of "immigration, legal, financial, breaking").
  Does not amend it. Builds on ADR-057.

## Context

The model sets `sensitivity`, and any value other than `NONE` forces human review
(`SENSITIVE_CATEGORY`). That is NON_NEGOTIABLES #5, with ADR-054 as the only
exception. Neither #5 nor SPEC defines the categories, and the classifier prompt
only listed their names. For a Telugu-diaspora product, nearly every story touches
visas, money or courts, so a story that merely features immigrants, a company or a
court could be tagged and held. Unknown values also fall back to `BREAKING`
(`FALLBACK_SENSITIVITY`). The owner reports that the queue keeps filling with
stories that have a verifiable source link and should publish.

## Decision

The classifier prompt (`SENSITIVITY_CRITERIA` in `app/jobs/generate.py`) now
defines each category by what a reader might act on:

- **IMMIGRATION:** new or changed visa, green-card, status, consular or
  enforcement rules, deadlines, fees or guidance, or deportation/detention of
  people. A story that only features immigrants doesn't count.
- **LEGAL:** court rulings, lawsuits, or new laws/regulations a reader might act
  on. Routine politics doesn't count.
- **FINANCIAL:** tax, investment, banking, remittance or exchange-rate
  information a reader might act on with their money. Business or market news
  without such guidance doesn't count.
- **BREAKING:** a major unfolding event whose facts may still change. Recent or
  important news alone doesn't count; that is what urgency is for.
- **OBITUARY_ACCUSATION:** a death, or an allegation against a named person.

When unsure, the model still picks the sensitive value. No routing code changes:
anything that meets a definition is held exactly as before, and the confidence,
similarity, content-rule, rights and budget holds still apply.

## Consequences

- Fewer `SENSITIVE_CATEGORY` holds. Ordinary diaspora, business, politics and
  community stories go through ADR-057's auto-publish path.
- The model's reading of the definitions decides the boundary. Spot-check the
  first day of auto-published stories for any that should have been held. If
  one slips through, tighten the wording rather than removing the definitions.
- Only new classifications change. Stories already held keep their tags. Clear
  them through the queue, or bulk-clear them (ADR-055).

## Alternatives considered

- **Remove `SENSITIVE_CATEGORY` review for stories with a source link.** Rejected:
  that breaks NON_NEGOTIABLES #5, which only the owner can amend explicitly
  (as ADR-054 did for breaking news).
- **Keep the prompt and rely on the confidence threshold.** Rejected: sensitivity
  forces review whatever the confidence, so the threshold has no effect here.
