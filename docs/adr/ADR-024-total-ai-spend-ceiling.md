# ADR-024: A total AI spend ceiling, not only a degradation threshold

- **Status**: accepted (2026-09-30): owner chose options 1, 5 and 6; add 3 only with a second worker
- **Date**: 2026-09-29
- **Ticket**: review 2026-09-29 finding #2 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

`MONTHLY_AI_BUDGET_USD` (ADR-007, lowered to $50 by ADR-018) is a
**degradation threshold**. Once month-to-date cost crosses it, the gateway
refuses `SUMMARY`, `WHY_MATTERS` and `TRANSLATION_EN_TE`
(`DEGRADABLE_ON_BUDGET_BREACH`, `app/ai/tasks.py`) but keeps paying for
`RELEVANCE_CATEGORIZATION`, per §7.5. What bounds spend today:

- The check reads accumulated cost **before** a call. It reserves nothing, and
  the gateway's schema retry doesn't re-check, so one call (plus its retry) can
  cross the line.
- Classification after a breach is unbounded, except that review #1 (commit
  `d23d70b`) now caps each story at 20 transient failures and 3 invalid
  results, and caches a successful classification.
- `DAILY_AI_ALERT_USD` alerts; it doesn't block.
- A second worker could race the check. There is one worker today.
- An unset `MONTHLY_AI_BUDGET_USD` means no guardrail. Production startup
  doesn't refuse that.
- Review #3 (commit `8d7f7f2`) made logged cost more complete (thinking
  tokens, billed failures). Logged cost is still an estimate: cached input is
  priced at the full rate, and it isn't reconciled against billing.

## Decision

Pending. Options, which can be combined:

1. **Hard monthly ceiling for all paid calls.** Add `MONTHLY_AI_HARD_CAP_USD`
   (at or above the degradation budget). At or above it, every paid call is
   refused, classification included; stories wait under review #1's backoff.
   This keeps the §7.5 classification-only policy inside the band between the
   two numbers.
2. **Separate classification allocation.** Classification keeps running after
   the degradation budget until its own monthly allowance is spent.
3. **Reserve before the call.** Lock the month-to-date total, add the task's
   maximum cost (input estimate plus an output-token limit, which also needs a
   `maxOutputTokens` setting per task), then reconcile to actual usage. This is
   needed only if more than one worker runs, or if the ceiling must never be
   exceeded by even one call.
4. **Daily blocking limit.** Turn `DAILY_AI_ALERT_USD` into, or add, a daily
   hard stop.
5. **Refuse to start in production without budget variables.**
6. **Provider-side cap as a second guard.** Set a budget alert and quota cap
   on the paid Gemini Cloud project. Google's billing is delayed, so neither
   control can promise zero overrun.

Suggested minimum: 1, 5 and 6 now. Add 3 only when a second worker is added.

## Consequences

A hard ceiling means that past it, nothing new gets AI-drafted until the next
month or a budget change. Manual drafting (admin) still works, and the queue
fills with stories waiting on backoff.

## Alternatives considered

Keeping the current behaviour plus an alert: the review found it doesn't bound
total spend.
