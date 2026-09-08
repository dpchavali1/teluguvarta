# ADR-003: Database job queue strategy

- **Status**: accepted
- **Date**: 2026-09-08
- **Ticket**: T08

## Context

`docs/SPEC.md` §14 defines a Postgres-backed job queue covering 15 job types
across ingestion, AI, editorial, and notifications, and NON_NEGOTIABLES #2
rules out Redis/Celery outright. T03 already created the `jobs` table shape
(`status`, `attempts`, `run_after`, `lock_expiry`, `locked_at`, `dedupe_key`)
but nothing has ever claimed or processed a row from it. T08 (`source_fetch`)
is the first ticket to actually run a job, so three things need to be settled
before any worker code is written, per the ticket's own instruction:

1. The exact claiming SQL pattern, so two workers can never both process the
   same job.
2. The worker deployment shape: a managed cron trigger per job type, versus
   one persistent worker process.
3. Retry/backoff parameters, so a failing job is bounded (NON_NEGOTIABLES
   #10) rather than retried forever or silently dropped.

## Decision

**Claiming pattern.** A worker claims one job at a time with:

```sql
SELECT * FROM jobs
WHERE type IN (:job_types)
  AND (
    (status = 'PENDING' AND run_after <= now())
    OR (status = 'RUNNING' AND lock_expiry < now())
  )
ORDER BY run_after
FOR UPDATE SKIP LOCKED
LIMIT 1;
-- then, in the same transaction:
UPDATE jobs SET status='RUNNING', attempts = attempts + 1,
  locked_at = now(), lock_expiry = now() + interval '5 minutes'
WHERE id = :claimed_id;
COMMIT;
```

`FOR UPDATE SKIP LOCKED` means a second concurrent claimer never blocks on a
row a first claimer already holds, and never picks that same row — each
`claim_job` call either gets a distinct job or nothing. Committing the
`RUNNING` update immediately (rather than holding the transaction open for
the job's full duration) releases the row lock right away, so it doesn't
block other workers' claim queries while the job actually runs.

The `OR (status = 'RUNNING' AND lock_expiry < now())` branch reclaims jobs
whose worker crashed mid-run, without a separate sweep process: a 5-minute
lock TTL is long enough for one `source_fetch` run, short enough that a
crash doesn't stall a job past a typical `refresh_minutes` cadence.

Implemented in `apps/api/app/jobs/queue.py::claim_job`.

**Worker deployment shape: one lightweight always-on worker process**
(`python -m app.jobs.worker`), not a managed cron trigger per job type.

§14 lists 14 job types spanning ingestion, AI, editorial workflow, and
notifications, and more tickets will add handlers for most of them over the
build. A managed-cron-per-type approach means provisioning and maintaining N
separate scheduled triggers that drift out of sync with the codebase as
tickets land; a single polling worker keeps job processing to one deployable
unit, which is also the more natural fit for "modular monolith, no
microservice fleet" (NON_NEGOTIABLES #3) than N independent scheduled
functions. It needs no infrastructure beyond "keep one process running,"
which V1 already needs for the API itself, and it gives near-immediate
pickup for jobs where poll-to-cron latency would matter later (e.g.
`notification_dispatch`, `review_reminder`) instead of being bound to a
fixed cron tick.

Cost is one small always-on instance rather than paying nothing between cron
ticks — acceptable for V1 scale against §19's cost goals. Revisit only if a
specific job type's ops or cost profile actually diverges enough to justify
decoupling it onto its own managed schedule.

**Retry/backoff.** `attempts` increments at claim time (so it counts total
runs, not just retries). `MAX_JOB_ATTEMPTS = 5`; on the 5th failure the job
is left `FAILED` — a terminal, observable row with `last_error` retained —
instead of being rescheduled again (NON_NEGOTIABLES #10: bounded retries,
never an infinite loop). Backoff between attempts is exponential:
`60s * 2^(attempts - 1)`, capped at `3600s` (1 min, 2 min, 4 min, 8 min,
16 min for attempts 1-5).

**Source-level circuit breaker is separate from job-level retry.** Job
retry/backoff (above) governs one job's lifecycle; the §6.5 circuit breaker
acts on `sources.fail_count` across many job runs over time. The
`source_fetch` scheduler refuses to enqueue a new job for a source once
`fail_count >= 5`, until an admin/editor investigates — `fail_count`,
`last_success_at`, and `last_error_at` are already exposed via T06's
`/v1/admin/sources` fields. This is deliberately manual-reset (no auto-clear
timer): ADR-002's addendum already flagged rights/health auto-checks as a
T08/T18 follow-up, not something to half-build here.

**Idempotent recurring scheduling.** Rather than tracking "is a job already
queued for this source" with a separate query, `schedule_due_source_fetches`
computes a time-bucketed `dedupe_key` (`source_fetch:{source_id}:{window}`,
where `window` floors "now" to the source's `refresh_minutes`) and relies on
the existing unique `jobs.dedupe_key` constraint with `ON CONFLICT DO
NOTHING`. Calling the scheduler any number of times inside the same cadence
window enqueues at most one job for that source; a fresh key becomes
available automatically once the next window starts.

## Consequences

- One deployable worker process to run, monitor, and scale — not N cron
  schedules — as more job types land in later tickets.
- A crashed worker or process restart loses at most one job's progress
  mid-run (bounded by the 5-minute lock TTL), not the whole queue.
- Source-level health (circuit breaker) and job-level retry are tracked
  independently and both surface through existing admin fields — no new
  admin UI needed for T08 to satisfy its acceptance criteria.
- Revisit the single-worker choice if job volume or latency needs ever
  diverge sharply by job type (e.g. `notification_dispatch` needing
  sub-second dispatch while `cleanup` runs hourly) — split into multiple
  worker processes filtering by `type`, still against the same table and
  claiming pattern, before reaching for a broker.

## Alternatives considered

- **Managed cron trigger per job type**: rejected — N schedules to
  provision and keep in sync with code as §14's 14 job types get
  implemented across the remaining tickets; also a worse fit for the
  modular-monolith constraint than one worker process.
- **Postgres advisory locks (`pg_advisory_lock`) instead of `FOR UPDATE
  SKIP LOCKED`**: rejected — advisory locks need the caller to manage lock
  keys and explicit unlock/session-scoping; `SKIP LOCKED` is the standard,
  simpler pattern for exactly this "claim one row from a queue table"
  shape and ties the lock to the row's own transaction.
- **Redis/Celery**: ruled out outright by NON_NEGOTIABLES #2.
