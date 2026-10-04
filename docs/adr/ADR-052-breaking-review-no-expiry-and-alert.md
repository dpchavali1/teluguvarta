# ADR-052: Breaking/high-importance review holds never expire, and alert a human

- **Status**: proposed (owner request, 2026-10-04)
- **Date**: 2026-10-04
- **Ticket**: —
- **Amends**: ADR-032 (stale holds expire)

## Context

A death story about a famous Telugu personality never reached the feed. Such stories are
(correctly) held for human review (NON_NEGOTIABLES #5), but ADR-032 auto-archives any hold
older than `STALE_AFTER_HOURS` (24h), and nothing told anyone a breaking story was waiting.
The story aged out unseen.

## Decision

1. `expire_stale_holds` skips a `REVIEW_REQUIRED` story whose `sensitivity` is `BREAKING` or
   `OBITUARY_ACCUSATION`, or whose pending task reason includes `HIGH_IMPORTANCE`. These stay in
   the queue until a person approves or rejects them. All other classes keep the 24h expiry.
   Human approval is still required; nothing here publishes anything.
2. `check_priority_review_alerts` (run from `alerts.check_all`) sends one alert through the
   existing alert channel (log + optional `ALERT_WEBHOOK_URL`) when such a task is pending, and
   one reminder if it is still pending after 60 minutes. Deduped per review task via
   `audit_events` (`REVIEW_ALERT_SENT`); failures are recorded (`REVIEW_ALERT_FAILED`) and give
   up after 3 attempts per task and kind. No new provider, secret or table.

## Consequences

- The review queue can accumulate old priority items; editors must clear them. Rejecting is the
  way to drop one.
- Stories flagged only by RESTRICTED privacy (death words) with sensitivity `NONE` are not covered.
- Alert latency is bounded by the worker's alert cadence (every 60 loops); webhook delivery is
  fire-and-forget, so a failed POST is logged but not retried.
