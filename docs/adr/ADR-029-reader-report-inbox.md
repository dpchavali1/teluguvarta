# ADR-029: Reader-report inbox — storage, retention, abuse controls, access

- **Status**: proposed
- **Date**: 2026-09-30
- **Ticket**: review R6 (`docs/reviews/2026-09-30-live-product-and-admin-plan.md`)

## Context

Web and mobile story cards have a "Report an issue" form. It posts
`{event: "report_issue", properties: {story_id, description}}` to the
unauthenticated `POST /v1/events` (`apps/web/src/lib/api.ts::reportIssue`,
`apps/mobile/src/lib/api.ts`). `app/analytics.py::track` writes it to the
structured log and forwards it to PostHog with `description` stripped. Nothing
else happens: no table, no admin view, no state. A report the reader was told
was "sent" is only findable by grepping container logs, and those rotate.

Gaps today, independent of the inbox:

- `AnalyticsEventIn.properties` is an unbounded `dict`. The web textarea has
  `maxLength=2000`, but the API accepts any size, any keys, and any `story_id`
  (it isn't checked to exist).
- `/v1/events` has no rate limit (`app/rate_limit.py` covers search and admin
  only). Anyone can write arbitrary text into our logs at volume.
- Report text can contain a reader's name, email or phone. It sits in logs
  with no retention rule, against SPEC §16 "retention schedules, cross-system
  deletion job".

SPEC §17 lists `report_issue` as an analytics event and uses "correction rate"
as a metric; it says nothing about storing, triaging or retaining reports.
NON_NEGOTIABLES #6 forbids UGC/comments. A private report that only editors see
and is never published is not UGC, but where that line sits, how long a
reader's free text is kept, and who can read it are owner/legal decisions, so
this ADR stops before implementation.

## Decision (proposed; owner to confirm the starred values)

**1. Separate endpoint and table, not analytics.** Add
`POST /v1/stories/{story_id}/reports` (no login, NON_NEGOTIABLES #9) writing a
`reader_reports` row:

`id, story_id (FK, CASCADE), category, description (nullable), language,
platform (web|ios|android), client_hash, status, resolution, resolution_note,
resolved_by (FK users, SET NULL), resolved_at, correction_id (FK corrections,
SET NULL), created_at, description_purged_at`.

The endpoint also emits the `report_issue` analytics event with only
`story_id`, `category`, `platform` — never the text, so the free text lives in
exactly one place we can delete. `/v1/events` stops accepting `description`
and the clients move to the new endpoint. Unknown story → 404.

**2. Categories (fixed enum).** `FACTUAL_ERROR, TRANSLATION, BROKEN_LINK,
WRONG_IMAGE, OFFENSIVE, OTHER`. The form gets a required category picker; the
text stays optional.

**3. Lifecycle.** `OPEN → RESOLVED | DISMISSED`, with a `resolution` enum:
`CORRECTED` (must link a `corrections` row), `RETRACTED` (story was
retracted), `NO_CHANGE`, `DUPLICATE`, `SPAM`. Every transition writes an
`audit_events` row like other admin mutations. Reports never change a story by
themselves; the editor uses the existing audited correction/retraction flows
and links the result. No assignment in V1 — there are one or two editors.

**4. Access.** EDITOR and ADMIN can list, read and resolve. Reports are never
returned by any public endpoint, feed, search or contract a reader can reach,
and no reader is told the outcome (there is no reader identity to tell). No
reply-to-reader channel in V1.

**5. Retention\*.** Recommended: description text is erased (`NULL`,
`description_purged_at` set) **90 days after resolution**, or **180 days after
receipt if still open**; the row (category, story, dates, resolution) is kept
for correction-rate metrics. A daily job does this, idempotent and bounded per
NON_NEGOTIABLES #10. Account deletion doesn't touch reports, because reports
aren't linked to accounts. Existing `report_issue` log lines age out with the
normal log rotation; no backfill from logs.

**6. Abuse controls\*.**

- Pydantic limits: description ≤ 2,000 chars, category from the enum, no extra
  fields (`extra="forbid"`); same caps on `/v1/events` properties (key count,
  value length).
- Rate limit per client address: **5 reports / 10 min and 20 / day**, via
  `app/rate_limit.py` (process-local, same as search; ADR-007's caveat holds).
  `/v1/events` gets a looser limit too.
- `client_hash` = HMAC-SHA256(server secret, client IP + UTC day). It lets an
  editor see "same sender, same day" and lets the limiter work, without storing
  an IP. It rotates daily, so it can't track a reader across days.
- At most one OPEN report per `client_hash` + story + category; repeats are
  accepted (200) but counted on the existing row, not stored again.
- No CAPTCHA in V1. Revisit if the inbox gets > 50 SPAM resolutions a week.

**7. Admin.** A "Reports" nav item with open count; list filtered by
status/category/story; detail shows the story (both language variants, sources,
status, existing corrections) next to the report, and resolve actions. Home's
attention list includes "N open reader reports, oldest Xh".

## Consequences

- A sent report becomes a record an editor must close, and "correction rate"
  and "reports per published story" become measurable from the DB.
- Reader free text lives in one table with a deletion schedule, instead of in
  logs and (if a client ever regresses) PostHog.
- Cost: one table + migration, one public endpoint, one daily job, admin
  list/detail pages, and a client change on web and mobile. Mobile needs a
  store release for the new endpoint, so the API keeps accepting
  `report_issue` on `/v1/events` (text dropped, not logged) until the old
  app version is retired.
- The process-local rate limit resets on restart and doesn't span instances;
  acceptable at current volume, same as search.
- Daily-rotating `client_hash` means abuse spread across days isn't linked.
  Accepted for privacy.

## Alternatives considered

- **Keep reports in logs, add a log viewer in admin.** No state, no deletion
  control, and log rotation silently loses reports. Rejected.
- **Store in the analytics pipeline / PostHog.** Sends reader free text to a
  third party, which `_FORWARD_REDACT` exists to prevent. Rejected.
- **Require login to report.** Cuts spam, but contradicts no-login reading
  (NON_NEGOTIABLES #9) and most readers have no account. Rejected for V1.
- **Store the raw IP for abuse handling.** More personal data than the job
  needs; the daily HMAC covers rate limiting and same-day duplicates.
  Rejected.
- **Email reports to editors.** No lifecycle, no audit, text copied into
  mailboxes outside the retention rule. Rejected.

## Owner decisions needed

1. Accept that private editor-only reports are not UGC under NON_NEGOTIABLES #6.
2. Retention: 90 days after resolution / 180 days if open — or other values.
3. Rate limits: 5 per 10 min, 20 per day per client — or other values.
4. Category list above — add/remove any.
