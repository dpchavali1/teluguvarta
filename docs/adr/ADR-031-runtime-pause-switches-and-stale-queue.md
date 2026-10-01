# ADR-031: Dashboard pause switches for AI and auto-publish; stale queue expiry

- **Status**: accepted (owner delegated the design, 2026-10-01)
- **Date**: 2026-10-01
- **Ticket**: none (ops request after the 2026-09-30 auto-publish rollout)

## Context

Two problems surfaced on the admin dashboard on 2026-10-01:

1. **The review queue held 376 stories, oldest 3 days.** `AUTO_PUBLISH_GLOBAL`
   was off until 2026-09-30 ~23:08 UTC, so every non-sensitive story got a
   review task tagged `AUTO_PUBLISH_DISABLED`. Turning the flag on only
   affects stories reaching `AI_READY` afterwards — the existing tasks stay
   pending forever, and the news in them is now stale.
2. **An admin cannot stop the pipeline from the dashboard.** The §15 kill
   switches are env vars (`GET /v1/admin/kill-switches` is read-only), and AI
   spend only stops when the budget or hard cap (ADR-024) is reached.
   Stopping anything means SSH, editing `.env.prod`, and a restart.

## Decision

### Two switches, stored in the database

A `runtime_switches` table (`key` PK, `enabled`, `updated_by`, `updated_at`,
`note`) holds:

- **`ai`** — when off, no AI provider is called. The worker stops claiming
  `ai_classify`, `ai_translate`, `ai_summarize` jobs (they wait in the queue,
  so no retry attempts are used up and no story is pushed to review as
  "AI retries exhausted"). The gateway also refuses every call with
  `DEFERRED` as a backstop, which covers the two AI calls inside other jobs:
  clustering falls back to title matching only, and the brief lane is
  skipped. Ingestion keeps running; new stories wait as `DRAFT` and are
  picked up when AI is switched back on.
- **`auto_publish`** — when off, nothing is published automatically.
  Stories that finish AI wait in `AI_READY` (no review task is created, so
  the queue does not fill up) and the brief lane does not run. Stories an
  editor approves by hand still publish: that is a human decision.

A missing row means **on**. The env vars stay as a hard ceiling:
`AUTO_PUBLISH_GLOBAL=false` keeps auto-publish off whatever the dashboard
says (the dashboard shows it as locked by server setting). Effective state =
env allows it AND the dashboard switch is on. NON_NEGOTIABLES #5 is
unchanged: sensitive stories never auto-publish under any switch state.

Only an `ADMIN` can flip a switch (`PUT /v1/admin/switches/{key}`); every
flip writes an `AuditEvent` (`RUNTIME_SWITCH_CHANGED`). Switches are read on
each worker loop / sweep, so a flip takes effect within one poll, no restart.

### Stale stories expire instead of queueing

`STALE_AFTER_HOURS` (env, default 24) applies whenever auto-publish is
effectively on:

- A story in `REVIEW_REQUIRED` whose only pending reason is
  `AUTO_PUBLISH_DISABLED` (optionally with a brief-lane suffix) was queued
  only because auto-publish was off. The sweep re-runs it through the normal
  automatic gates (sensitivity, source rights, ADR-026 content rules). If it
  is fresh it is auto-approved like any other story; if it fails a gate, its
  task reason is replaced with the real reason so an editor sees why.
- If it is older than `STALE_AFTER_HOURS` (age = when its English draft was
  generated), it is archived (`REVIEW_REQUIRED -> ARCHIVED`), its task
  closed as `REJECTED` with decision `STALE`, audited as
  `STORY_EXPIRED_STALE`.
- Stories that waited in `AI_READY` during an auto-publish pause get the same
  age check on resume: stale ones are archived the same way (via
  `REVIEW_REQUIRED`, the only legal path), fresh ones publish.

Stale expiry never touches a story held for a real editorial reason
(sensitive, low confidence, content rules, rights, AI failure): those stay
in the queue until a person decides.

## Consequences

- Pausing is one click and takes effect within one worker poll; resuming
  picks up exactly where it stopped.
- The queue now contains only stories that genuinely need a person. The
  current 376 backlog clears itself on the next publish sweep after deploy:
  fresh ones publish, old ones are archived (all audited, reversible by an
  editor only through normal tooling — archived is final in the state
  machine, which is acceptable for days-old news).
- While AI is paused, clustering is title-match only, so near-duplicate
  stories may be created; they are merged or reviewed as usual later.
- Two sources of truth (env ceiling + DB switch) — the dashboard shows both
  so the effective state is never ambiguous.

## Alternatives considered

- **Keep env-only switches.** Rejected: needs SSH and a restart to stop
  spending, which is the problem being solved.
- **One combined "pause everything" switch.** Rejected: the common case is
  "stop publishing but keep preparing stories" or "stop spending but let
  editors keep publishing", which need separate switches.
- **On auto-publish pause, queue stories for review (current env-off
  behaviour).** Rejected: that is exactly what produced the 376 backlog.
- **Bulk-approve the backlog.** Rejected: would publish 3-day-old news as if
  it were new.
