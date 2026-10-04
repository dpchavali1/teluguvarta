# ADR-050 — Push delivery fixes: defer, don't suppress; local briefing; foreground + channel

Status: accepted (owner, 2026-10-04: asked to fix all of the audit findings below)

## Context
An audit of the push pipeline found: quiet hours and the daily cap permanently
SUPPRESSED a row (dedupe key spent, never retried); the daily briefing was queued for
everyone at 00:00 UTC; rows queued while push was off or the credential failing burned 5
attempts and went FAILED; only 404 UNREGISTERED retired a token and an OAuth token was
fetched per send; Android had no foreground handler and no notification channel.

## Decision
- Quiet hours DEFER: the row stays PENDING with `next_attempt_at` set to the first
  moment outside quiet hours in every configured zone (home and residence). Daily cap
  defers to the reader's next local midnight; "today" for the cap is the reader's local
  day (residence, then home, then UTC). Same row, same dedupe key: no duplicates.
  The obsolete-reason check still runs at every send attempt.
- Bounded age: a still-PENDING row older than its type's max age becomes SUPPRESSED /
  `EXPIRED` (migration adds the reason). Max ages: BREAKING_ALERT 6h (stricter than the
  rest, a late breaking alert is worse than none), DAILY_BRIEFING 12h, DIGEST 12h, all
  other types 24h; exam reminders last until the deadline passes.
- PUSH_DISABLED, FCM_AUTH_ERROR and NO_FCM_TOKENS do not consume attempts: the row stays
  PENDING (re-tried every 5 minutes, bounded by expiry) with `notifications.last_error`
  recording why. Real delivery failures still use 5 attempts and backoff.
- Daily briefing: one per user per local date, created from 07:30 local (6h grace) in the
  residence/home zone, UTC when none (the digest's rule). Key `daily_briefing:{local date}`.
- Token retirement also on 403 SENDER_ID_MISMATCH and 400 INVALID_ARGUMENT whose field
  violation is `message.token`; never on other 400/401/403/5xx. The OAuth access token is
  cached until 5 minutes before expiry.
- Mobile (Android): channel `alerts` (high importance) created at startup, set as the FCM
  default channel via the expo-notifications plugin (`defaultChannel`) and in the API
  payload (`android.notification.channel_id`). Foreground FCM messages are shown as an
  immediate local notification; its tap routes via `resolveNotificationDeepLink`.
  DIGEST and STORY_UPDATE added to the deep-link types.

## Consequences
Migration must run before the new API/worker. On the deploy day a user can get one extra
briefing (old UTC-date key vs new local-date key). The mobile app needs a rebuild.
Analytics: `notification_skipped_due_to_quiet_hours` and
`notification_suppressed_by_daily_cap` now mean "deferred" (first time per row);
new `notification_expired` and `notification_waiting`.
