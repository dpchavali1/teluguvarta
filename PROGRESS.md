# Progress — current handoff

Updated 2026-10-02. This page is the current status for build-order decisions.
The [verbatim prior tracker](docs/history/PROGRESS-through-T14-search-2026-10-01.md)
preserves the full implementation chronology, commands, results, and rationale
through T14-search. See the [improvement plan](docs/reviews/2026-10-01-improvement-plan.md)
for the ordered follow-ups and the [ADR registry](docs/adr/README.md) for decisions.
Local implementation is distinct from deployment and device acceptance.

**T17-firebase (2026-10-02):** The owner selected Firebase for both mobile
push delivery and analytics. [ADR-039](docs/adr/ADR-039-firebase-mobile-push-and-analytics.md)
records native FCM delivery and separate, default-off analytics consent;
[T17-firebase](docs/tickets/T17-firebase.md) orders implementation and
activation. The owner selected `theteluguedit@gmail.com`; the dedicated
`theteluguedit-app` project is now Firebase-enabled. Android and iOS apps
were registered for `org.teluguglobal.app`, and their public native config
files are saved in `apps/mobile/` and referenced by Expo config. Native
Firebase app, messaging, and analytics modules are installed; native
prebuild passes, with Analytics and FCM auto-init default-off before JS
startup and no iOS Ad ID support. Google Analytics property `557190245` is linked to both app streams under the
existing account; optional Analytics account data-sharing choices and email
updates were turned off and verified after reload. Mobile analytics consent
is implemented locally, with safe event names only, revocation, account-
deletion reset, and updated privacy copy. Native FCM registration and token
refresh replace Expo registration. The API worker uses FCM HTTP v1 with
invalid-token retirement and bounded retries; the VPS compose mounts a
private worker credential directory. Android/iOS prebuild, final Android
release build, mobile typecheck, 85 tests, and
Android/iOS export pass; the generated Android manifest confirms Analytics
and Messaging start off. Five FCM sender tests and scoped API Ruff/mypy pass.
Database-backed notification tests were skipped locally without Postgres.
The dedicated `tte-fcm-sender` service account has only the FCM API Admin
role and FCM API is enabled. Its private credential has not been generated or
installed on the VPS. The production-URL Android release APK was installed
over the owner's attached phone on 2026-10-02 after a forced fresh JS bundle.
Android reported the original 2026-09-28 first-install date and a running
app process after launch. On reconnection, Android reported notification
permission granted and a fresh launch logged successful default Firebase app
initialization without a push-registration error. The deployed API reports
revision `abf3084` and `push_notifications_enabled=false`. A registered FCM
token and actual delivery remain unverified; device logs do not expose a
successful server registration. Analytics consent and production activation
also remain pending. ADR-038 still blocks release.

**T17 push diagnosis (2026-10-02):** Production reports push delivery disabled.
The previously installed Android APK has OS notification permission but used
Expo registration without an EAS project ID, so it could not obtain a push
token. ADR-039 replaces that path with Firebase. See the revised
[activation steps](docs/reviews/2026-10-02-push-activation.md). No live push
was sent or activated; a rebuilt app, provider credential, and device proof
are still required.

**T17 push live on Android (2026-10-02):** The `tte-fcm-sender` JSON key is
installed on the VPS (`secrets/firebase-messaging.json`, mode 0400), `.env.prod`
has `FCM_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS`, and
`PUSH_NOTIFICATIONS_ENABLED=true` (rollback: set it to `false` and
`docker compose ... up -d api worker`). On the owner's Android phone: a native
FCM token registered, a manually inserted `DAILY_BRIEFING` was `SENT` and
displayed, and a story-linked `TOPIC_ALERT` opened the story from the
background. Fixes after that test: taps now use Firebase
`onNotificationOpenedApp`/`getInitialNotification` (expo-notifications did not
see FCM taps; a cold-start tap is held until navigation is ready), and story
alerts now show the story headline (profile language; Telugu only after QA).
After deploying `4ba5c39`, a story alert showed the headline and a tap with
the app force-closed opened the story (verified on device). Quiet hours, daily
cap, breaking alerts and iOS (needs APNs key and an iPhone) remain unverified. ADR-038 still blocks release. API tests:
`test_editor_sets_event_countries_and_importance` already fails on `main` in
the full suite (passes alone); unrelated to push.

**T19-release (2026-10-02):** The VPS deploy/monitor gate now verifies that
API, admin and web serve the exact checkout revision and that public Search and
admin Review/Coverage routes respond. Admin displays the short deployed SHA.
CI checks that required admin routes are tracked. The revision probes expose
only the public Git SHA. Shell syntax and three monitor failure-path tests
pass; the focused API revision test, Ruff/mypy, admin/web lint, typechecks and
production builds pass. Database-backed API health tests could not run locally
without Postgres; the first CI run's API job passed. Its contracts job found
stale generated files, which were regenerated in the follow-up. The owner
reported deployment, and the API, web, and admin publicly report the exact
`5048385` revision; readiness, Search, Review, and Coverage return HTTP 200.
The [release smoke evidence](docs/reviews/2026-10-02-release-smoke.md) records
these checks. VPS monitor execution and recovery evidence remain open. See
[T19-release](docs/tickets/T19-release.md).
The current CI dependency scan is still red on an unpatched Expo CLI
`node-forge` advisory; accepted
[ADR-038](docs/adr/ADR-038-unpatched-expo-cli-advisory.md) keeps the audit gate
blocking releases until a published fix is upgraded and validated. The audit
gate has not been weakened.
The [public editorial baseline](docs/reviews/2026-10-02-public-editorial-baseline.md)
samples 300 recent published stories and flags publisher concentration,
missing Telugu variants and no immigration/visa/student-tagged story for
admin Coverage and editorial review; it changes no rights or publication
setting.
The owner's two-day phone testing is supported by the
[device checklist](docs/reviews/2026-10-02-device-check.md). PageSpeed's
unauthenticated mobile request returned 429; field Core Web Vitals remain
unmeasured.

**UI17 (2026-10-02):** Admin phone navigation is a compact menu with the
current destination shown. The review queue uses readable cards at phone
widths, keeps search and sensitive-only filtering at hand, and tucks the
remaining filters behind an applied-filter count. Story detail now places
source evidence immediately after the draft and its decision controls after
the review material on phones. Existing API actions, audit reasons and
human-review gates are unchanged. See [UI17](docs/tickets/UI17.md).
Admin lint, typecheck and production build pass. Live phone/browser visual
acceptance remains open. The owner confirmed seeing the new phone layout in
the installed admin web app; the exact deployed revision is now verified.
Production follow-up: `/coverage` returned 404 because its existing page was
hidden by the generic Git `coverage/` ignore rule. The rule now exempts the
admin route and the page is tracked. A clean-checkout admin build must include
`/coverage`; admin lint, typecheck and production build pass with that route
present. The redeployed `/coverage` route now returns HTTP 200.

**UI16 (2026-10-02):** Mobile Settings now has one Alerts row; its former
empty inbox path is removed. The screen keeps existing preferences, makes
the master pause state clear, disables dependent controls while paused, and
uses accessible hour/cap steppers that match the backend's whole-hour quiet
periods. Topic alert switches now default off until explicitly selected,
matching the stored subscription state. Failed server sync shows a retry and
is retried on the next visit. See [UI16](docs/tickets/UI16.md).
Mobile typecheck, 76 tests in 14 suites, and Android/iOS Expo export pass.
The release APK was built with production URLs and installed over the existing
app on the owner's attached Android phone on 2026-10-02; Android retained the
original first-install date, the app launched, and the dark Alerts screen was
visually inspected without an immediate crash. Broader real-device and live
push-delivery acceptance remain open.
Device feedback follow-up: timing controls now precede the topic list; topic
search and a selected-only filter make long general/student lists manageable.
Mobile typecheck, 77 tests in 14 suites, and Android/iOS export pass. A new
release APK with production URLs was installed over the existing app on the
attached Android phone on 2026-10-02; Android retained its first-install date
and no immediate startup error appeared. Detailed visual/device acceptance
and live push-delivery verification remain open.

**X activation follow-up (2026-10-01):** The admin Sources page can now add a
disabled `X_ACCOUNT` source and link a verified numeric X user ID, handle,
cadence and budget class. Its existing rights form remains the activation
gate. The regular RSS scheduler explicitly excludes X sources, including ones
given a feed cadence in error. See the [activation handoff](docs/reviews/2026-10-01-x-activation.md)
for official-account candidates and the live setup sequence. No production
account, X credential, or poll has been enabled; ADR-037 placement and
ADR-036 deployment topology remain open.

## Build status

| Ticket | Current status |
|---|---|
| T01–T18 | Done. The linked history records per-ticket evidence. |
| T19 hardening | **Partial.** Local MFA, deletion, security, accessibility, load, backup/restore, and app-store readiness work exists. Managed-infrastructure recovery, production alerts/rate limits/MFA journeys, live-provider golden eval, production accessibility/performance, and release/device evidence remain open. |
| T21 visual refresh | Implemented locally. ADR-035 supersedes ADR-010's palette and shapes; UI15 adds the rounded mobile pass. Native-device visual acceptance remains open. |
| T20 pilot | Removed by owner decision on 2026-09-16; no pilot gate. |

X1–X4 and S1–S2 are implemented locally. T13-repair (ADR-034 A) and
T14-search (R12 pagination) are implemented locally. UI01–UI14 are implemented
locally; UI12–UI14 still have device, language and production acceptance gates.
T19-maintenance and UI15 are implemented locally as described below. No entry
on this page implies a production deployment or app-store release.

**T19/X5 follow-up (2026-10-01, merged to main at `e1afb85`):** The requested release
proof is in progress. [Preflight evidence](docs/reviews/2026-10-01-release-preflight.md)
shows CI for `fa780eb` failed on an RSS type-only import and an unpatched
high-severity node-forge advisory in Expo CLI. The RSS import is fixed on main;
bandit, mypy, ruff, 17 focused X/RSS tests, the full API suite (564 passed),
and ten simulated restore/alert tests pass. CI remains blocked by node-forge.
No production deploy/restore/alert/
rollback has been attempted. ADR-036 awaits the actual deployment topology.
For X5, public X attribution now uses the reviewed source name instead of
raw post text while retaining the post link; API contracts expose `is_x_post`
and native cards label the original post action. Mobile typecheck, 74 tests
and Android/iOS export pass. ADR-037 awaits reader placement
and curated account approval; no X account was enabled or live post shown.

## Latest local work — 2026-10-01

**T19-maintenance:** The API mypy count fell from 70 errors in 15 files to
**zero in 81 source files**. Fixes narrow nullable database fields and AI
gateway results and type the API serialization boundaries; the CI baseline is
now zero. Ruff passes. The full API suite passes **564 tests, 10 warnings,
zero teardown errors**. This short tracker replaces the archived full text
without discarding earlier evidence. T19's release gates above are still open.

**UI15:** ADR-035 selects paired cool light/dark canvases, indigo actions,
semantic status colors, and rounded 8/12/16/pill radii. Shared tokens now
generate a nonzero mobile pill radius, fixing square controls. Mobile reading,
search, saved, onboarding, settings, and navigation controls use the refreshed
colors and shapes. Token drift and contrast checks pass. Mobile typecheck,
**73 tests in 14 suites**, and Android/iOS Expo export pass; web/admin
lint/typecheck/build pass. Synthetic Chromium search checks pass 12 EN/TE,
light/dark layouts at 320/390/1440px, keyboard paging and scoped axe with no
serious/critical findings. Phone/desktop Telugu light/dark screenshots were
inspected under `/tmp/tte-ui15-browser/`. Real-device acceptance remains open.

**T14-search:** Public newest-first EN/TE search has bounded cursor paging
across API/contracts/web/app. Web first-page/retry links retain the query;
mobile appends/deduplicates and rejects stale page responses. Earlier full API
**564 passed**, web **11 tests**, mobile **73 tests**; synthetic browser matrix
passed. Production deployment and native-device acceptance remain open.

**T13-repair:** ADR-034 A's ADMIN-only audited Telugu withholding and bounded
regeneration are implemented in API/admin, sharing the existing two-reset cap.
The API/admin must deploy together. Live translation inventory, native-speaker
fidelity, and cache/production evidence remain open.

## Next work and gates

1. On the deployed `5048385` revision, confirm migrations, public search
   cursors, repair flow, account deletion, and rollback path. Public revision
   and route smoke checks passed; the deeper journeys need production evidence.
2. Exercise T19 against managed infrastructure: admin MFA/logout and rate
   limits, backup age and restore RPO/RTO, alert delivery, and live-provider
   golden eval. Keep rights and sensitive-story review gates intact.
3. Run Android/iOS real-device journeys: light/dark appearance, safe areas,
   large system text (1.5/2.0), TalkBack/VoiceOver, offline/poor-network
   recovery, deep links, push, Telugu reading and native-speaker review.
4. Review live editorial yield, publisher/topic balance, and Telugu quality.
   Measure search relevance/latency before a ranking change. ADR-030 is needed
   for taxonomy/navigation; regional tagging and durable offline expiry need
   their own accepted decisions.
5. Measure production Core Web Vitals and mobile performance against the SPEC
   targets; complete store release evidence separately.

Personalization plan 2026-10-03: tickets P01–P08 and ADR-040 (explicit-signal
personalization) / ADR-041 (timely trackers) accepted; see `docs/BUILD_ORDER.md`.
P04 mobile done: Telugu font choice (system / Noto Serif Telugu / Mandali,
bundled, falls back to system if loading fails) and Short story length for
feed cards; font size already existed. Mobile typecheck, 89 tests in 16 suites
and bundle pass; release APK rebuilt. Not yet device-verified (Telugu glyph
rendering/bold faces need a look on the phone). P04 web parity done later (see
below); P05–P08 were built afterwards (entries below).

**P05 My Edit (2026-10-04, local, mobile only):** `packages/domain/myEdit.ts`
(pure, deterministic) builds Home sections — Top 5 today, For you, Because you
saved X — from the server-ranked page plus explicit on-device signals (ADR-040).
Mutes ("Show less") now never hide BREAKING/IMMIGRATION/LEGAL/FINANCIAL stories,
including in Latest. Every Home card has "Why am I seeing this?". Settings → My
Edit signals lists follows, hidden topics (reset) and saved count. Mobile
typecheck and jest (99) pass. Gaps: no web/API change (no server-side mutes or
sources mute; "mute source" not built); signals page resets hidden topics only
(follows/saves edited on their own screens); not device-verified.

**P07 visa bulletin tracker (2026-10-04, local, API only):** travel.state.gov
returns a Cloudflare 403 to automated fetches (checked, including `robots.txt`),
so per owner decision there is no ingest job: an editor enters each month from the
official notice (`PUT /v1/admin/visa-bulletins/{YYYY-MM}`, source link must be an
https travel.state.gov page), then approves it (`POST .../approve`). Only APPROVED
bulletins are public (`GET /v1/visa-bulletins/latest?category=&country=`, with
previous cutoff and movement). Readers follow up to 5 category+country pairs via
`follow_visa` on `/me/preferences`; approval queues one `TRACKER_UPDATE` per
alert-enabled follower whose final-action cutoff moved (the first bulletin is a
baseline, no alerts), through the normal quiet-hours/daily-cap/dedupe path.
Migration `f6c0e4a8b3d9`. API ruff, mypy and 613 tests pass. Gaps: no mobile/web/
admin UI yet; exam/deadline reminders (second half of P07) not started; a single
admin can approve their own entry (no four-eyes rule was requested); the alert
deep-links to Home, not a tracker screen; not run against managed infra.

**P06 saved stories 2.0 (2026-10-04, local, mobile only):** ADR-044 accepted: a
save stays a bookmark (ID only, no story text on the device, no offline
reading). Added on-device collections (max 20), per-story notes (500 chars) and
local read-later reminders (`expo-notifications`, deep-links to the story),
all in `tg_saved_extras_v1` (cleared by "clear data"; unsaving drops a story's
note/lists/reminder and cancels the reminder). Saved screen: list filter, an
Organize sheet per story, and "Remove unavailable" for withdrawn stories.
Mobile typecheck and jest (110) pass. Gaps: no web parity; reminders and the
Organize sheet not device-verified (permission prompt, delivery, restart); no
bundle/APK rebuild yet.

**P03 location follows (2026-10-04, local):** ADR-043 accepted (diaspora catalog,
explicit residence + origin, up to 10 follows, model-proposed tags with editor
override, new stories only). Backend: catalog `apps/api/app/content/places.py`
(TS mirror `packages/domain/places.ts` is generated and drift-tested), tables
`story_places`/`user_places` (migration `e5b9d3f7a2c8`), generation proposes
catalog ids and drops unknown ones, `PUT /admin/stories/{id}/places` (audited),
`GET /stories?place=` (subtree match, 422 on unknown), `/home?places=` ranking
term with "Because you follow Warangal", `follow_places` sync on
`/me/preferences` (cap 10, unknown dropped), per-place alert switch reusing the
topic-alert key. Mobile: Settings → Your places (search, follow, alert switch),
place stories screen with explicit empty state, Home sends follows. Gaps: AP/TG
district and US state lists are partial (more by demand, Telugu names need
native review); no admin place-editor UI yet (API only); web parity and
native-device check open; `home_state`/`home_city` remain free text.
No existing stories are backfilled, so many places start empty.

P01 persona presets done locally (2026-10-03): `packages/domain/personas.ts`
holds the seven presets and pure apply/remove logic; each preset records only
what it added (topics, alert topics, student life stage, quiet hours) so
removing it, or another preset that shares a topic, never touches the user's
other choices. Mobile: picker in onboarding welcome step and Settings → Quick
setup (reuses the student life stage, syncs alerts through the existing
preferences endpoint); web: Quick setup on the onboarding/profile page (no
alert prefs on web). Mobile typecheck, 93 tests (4 new) and web typecheck/
build pass. Not device- or browser-verified; web has no persona tests yet.

P02 smart alerts done locally (2026-10-03): [ADR-042](docs/adr/ADR-042-synced-saved-ids-and-keywords.md)
lets the client sync saved story IDs and keywords (bounded: 200 / 20x40 chars).
API: IANA home/residence zones, digest hours, per-topic urgency (instant /
breaking only / digest), keyword follows, and DIGEST + STORY_UPDATE
notifications through the existing PENDING-row dedupe, retry and daily cap;
quiet hours apply when either zone is quiet. Mobile Alerts screen has the
controls; disable-all clears the synced lists; privacy copy updated. Full API
pytest (594), ruff, mypy, mobile typecheck and 96 tests pass. NOT deployed:
migration `d4a8c2e6b1f9` must be run on the VPS first; no device push proof;
web has no alert UI; admin/web builds not rerun since contracts regenerated.


**P08 WhatsApp share card (2026-10-04, local):** [ADR-045](docs/adr/ADR-045-whatsapp-share-card.md)
Option A (owner-accepted): card from TTE-authored text only. Web route
`/story/[slug]/card?lang=en|te` returns a 1200x630 PNG (our headline, source
domain, canonical link); 404 for retracted/unpublished stories and for
link-first briefs (their headline is the source's). Web share attaches the
card via the Web Share API when files are supported, else text (headline,
`Source: domain`, URL). Renderer is HarfBuzz outlines + resvg because satori
and resvg's own text engine both mis-shape Telugu conjuncts (checked visually
on a sample). Bundled Noto Sans + Noto Sans Telugu (OFL). Mobile shares the
text only (no file-sharing module installed). Web tests (18) / typecheck /
lint / build and mobile typecheck + 112 tests pass. NOT verified: real
WhatsApp/device share sheets, Linux VPS (resvg native package), live API story.


The [historical tracker](docs/history/PROGRESS-through-T14-search-2026-10-01.md)
contains detailed earlier statuses and validation. Temporary synthetic screenshots
and logs are under `/tmp`; they are not production or device evidence.

**P04 web parity (2026-10-04, local):** Reading section on the onboarding/profile
page: text size (root font-size 90–130%, so the browser's own setting still
applies), Telugu font (Standard / Noto Serif Telugu / Mandali via next/font,
loaded on demand), and Short story length (feed cards only: 2-line summary, no
"why this matters"; the story page is unchanged). Stored in localStorage
`tg-reading-v1`, applied pre-paint as `<html>` attributes. No new AI. Web tests
(20) / typecheck / lint / build pass. NOT verified in a browser (Telugu glyph
rendering, font loading, line clamp); no dedicated Settings page on web.

**P07 exam/deadline reminders (2026-10-04, local, API only):** editor-entered like
the visa bulletin (ADR-041 addendum). `POST/PUT /v1/admin/exam-deadlines`,
`.../{id}/approve`, `.../{id}/withdraw`; public `GET /v1/exam-deadlines?exam=`
returns APPROVED, upcoming dates only. Followers sync `follow_exams` (max 10,
keys upper-cased) on `/me/preferences`; approval queues one `TRACKER_UPDATE` per
alert-enabled follower, and the notification job adds 7- and 1-day reminders
(UTC date), idempotent per user and tag. Migration `a7d1f5b9c3e2` (checked as
offline SQL only, not applied to a database). API ruff, mypy and 618 tests pass.
Gaps: no mobile/web/admin UI; no exam list was named so keys are free-form; any
https source link is accepted; a single admin can approve their own entry; alert
deep-links to Home; not run against managed infra.

**P07 tracker UI (2026-10-04, local):** contracts regenerated (they lacked the
visa/exam endpoints). Admin: `/visa-bulletins` (month + official link + one
entry per line, save draft, approve) and `/exam-deadlines` (create/edit draft,
approve, withdraw), both in the nav. Mobile: Settings → "Visa & exam trackers"
(`TrackersScreen`): follow category+country (max 5) and exam keys (max 10) with
per-item alert switch, latest approved final-action cutoff with movement, exam
dates linking to the official source; follows live on device and sync via
`follow_visa`/`follow_exams`. A `TRACKER_UPDATE` tap now opens Trackers (not
Home). Admin typecheck/lint/build, mobile tsc and 115 tests pass. Gaps: no web
reader page; admin screens have no tests (the app has no runner) and were not
exercised in a browser; mobile screen not seen on a device; exam keys are
free-form (the screen lists only exams with an approved upcoming date).

**P07 web tracker page (2026-10-04, local):** public `/trackers` on apps/web
(ISR 1h): latest approved visa bulletin final-action matrix with movement and
official link, plus upcoming approved exam dates with source links. Read-only —
web has no follows or alerts. In the footer and sitemap. Web lint/typecheck/20
tests/build pass. Not viewed in a browser; styling uses existing classes plus a
bare table, so it may want a polish pass.

**Review 2026-10-04 fixes — notifications and retraction (local, API + admin):**
[review](docs/reviews/2026-10-04-editorial-safety-and-security-review.md).
(1) A corrected story (`UPDATED`/`CORRECTION_PENDING`) can now be retracted:
API, DB transition trigger and the admin Retract button. (2) Every queued alert
is re-checked at delivery (`_obsolete_reason` in `jobs/notify.py`): a story that
is no longer PUBLISHED/UPDATED, a topic/keyword/place/breaking alert the reader
no longer qualifies for, a briefing turned off, an unsaved story's update, and a
withdrawn exam date or a dropped exam follow are marked `SUPPRESSED` with the
new reasons `STORY_UNAVAILABLE` / `NO_LONGER_ELIGIBLE` instead of being sent.
Migration `b8e2a6d4f1c3` (applied to the test DB by the suite; not to
production). Contracts regenerated. API ruff, mypy and 624 tests pass; admin
lint/typecheck pass. Not done: rights re-check at delivery (only public status),
visa-tracker follow re-check, Expo local-reminder tap handling (review medium),
the security requirements pass, and any production run.
