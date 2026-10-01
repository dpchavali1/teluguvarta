# ADR-032: Every stale review hold expires

- **Status**: accepted (owner decision, 2026-10-01: "expire all after 24h")
- **Date**: 2026-10-01
- **Ticket**: none (ops follow-up to ADR-031)
- **Extends**: [ADR-031](ADR-031-runtime-pause-switches-and-stale-queue.md)

## Context

ADR-031 cleared the `AUTO_PUBLISH_DISABLED` backlog but deliberately left
every other hold alone. Live queue on 2026-10-01 ~22:30 UTC: 380 pending,
0 `AUTO_PUBLISH_DISABLED`, ~8 new holds an hour and nothing leaving except by
hand. 87% were over 6h old:

| reason | pending |
|---|---|
| `CONTENT_RULES_FAILED:SUMMARY_TOO_SHORT` | 138 (almost all from the 2026-09-30 23:00–01:00 rollout burst) |
| `SENSITIVE_CATEGORY` (+`HIGH_IMPORTANCE`/`LOW_CONFIDENCE_GENERATION`) | 87 |
| `LOW_CONFIDENCE_GENERATION` | 77 |
| `NO_PAID_PROVIDER` | 50 (2026-09-29/30) |
| `CONTENT_RULES_FAILED:HEADLINE_COPIES_SOURCE` | 14 |
| `TELUGU_TRANSLATION_SAMPLE_REVIEW` / `SIMILARITY_TO_SOURCE` | 8 / 6 |

Editorial capacity is far below inflow, so the queue can only grow, and an
old held story isn't worth publishing anyway.

## Decision

`publish.expire_stale_holds`, run at the start of every publish sweep
(every 2 min), regardless of `AUTO_PUBLISH_GLOBAL` and the dashboard pause,
since it only archives:

- For each story with `PENDING` tasks, age = English draft `generated_at`, or
  the oldest pending task's `created_at` when there is no draft (e.g.
  `NO_PAID_PROVIDER`). Older than `STALE_AFTER_HOURS` (default 24) → expire.
- Story in `REVIEW_REQUIRED` → `ARCHIVED`; all its pending tasks
  `REJECTED` / decision `STALE`; audit `STORY_EXPIRED_STALE` with the reasons.
- Story already in another status (e.g. a Telugu sample task on a `PUBLISHED`
  story) → only the tasks are closed; story untouched; audit
  `REVIEW_TASK_EXPIRED_STALE`.

Sensitive holds expire too. That keeps NON_NEGOTIABLES #5: expiry never
publishes, it only stops a story that a person never cleared. An editor who
wants an archived story can still find it in the content library.

## Consequences

- The queue is bounded at roughly one day of inflow (~200 now).
- The first sweep after deploy archives ~350 stories: expect a burst of
  `STORY_EXPIRED_STALE` audit events.
- Sensitive stories nobody reviews within 24h are never published. If that
  becomes a coverage problem, the answer is editor capacity or a longer
  `STALE_AFTER_HOURS`, not an exemption.
- The 138 `SUMMARY_TOO_SHORT` holds suggest the minimum-summary rule
  (ADR-026) fails most of the new Telugu-source drafts. That is a separate
  look and is not changed here.
