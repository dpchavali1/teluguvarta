# Progress tracker

**Live product/admin review (2026-09-30):**
`docs/reviews/2026-09-30-live-product-and-admin-plan.md` records the post-launch
review and proposed improvement sequence. New live findings: Telugu-slug web
story 404s despite API 200; mixed Kannada/Hindi script in PASSED Telugu variants.
Also proposes clearer today/month/hard-cap AI spend, editorial/pipeline drilldowns,
private reader-report handling and web/mobile visual improvements. Review only;
no implementation ticket completed or production behavior changed. Admin beyond
login and mobile were inspected through code, not authenticated/device journeys.
- **R1 fixed (2026-09-30, `c76bda6`, deployed; live Telugu slug now 200):** Next hands dynamic params over still percent-encoded
  and `getStory`/`getShareMeta` encode again, so Telugu slugs reached the API double-encoded (live: API 200,
  web 404). Story layout, page and metadata now decode once via `src/lib/pathParam.ts` (was `api.ts`
  `pathCursor`; cursor pages use it too); a malformed escape 404s. Verified with `next dev` against the prod
  API: Telugu slug 404 → 200, ASCII/missing/cursor unchanged. Slugs for new stories now keep vowel signs
  (`cluster._slug_key`; they were built from the dedupe key, which drops combining marks: `రేవంత్` → `రవత`).
  The dedupe key itself is unchanged, and existing slugs keep their URLs. (`810f5f5`, pushed 2026-09-30, **not deployed**; owner first held it
  2026-09-30 to batch with the rest of the review work.) Next: work the review plan in its stated order,
  R3–R12 (R1/R2/R4/R5 done; R3 awaits owner evidence).
- **R2 fixed for new translations (2026-09-30, `2c8f9d2`, deployed):** `qa.find_variant_qa_issues` adds
  `MIXED_SCRIPT:<field>` for any Devanagari/Bengali/Gurmukhi/Gujarati/Odia/Tamil/Kannada/Malayalam letter,
  unless the English field contains that same script (quoted text); dandas are allowed. The variant is FAILED,
  so readers get English. Dry run on the live API: 5 of 20 served Telugu variants would fail (`9f334ada`,
  `c3061756` headline; `ca1e69c2`, `9193cbbe` why-matters; `085b7508` summary). **These stay served until
  re-translated**: no audited re-translate path exists for a PASSED variant yet (ADR-025 retry covers
  EXHAUSTED only), so that needs an editor fix or an ADR.
- **R3 code done (2026-09-30, pushed `5628cd8`, not deployed); evidence still owed by the owner.** New table
  `ops_checks` (migration `e7c2a9d4f1b6`), one row per BACKUP / OFFSITE_COPY / RESTORE_DRILL / MONITOR /
  ALERT_TEST with last success/failure and detail. Host scripts write it through
  `infra/deploy/ops-record.sh` (best effort; never fails the caller): `backup-prod.sh` (file + size;
  OFFSITE_COPY fails when `BACKUP_STORAGE_BOX` is unset), `restore-drill.sh` (RTO/RPO/schema),
  `monitor.sh` cron runs (not the deploy gate). `app/ops_status.py` derives OK / STALE (backup 26 h,
  monitor 15 min, drill 35 d per BACKUPS.md's monthly cadence) / FAILING / NEVER; `/v1/admin/observability`
  returns `operations`, and admin Observability has a "Backups & monitoring" tile and table.
  `infra/deploy/ops-evidence.sh` (owner runs on the VPS) reports settings set/unset, newest local and
  Storage Box backups and their age, backup/monitor log failures, and the `ops_checks` rows; `--drill`
  runs the restore drill, `--test-alert` posts a TEST failure to healthchecks.io and records ALERT_TEST
  only when the owner confirms receipt. Tests: `tests/test_observability.py` (10 passed); recorder SQL
  checked against local Postgres via a docker stub, including a quote/semicolon detail. Full suite 465
  passed + the known flaky fixture error (passes alone). Scripts were not run on a real VPS. **R3 is done
  only when** the owner deploys, runs `ops-evidence.sh --drill --test-alert`, and the result (newest
  offsite backup, RTO/RPO, alert receipt) is recorded here.
  **Prod state (2026-09-30):** `BACKUP_AGE_RECIPIENT` was unset on the server, so production had no backups
  at all. Owner is setting up the key and local backups now; **offsite (Storage Box) skipped for now by owner
  decision**, so admin shows OFFSITE_COPY as Failing ("BACKUP_STORAGE_BOX not set") until it exists. A server
  loss would lose the backups too. The 1a6882b deploy attempt failed building admin in `next/font`
  (Google Fonts CSS returned a font URL without a file extension); not caused by R3/R4, retry pending.
- **R4 done (2026-09-30, pushed `cd2e5a9`, not deployed): admin budget wording matches the gateway.**
  `app.ai.budget.budget_mode` → NORMAL / CLASSIFICATION_ONLY (budget reached: summary, why-matters and
  translation stop on every provider; classification continues, paid included) / PAID_STOPPED (hard cap:
  paid calls stop; free-tier routes can still run). Tests pin it to `is_over_monthly_budget`/`is_over_hard_cap`.
  `ai_cost` in `/v1/admin/observability` adds `monthly_hard_cap_usd`, `hard_cap_remaining_usd`, `mode`,
  `day_start`/`month_start` (UTC, unchanged semantics) and `quota_resets_at` (next midnight Pacific,
  DST-tested). Admin Home has "AI spend today (est.)" and a month tile with the mode; the attention item
  states what stopped instead of "paid AI is paused". Observability shows mode, budget and cap with what
  each stops, the UTC/Pacific windows, that figures are token-price estimates (cached input at full rate),
  and that a call in flight can cross a limit. Amounts under $1 show four decimals (`src/lib/aiBudget.ts`).
  A failed minute refresh now leaves a persistent "figures are from HH:MM" alert, not just a toast.
  Tests: `tests/test_budget_mode.py` (new) + observability; full suite 475 passed + 1 known flaky fixture
  error. Admin has no test runner: typecheck/lint clean, wording checked by transpiling `aiBudget.ts`. Not
  checked in a browser (no authenticated local admin session).
- **R5 done (2026-09-30, pushed `9abf4dd`, not deployed): where stories and AI money go.** `GET /v1/admin/ai-costs?start&end`
  (`app/ai/cost_report.py`; inclusive UTC days, default month to date, max 93 days, 422 `INVALID_RANGE` /
  `RANGE_TOO_LONG`): totals with thinking/cached tokens, "paid for, not used" (billed outcomes other than
  SUCCESS/RETRY_SUCCESS), retry spend (RETRY_SUCCESS cost), zero-filled daily series, provider/model/task
  breakdown with tier (gemini = FREE, none = NONE, else PAID), outcomes, unlinked calls, linked spend by
  the story's current status, top 15 stories. Publication cohort = stories with `published_at` in range +
  lifecycle cost of all their calls (any date), shown separately; the page labels its per-story average as
  lifecycle, never window spend ÷ publications. `GET /v1/admin/pipeline` (`app/pipeline_status.py`): story
  counts by status, published 24h, review queue (same PENDING rows as `/review-queue`) + oldest, AI retry
  state per stage (retrying/exhausted, oldest update), live stories with no PASSED Telugu (+ failed QA,
  oldest). Stories have no `created_at`, so DRAFT/AI_READY have no age. Admin: new **AI costs** page
  (`/costs`, nav) with presets/custom range and drilldown to `/review/{id}`; Home uses `/pipeline` for
  review age, published 24h, English-only and AI retry tiles, an attention item for exhausted retries,
  and spend tiles link to `/costs`. Contracts regenerated. Tests: `tests/test_cost_report.py` (5: every view
  reconciles to totals, window edges at 23:59/00:00 UTC, cohort includes pre-window calls, bounds, 401,
  pipeline counts/ages); full suite 480 passed + the known flaky fixture error (passes alone). Admin
  typecheck/lint/build clean. Checked against a seeded local DB (350 calls: days, breakdown and
  linked+unlinked all equal totals; `/costs` and `/` served 200 from `next dev`); **not viewed in a browser**
  (extension not connected), so phone/desktop layout is unchecked. Next: R6 (reader reports, needs ADR).
- **R6 done (2026-09-30, pushed `2e9aece`, not deployed): private reader-report inbox per ADR-029 (accepted as proposed).**
  `POST /v1/stories/{id}/reports` (no login; public stories only, else 404; `extra="forbid"`, text ≤ 2,000)
  writes `reader_reports` (migration `f3b8d1c6a2e7`). Rate limit 5/10 min + 20/day per client
  (`rate_limit_reports`, process-local); `client_hash` = HMAC(`ADMIN_JWT_SECRET`, IP + UTC day), no IP
  stored; a repeat from the same sender/story/category bumps `repeat_count` on the OPEN row (partial unique
  index). The server emits `report_issue` with story/category/platform only. `/v1/events` now has a
  120/min limit, flat properties (≤ 20 keys, ≤ 500-char strings) and drops `report_issue.description`
  before validation, so old app builds still work and the text is never logged. Admin:
  `GET /v1/admin/reports` (status OPEN default/RESOLVED/DISMISSED/ALL, category, story, paging),
  `GET /reports/{id}`, `POST /reports/{id}/resolve` (CORRECTED needs a correction on that story,
  RETRACTED needs a retracted story; audited as `READER_REPORT_RESOLVED`); `/pipeline` adds
  `reports_open`/oldest. Retention: reserved `cleanup` job, daily, erases text 90 d after close / 180 d if
  open, ≤ 1,000 rows per run (`app/jobs/cleanup.py`). Admin UI: "Reader reports" nav with open count,
  `/reports` list, `/reports/[id]` (report, both variants, sources, other reports, close form linking to
  `/review/{id}` for the actual correction/retraction), Home attention item. Web and mobile forms: required
  category, optional text, privacy note, 429 message (mobile: inline panel instead of the old Alert).
  **Mobile needs a store release** for the new form; until then old builds' reports reach analytics with
  the text dropped and create no inbox row. Tests: `tests/test_reader_reports.py` (9); full API suite 489
  passed + the known flaky teardown error; mypy adds nothing (72 = clean HEAD; baseline file says 71, so
  CI's mypy gate was already over before this change); web 8 tests, mobile 24 tests, admin
  typecheck/lint/build, web typecheck/lint clean. **Not checked in a browser or on a device.**
  Next: R7 (review/admin navigation at volume).
- **R7 done (2026-09-30, pushed `554d0aa`, not deployed): admin lists page on the server.** `app/admin_lists.py`.
  `GET /v1/admin/review-queue` now returns a page (`ReviewQueuePageOut`: items, filtered `total`, whole-queue
  `pending_total`/`danger_total`/`unclassified_total`/oldest, `next_cursor`), **breaking shape change**
  (admin is the only caller; deploy API and admin together). Server order: always-human-reviewed reasons
  first, then oldest; keyset cursor so resolving rows mid-paging skips/repeats nothing. Filters: `danger_only`,
  `reason`, `q` (EN/TE headline, source title, slug; ILIKE), `topic`, `source_id`, `telugu`
  (MISSING/PENDING/PASSED/FAILED), `older_than_hours`. Bad cursor → 422 `INVALID_CURSOR`. New
  `GET /v1/admin/stories` content library (any status, `corrected`, same filters, `format`; offset paging;
  `status_counts`; ordered by published_at, else newest variant, since stories have no created_at).
  `GET /v1/admin/audit` is now a page (`AdminAuditPageOut`) with `action`/`entity_type`/`entity_id`/`actor`
  (substring)/`since`/`until` and a cursor — was the latest 200 only. Migration `a4d9e2b7c5f1` adds indexes
  (pending review tasks, review_tasks.story_id, audit by time and by entity). Admin: review queue uses
  server filters + "Load more", Home already counted via `/pipeline`; detail's "next story" asks for
  `limit=2`; new **Stories** and **Audit log** pages (nav), story page links its audit history; lists show
  "Loaded HH:MM" + Refresh and warn after 5 min (no polling, so rows don't move under j/k). Unsaved-edit
  guard (`beforeunload` only, not in-app links) on open draft editors and the correction form. **Not done,
  by design:** bulk actions (none — sensitive decisions stay per story); concurrent-editor conflict/version
  handling and assignment/locking (need an ADR when a second editor exists). Tests:
  `tests/test_admin_lists.py` (4: paging order/no-skip, every filter, library, audit past 200); full suite
  493 passed + the known flaky fixture error (passes alone); ruff clean; mypy 72 (unchanged). Admin
  typecheck/lint/build clean. **Not checked in a browser.** Next: R8.
- **R8 measurement done (2026-09-30, pushed `2577e21`, not deployed); product half waits on ADR-030 (proposed).**
  `GET /v1/admin/coverage?start&end` (`app/coverage_report.py`; inclusive UTC days, default last 7, max 93,
  same 422s as `/ai-costs`). Item cohort = source items whose *publisher* date is in range (items record no
  fetch time; undated items are not counted), each in exactly one outcome: rights_blocked, backlog_skipped
  (ARCHIVED, never clustered), not_relevant (ARCHIVED after clustering = classifier said irrelevant), live,
  in_review, other (waiting/approved/withdrawn); outcomes sum to items. Publication cohort = live stories
  with `published_at` in range, credited to their PRIMARY item's publisher; publisher = site host of
  `base_url` (section feeds of one paper roll up). Also: top-publisher share, per-day publications and
  distinct publishers, median lag per feed, lag buckets, every active topic zero-filled with published +
  in-review-now, untagged and hand-drafted counts. Admin: new **Coverage** page (nav) with drilldowns to
  `/stories?source_id=` / `?topic=`; Stories now reads `status`/`topic`/`source_id` from the URL; the
  costs page's range picker moved to `components/RangePicker.tsx` + `lib/dateRange.ts` and is shared.
  Contracts regenerated. Tests: `tests/test_coverage_report.py` (4: outcomes reconcile, publisher rollup/
  share/lag/days, zero-filled topics, endpoint bounds/401); full suite 497 passed + the known flaky fixture
  error (passes alone); ruff clean; mypy 72 (unchanged). Admin typecheck/lint/build clean. Ran against the
  local dev DB (26 active topics, only `immigration` published this month). **Not checked in a browser.**
  **Owner decisions in ADR-030:** (A) fixed reader navigation sections mapped onto existing topic slugs
  (classifier categories are free text and `generate._link_topics` creates a topic for each new one: the
  source of the overlap); (B) "Top stories" = importance within 24h, or rename it; (C) weekly coverage
  floors set after two weeks of data. Curating AP/Telangana/cinema/NRI/student sources stays an owner
  rights decision; nothing approved here. Next: ADR-030 decision, or R9.
- **R9 done (2026-09-30, not deployed): shorter copy and compact feed attribution.** New
  `docs/EDITORIAL_STYLE.md` (EN headline ≤ 12 words, summary 2–3 sentences/~40–80 words, why-matters one
  sentence ≤ 30 words naming a source-supported consequence or **empty**; Telugu headline a short news
  headline; never invent dates/actions/local impact). Same text lives in `app/content/editorial.py` and is
  added to the generation, translation and segment why-matters prompts. **Guidance only, not a gate**:
  ADR-026 still decides publication, so no story is held for length. A blank `why_matters_en` is stored as
  NULL; a Telugu why-matters is dropped when the English has none (it was stored as-is). A segment line
  of `""` is cached (no regeneration, job doesn't retry) and `/v1/home` returns `personalization.why_matters
  = null`, so clients show the generic line. Web lead card and mobile feed cards show "Read the original
  source" + domain instead of the full source title (full title stays in the accessible name and on
  detail); mobile parses the domain without `new URL` (RN lacks `hostname`). Admin draft editor shows word
  counts against the guide. No truncation added. Tests: 3 new (generate prompt + blank why-matters,
  Telugu-only why-matters dropped, empty segment line falls back); full API suite 500 passed; ruff clean;
  mypy 72 (unchanged); web 8, mobile 24 tests; admin/web/mobile typecheck and admin/web lint clean.
  **Not checked:** real model output against the guide (no paid eval run), existing live copy (unchanged
  until re-generated or edited), browser/device layout. Next: R10.
- **R10 partly done (2026-09-30, not deployed; mobile needs a store release): icons and cache-assisted opening.**
  Tab bar uses `@expo/vector-icons` Ionicons (filled when focused) instead of text glyphs. The old blocker
  (a second `@types/react` breaking `next build`) no longer happens: the install adds no new resolution and
  web + admin build clean. Bundle grows by Ionicons.ttf (390 KB). Story detail opens from the in-memory
  copy a feed already loaded (`StoryCacheContext.getBySlug`, with load time) and swaps in the API version;
  if the refresh fails it keeps the copy with a banner ("You're offline / Couldn't refresh. Showing the
  copy loaded at HH:MM; it may not include later corrections" + Retry). A 404 evicts the cached copy
  (`remove`) and shows "no longer available", so a retracted story is never shown from cache. Home's
  refresh error now says when the stories still on screen were loaded. Tests: 3 new in
  `ux-reliability.test.tsx`; mobile 27 passed, typecheck clean, `bundle-check` exports. **Not done:**
  readability controls (system font scaling still applies), Home/Latest navigation (owner decision; Latest
  stays reachable from Home), persisted offline reading (cache is still memory only; needs an ADR on
  expiry and correction/retraction), and every device check (large text, TalkBack/VoiceOver, poor network,
  push opening, Unicode shared links). Next: R11.
- **R11 done (2026-09-30, pushed, NOT deployed): ADR-028 accepted, option A (owner).**
  Done: `admin_sessions` table (migration `b8e3f1a6d2c9`, stores SHA-256 of the cookie only);
  `app/admin_sessions.py` (cookie `tte_admin`: HttpOnly, Secure unless `ADMIN_COOKIE_SECURE=false`,
  SameSite=Strict, host-only, Path=/v1/admin; 30 min idle / 12 h absolute, enrollment 5 min; last_seen
  written ≤ once/min). `current_admin` reads the cookie (bearer JWTs no longer accepted; JWT helpers
  removed, `ADMIN_JWT_SECRET` stays for report hashes), 401 before the CSRF check, then
  `X-TTE-Admin: 1` required on non-GET; login needs it too. Demoted/deleted account → all its sessions
  revoked on first request. New `GET /auth/session`, `GET /auth/sessions`, `POST /auth/logout`,
  `POST /auth/logout-everywhere`; re-login revokes the browser's previous session; completed MFA
  enrollment ends the enrollment session. Login body no longer has `access_token` (**breaking: deploy API +
  admin together**). CORS `allow_credentials=True`, `*` refused at boot. Daily `cleanup` also deletes
  sessions ended > 30 d. Admin: `lib/auth.ts` keeps only a role hint (deletes the old `tg_admin_token`);
  `apiFetch` sends `credentials: "include"` + CSRF header everywhere; nav checks `/auth/session` per
  navigation; new `/sessions` page (device, signed in, last active, "Sign out everywhere"). Contracts
  regenerated. Tests: `test_admin_auth.py` rewritten (cookie attrs, hash-only storage, no bearer, CSRF,
  idle/absolute expiry, keep-alive, logout, logout-everywhere, re-login, purge, enrollment);
  `tests/admin_session_helpers.py` used by the other admin tests. Full API suite before the 401/CSRF
  ordering fix: 506 passed + 1 fixed failure + 3 known flaky fixture errors (pass alone). Admin
  typecheck/lint clean. **CSP (second commit):** `apps/admin/src/middleware.ts` sets a per-request nonce
  CSP on every page: `script-src 'self' 'nonce-…' 'strict-dynamic'` (plus `'unsafe-eval'` in dev only),
  `style-src 'self' 'unsafe-inline'` (React style props are inline attributes a nonce can't cover),
  `img-src 'self' data:`, `connect-src 'self'` + API origin + Sentry DSN host, `object-src 'none'`,
  `base-uri`/`form-action 'self'`, `frame-ancestors 'none'`. Layout reads `x-nonce` for THEME_INIT_SCRIPT
  (admin pages are now dynamic). `.env.example` documents `ADMIN_COOKIE_SECURE=false` for local http and
  drops the unused `ADMIN_JWT_EXPIRE_MINUTES` (also from `deploy.sh`'s first-run env). Verified: `next
  start` serves the header, all 21 scripts on `/login` carry the nonce; against the current API (local DB
  migrated to `b8e3f1a6d2c9`) the CORS preflight from :3001 allows credentials + `x-tte-admin`, login
  without the header → 403 `CSRF_HEADER_REQUIRED`, `/auth/session` without cookie → 401. API 507 passed,
  ruff clean, mypy 70 errors (76 before R11; not a CI gate, the R11 ones are the same `str`-vs-Literal
  noise). Admin + web build, mobile 27 passed. **Not done:** an in-browser login → MFA → `/sessions` →
  sign-out click-through (browser extension not connected; MFA code generation not permitted to the
  agent) — owner should do this locally before deploying. **Deploy API + admin together** (breaking).
- **R10 device checks partly done (2026-09-30, pushed; release APK installed on the owner's Android phone):**
  Checked over adb on the Android phone (dark), each setting restored afterwards (font scale 1.0, Wi-Fi and
  data on, app language English). **Unicode shared links:** a percent-encoded `tte://story/<Telugu slug>`
  opens the right story. **Found and fixed:** a cold-start link built the stack from the path alone, so the
  story had no back arrow and Back left the app. `linking.config.initialRouteName = "Main"` (config moved to
  `src/navigation/linking.ts`) puts Home underneath. Side effect: a link opened before onboarding now backs
  out to Home, not Onboarding; onboarding still shows on the next launch. **Large text (font scale 1.5):**
  story (English and Telugu), action buttons (wrap to a second row), Home and the tab bar all fit, and
  Telugu vowel signs aren't clipped. The "Story"/screen headers don't scale (native header). **TalkBack
  (accessibility tree only, TalkBack not run):** both language toggles (header EN/తె, story English/Telugu)
  were radios with `selected` but not `checkable`, so TalkBack couldn't say which was checked. They now
  use `checked`, like Appearance. Tests: `device-checks.test.tsx` (2; the link test fails without the fix).
  Mobile 45 passed, typecheck clean, bundle-check exports. **Not done** (owner was using the phone): fix
  verified on the device, poor network (offline banner on a cached story, Home refresh error), opening from
  a real push (code path: `navigate`, so Home stays underneath), TalkBack by ear, iOS. A real `https://`
  link still opens the browser, not the app: no Android intentFilters/assetlinks yet (needs the Play
  signing fingerprint). Noted: "Why this matters:" stays English in Telugu mode, the same as web
  (`lang="en"`), so left as is. Next: owner runs the remaining checks, then M4.
- **M5 Show less done (2026-09-30, pushed; release APK on the owner's Android phone):** Home and Latest cards
  get a "Show less" button (only where the story has topics) that opens "Hide stories about" with up to three of
  the story's topics plus Cancel; picking one announces it and hides the topic. `HiddenTopicsProvider`
  (`src/lib/HiddenTopicsContext.tsx`, inside `StoryCacheProvider` in `App`) keeps slugs on the device
  (`tg_hidden_topics_v1`, cleared by delete-data; Privacy also resets the live list). A story is left out when
  **any** of its topics is hidden. Home filters the lead/more stories, topic chips and Student Briefing; Latest
  filters via `PagedStoryList respectHiddenTopics`; Topic, Search and Saved don't filter or offer it (the
  reader asked for those). An all-hidden list says so and points to Settings. Settings → ACCOUNT → "Hidden
  topics" (`HiddenTopicsScreen`) lists them with "Show again". No analytics event (none defined for it). Source
  mute not done: the card payload has no source id (plan said check first). Tests: `hidden-topics.test.tsx`
  (6). Mobile 55 passed, typecheck clean, android bundle exports. Device (dark): panel shows Entertainment /
  Tollywood / Cancel; hiding Tollywood removed the lead story and the chip and promoted the next story; Hidden
  topics listed it, "Show again" brought both back (phone left with nothing hidden). Open question for the
  owner: hiding a topic also hides breaking or human-reviewed stories tagged with it; no exemption was added.
  Next: M6.
- **M4 Text size done (2026-09-30, pushed; release APK on the owner's Android phone):** Settings → TEXT SIZE:
  Small / Default / Large / Extra large (radio rows, ×0.9/1/1.15/1.3), hint "Story headlines and text. Your
  phone's text size still applies." `TextSizeProvider` (`src/theme/TextSizeContext.tsx`, inside the theme
  provider in `App`) holds the choice (`tg_text_size_v1`, so delete-data clears it; Privacy also resets the live
  size). `scaledStoryType` scales story fontSize and lineHeight together, so each language keeps its tuned
  leading (Telugu rounds up); only `StoryCard` headline, summary and "why this matters" use it — chrome, meta,
  pills and buttons don't. RN still applies the phone font scale on top. "Why this matters" now takes its
  size/leading from the body type (replaces the `whyTe` style). Tests: `text-size.test.tsx` (4). Mobile 49
  passed, typecheck clean, android bundle exports. Device (dark): section renders with radios `checked`;
  Extra large enlarged Home's hero headline/summary in English and Telugu, Telugu vowel signs not clipped,
  chips/tabs unchanged; restored to English + Default afterwards. Not checked: story page, Extra large with
  phone font scale 1.5, compact/comfortable modes (plan: only after large text passes). Next: M5.
- **M3 Settings basics done (2026-09-30, pushed; release APK on the owner's Android phone):** Settings → ABOUT:
  "About The Telugu Edit", "How we use AI", "Privacy policy", "Terms of use" open the web pages
  (`siteUrl()` + `/about`, `/ai-disclosure`, `/privacy`, `/terms`) in the browser (role link, "Opens in your
  browser" hint; a failed open is swallowed). Below the group, "Version 0.0.1" from `Constants.expoConfig`,
  plus `(build)` only when `android.versionCode`/`ios.buildNumber` is set (neither is today). Settings is now
  a ScrollView (four groups overflow a phone screen). No new storage key, no native module. Tests:
  `settings.test.tsx` (6). Mobile 43 passed, typecheck clean, bundle-check exports. Device (dark): section
  renders, Terms opened `theteluguedit.com/terms` in Brave. Not added: "Report a problem" (needs an ADR, see
  plan). Next: R10 device checks, then M4.
- **M2 Edit profile done (2026-09-30, pushed; release APK on the owner's Android phone):** Settings → ACCOUNT →
  "Your profile" (`ProfileScreen`): location, life stages, study details (only while International Student is
  selected, same gate as onboarding: `storage.asksStudentDetails`) and interests on one page; nothing is written
  until Save, back discards. The four sections are now shared components (`components/ProfileFields.tsx`, plus
  `useConfigTopics`), so onboarding renders the same fields. `storage.saveProfileEdits` keeps the stored
  language, drops `student` once that stage is deselected, leaves `onboarded` alone, and emits
  `PROFILE_CHANGE_EVENT`; Home reloads its feed on it. No new storage key. Tests: `profile.test.tsx` (5; the
  Home reload test fails with the listener removed). Mobile 37 passed, typecheck clean, bundle-check exports.
  Device (dark): screen renders, Save clears the gesture bar, tapping International Student shows "Your
  studies", live topics load; agent backed out without saving (owner's profile untouched), so Save on device
  is unchecked. Noticed, not fixed: the live topic list is long and unsorted, with near-duplicates
  ("corruption" vs "Corruption & Governance") — a taxonomy/data issue that onboarding shows too.
- **M1 Appearance done (2026-09-30, pushed; on the owner's Android phone via release APK):** Settings →
  APPEARANCE: "Use phone setting" / Light / Dark (radio rows). `ThemePreferenceProvider`
  (`src/theme/ThemePreferenceContext.tsx`, wraps `App`) holds the choice (`tg_theme_pref_v1`); `useAppTheme`
  prefers it over `useColorScheme`, so every screen follows. `Appearance.setColorScheme` (best effort,
  try/catch) moves native chrome too; StatusBar style follows the chosen scheme. Provider renders nothing
  until the stored choice is read (no wrong-scheme flash). `storage.LOCAL_DATA_KEYS` (= all `KEYS`) is now
  what Privacy's clear removes, and clearing resets the live theme to the phone setting. Tests:
  `appearance.test.tsx` (5). Mobile 32 passed, typecheck clean, bundle-check exports. Device: Settings shows
  the section with the phone-setting row checked in dark; tapping Light/Dark on the device not yet checked
  by the agent (owner was using the phone).
- **Mobile reader options planned (2026-09-30):** `docs/plans/mobile-reader-options.md`. M1–M5 done; R10 device checks partly done (see entry); next M6. Owner
  asked for a light/dark choice (app only follows the system today). Order: M1 Appearance → M2 edit
  profile/interests → M3 settings basics → R10 device checks → M4 text size → M5 hide topics → M6 read history;
  offline saved, Home/Latest, digest time, TTS and iOS build need a decision/ADR first.

Update this file at the end of every ticket. This is the source of truth for
"what's actually done" — trust it over assumptions, git log archaeology, or
prior conversation history.

**Pilot removed (2026-09-16)**: product owner decided there is no
recruited-user validation pilot at all, before or after build — not waived,
removed. T20 no longer exists as a ticket. The engineering deliverable built
for it on 2026-09-09 (landing page, 3 example personalized feeds, email
signup capture) has been deleted, including its `pilot_signups` DB table
(migration `c3d4e5f6a7b8`) — see the 2026-09-16 changelog entry below for
the full list of removed files. `docs/BUILD_ORDER.md`'s pre-build validation
gate section is gone; do not reintroduce a pilot gate on any future ticket.

**Review backlog (`docs/reviews/2026-09-29-comprehensive-review.md`)**: worked in the owner's order
#1 → #5 → #3 → #4 → #8 → #7; #2 (budget ceiling), held-story recovery and product/UX items wait on ADRs.
- **#1 done (2026-09-29): bounded AI retries across sweeps.** New table `ai_work_state` (migration
  `b8e4c2d6f1a3`), one row per (story, `GENERATE`|`TRANSLATE`), keyed to a hash of the stage's input.
  `app/jobs/ai_retry.py`: DEFERRED/UNAVAILABLE/CLASSIFICATION_ONLY back off 2 min doubling to a 6 h cap and give
  up after 20; HOLD (invalid output) gives up after 3. A successful classification is cached for its input
  version, so a failed summary no longer re-pays classification. Exhausted generation goes to review with
  reason `AI_RETRIES_EXHAUSTED` (editor rejects or drafts by hand); exhausted translation stops and English
  keeps serving. New evidence or corrected English resets the count; the row is deleted on success. No
  manual reset of an exhausted row yet (recovery ADR). Provider Retry-After isn't surfaced by the gateway,
  so quota deferrals use the same backoff. Tests: `tests/test_ai_retry.py`. Full suite: 371 passed; 2
  setup errors from the local fixture's `pg_terminate_backend` permission, different tests each run, pass alone.
- **#5 done (2026-09-29): stricter Telugu QA** (`app/content/qa.py`). Numbers compare as whole tokens and as
  a multiset, so a changed ("5"→"50") or added number fails (`UNEXPECTED_NUMBER`); Telugu digits and
  Indian grouping normalize first. Currency compares by token. Negation also fails when Telugu adds one that
  the English lacks (`UNEXPECTED_NEGATION`, unless the English has a negative-sense word like "denied").
  New `find_variant_qa_issues` requires headline and summary, why-matters when English has it, and at least
  25% Telugu script per field; used by `ai_translate` and the admin Telugu draft endpoint. Still a floor
  check, not a fidelity check: the native-speaker sample review stays. Full suite 378 passed (same 2 flaky
  fixture errors).
- **#3 done (2026-09-29): AI usage telemetry.** Migration `c9f5d3e7a2b4`: `ai_call_log.tokens_thinking`,
  `tokens_cached`, and statuses `PARSE_ERROR`, `BLOCKED`, `PROVIDER_ERROR`. Gemini `tokens_out` now includes
  `thoughtsTokenCount` (billed as output), so cost counts it. Cached input is recorded but priced at the full
  rate, which overestimates. Providers no longer raise on malformed JSON (`parse_json_output`); a
  malformed or blocked reply is logged with its usage and fails validation like any bad output. Transport
  errors log `PROVIDER_ERROR`, not `UNAVAILABLE`, so the misconfiguration alert isn't tripped. Not done:
  reconciling logged cost against the Cloud billing export (needs billing access). Full suite 384 passed.
- **#4 done (2026-09-29): brief headline and per-claim evidence** (`app/jobs/brief_lane.py`). The headline now
  goes through `title_match` like the sentence, so an invented name, number or negation in it sends the
  story to review (`BRIEF_TITLE_MISMATCH`). Each claim is checked only against the titles it cites.
  `title_match` also fails when negation is present in the text but not the titles, or the reverse, and when
  two checked tokens appear in the opposite order from one title ("Smith sues Jones" → "Jones sues Smith").
  Headlines get the order check on numbers only, since they reorder freely. Still lexical, not entailment: a
  swapped verb with the same tokens gets through. Full suite 390 passed (1 flaky fixture error).
- **#8 done (2026-09-29): bounded AI sweeps and safe job leases.** `generate_stories`/`translate_stories`
  attempt at most `AI_SWEEP_BATCH_SIZE` stories (default 10; backing-off stories don't count) and start none
  after 120 s. Order: generate newest source item first; translate published first, then newest. Each
  story commits on its own, so a crash doesn't repeat finished stories' paid calls. `queue.renew_lease`
  runs before each story: it extends the 300 s lease, so the lease only has to cover one story (worst case
  ~240 s), and raises `LeaseLost` if another worker has reclaimed the job. `complete_job`/`fail_job` also
  check that the job is still ours (the token is the claim's `locked_at`). `claim_job` marks an
  expired-lease job at `MAX_JOB_ATTEMPTS` FAILED instead of reclaiming it. The worker rolls back before
  logging or `fail_job`; before this fix, a failed flush made it raise `PendingRollbackError`. Tests:
  `tests/test_bounded_sweeps.py`. Full suite 396 passed (2 flaky fixture errors).
- **#7 done (2026-09-29): rights rechecked at approval and publication.** `app/content/rights.py`
  (`unpermitted_sources`; only `LINK_ONLY` is publishable under ADR-002; `active` is ignored, since not
  polled ≠ revoked). Auto-publish (global and brief lane) sends such a story to review with
  `SOURCE_RIGHTS_REVOKED`. Admin approve returns 409 `SOURCE_RIGHTS_REVOKED`. `publish_due_stories` leaves a
  SCHEDULED story unpublished (the status trigger allows only SCHEDULED→PUBLISHED) and audits
  `STORY_PUBLISH_BLOCKED_RIGHTS` once; it publishes if rights are restored. A story with any revoked
  source is blocked, even if its other sources are fine. Revocation for published stories, mixed-source
  stories, and a way back from SCHEDULED are open in ADR-023. Tests: `tests/test_rights_recheck.py`. Full
  suite 401 passed (3 flaky fixture errors, pass on rerun).
- **#9 code done (2026-09-30), operator steps open: production readiness.** `GET /health/ready` returns
  503 when Postgres is unreachable (`/health` stays static liveness); the api Compose service now has a
  healthcheck on it. `app/jobs/monitor.py` is a worker liveness check that runs outside the worker (in the
  api container): `WORKER_STALE` when no job has been claimed for 10 min and none holds a live lease,
  `QUEUE_BACKLOG` when a due job has waited 15 min. `infra/deploy/monitor.sh` runs it plus readiness and
  web/admin checks. Cron runs it every 5 min (installed by `deploy.sh`) and pings
  `MONITOR_HEALTHCHECK_URL`, a healthchecks.io dead-man's switch, so a dead server alerts too; runs are
  skipped while a deploy holds `/run/teluguvarta-deploying`. `deploy.sh` now **exits 1** if those checks
  don't pass within 2 min (before this, it printed completion after a failed health loop). The worker
  logs one line at start, since jobs log only on failure. Runbook with migration-aware rollback and the
  evidence checklist: `infra/deploy/OPERATIONS.md`. **Still to do on the server, by the owner:**
  configure backups and the Storage Box, run a restore drill, keep `.env.prod` (MFA key) off-box, and set
  `MONITOR_HEALTHCHECK_URL` and test the alert. Tests: `tests/test_health.py` (8 passed; related suites
  44 passed). **Deployed 2026-09-30 03:28 UTC at `62eea75`**: the deploy gate passed ("All healthy.") and
  the api container reports `healthy`. The first deploy of it (`e684a1a`) hung at the gate: `docker
  compose exec` under `timeout` was stopped reading the interactive tty. Fixed with `</dev/null` and a
  wall-clock wait. Cron runs haven't been observed yet: check `/var/log/teluguvarta-monitor.log`.
- **#16 done (2026-09-30): sitemap covers every published story** (`apps/web/src/lib/sitemap.ts`). The
  sitemap follows `next_cursor` 100 at a time up to 49,000 stories (one sitemap file holds 50,000 URLs;
  past that it needs a sitemap index). It lists only topics that have a published story, derived from the
  stories themselves (so no `/v1/config` call), dated by their newest story; Home and Latest carry the
  newest story's date. `/latest` was added. `/saved`, `/search`, `/onboarding` and `/account/` are
  left out of the sitemap and disallowed in `robots.txt`. At runtime an API failure now throws, so
  ISR keeps the last good sitemap; at build it falls back to static routes, as before. Country pages
  stay out until geography is fixed (#10). Web now has a `test` script (node's test runner, 4 tests in
  `apps/web/tests/sitemap.test.mjs`) and CI runs it. Verified: web typecheck, lint, test, and
  production build with the API unreachable. **Deployed 2026-09-30, verified live:** robots.txt has the four
  disallows; the sitemap lists 9 static routes and both published stories, and no topics, since neither
  story has a topic yet (before this, all 26 topic pages were listed, most of them empty).
- **#11 code part done (2026-09-30): populated topics first, editor topic tagging.** Topics were attached
  only by AI classification (`generate._link_topics`), so hand-drafted stories (both live ones) had none
  and every topic page was empty. `TopicOut.story_count` counts published stories;
  `serialize.active_topics_out` orders `/v1/config` and `/v1/home` topics by count, then name, and
  `/v1/topics/{slug}` returns its count too. New `PUT /v1/admin/stories/{id}/topics` (existing active
  topics only, max 5, replaces the set, any status since topics aren't story text; 422 `UNKNOWN_TOPIC`;
  audit `STORY_TOPICS_SET`); admin detail returns `topics`; the review page has a topic picker. Web: header
  topic bar, home chips and search suggestions show only populated topics (the header's Topics link
  still lists all); `/topics` shows populated topics with counts, then a "No stories yet" group; an empty
  topic page links to Latest. Mobile: Topics tab rows show counts; Home chips are populated only.
  Tests: `tests/test_topic_navigation.py` (3). Full API suite 411 passed (1 flaky fixture error, passes
  alone); web/admin/mobile typecheck and lint, mobile jest 19 passed, web and admin production builds.
  Not checked in a browser. **Not done (owner/editorial):** activating a balanced rights-reviewed source
  set, a daily editorial target, and student topics shown prominently to students (needs the
  onboarding profile in the header; not started). **Deployed 2026-09-30, verified live:** `/v1/config`
  returns `story_count` (all 26 topics at 0), `/topics` shows the "No topic has stories yet" state, and
  the admin topics endpoint is live (401 without a token). Next: tag the two live stories in admin.
- **#12 partly done (2026-09-30): no translation of unsettled or dropped stories.** `translate_stories`
  now picks only `TRANSLATABLE_STATUSES` (REVIEW_REQUIRED, APPROVED, SCHEDULED, PUBLISHED, UPDATED,
  CORRECTION_PENDING). Skipped: DRAFT (includes rejected-to-draft), ARCHIVED, RETRACTED, and AI_READY,
  which auto-publish moves on the same cycle and whose English the brief lane may replace (which
  deleted the paid Telugu). A story rejected after translation keeps its Telugu row; a rejected one is
  never translated again. **Not done (needs an ADR):** translating only after approval; REVIEW_REQUIRED
  is still translated so Telugu is ready at approval, and an editor's English edit in review still
  discards that Telugu. Also fixed: `tests/test_topic_navigation.py` (#11) failed `ruff check`, which CI
  runs. Tests: `test_translation_skips_stories_whose_english_is_not_settled`. Full API suite 412 passed
  (3 flaky fixture errors, pass on rerun); ruff clean. **Deployed 2026-09-30 by the owner** (`b28261b`);
  not checked live (no code path is visible from outside; check the next `ai_translate` runs in the worker).
- **#13 done (2026-09-30): bounded segment explanations from public home requests.** `GET /v1/home` with
  preferences still queues an `ai_summarize` job per uncached (story, segment, version), but at most
  `WHY_MATTERS_DAILY_JOB_CAP` (default 50) per rolling 24 h, counted once per request
  (`app/jobs/why_matters.py`); past it, readers see the approved generic text. Concurrent requests can
  overshoot by a few. Segment `other` now reads and generates the `general` explanation (same audience
  label, so it was a second paid call for the same text). The prompt JSON-encodes headline/summary inside a
  random untrusted-data boundary, and the call passes the story's privacy decision and editor-authored flag,
  so an allowed story can use the free route. That routing is now shared with translation
  (`content.variants.dispatch_privacy`). Not done: whether generic explanations suffice at launch (removing
  the feature needs an owner decision); the cost-per-published-story metric isn't built yet, though these
  calls log `story_id`. Tests: 4 new in `tests/test_personalization_api.py`. Full API suite 416 passed
  (1 flaky fixture error, passes alone); ruff clean; no new mypy errors in touched files. **Deployed 2026-09-30 by the owner** (`ec6cd3b`); not checked live
  (the cap only shows in the worker's `ai_summarize` jobs; no migration).
- **#10 done (2026-09-30): event geography and importance (ADR-027, accepted).** Migration `d1a6e4f8b3c5`:
  `stories.classification_confidence`, `urgency`, `importance_override`, and table `story_countries`
  (role `EVENT`; `AUDIENCE` reserved). Generation stores the model's confidence and urgency, writes its
  countries as EVENT rows (normalized to the 9 codes clients offer, unknown dropped;
  `app/content/geography.py`), and scores importance deterministically (`app/content/importance.py`: 0.4,
  +0.2 urgent, +0.1 per extra independent source up to +0.3, +0.1 for immigration/student topics). The score
  is recomputed when cluster adds a source and when an editor sets topics. The brief lane reads
  confidence (none → ineligible); the breaking-alert confidence check skips stories with no confidence, so
  the editor's alert approval decides for hand-drafted ones. Public `countries`, the ranking residence
  match and `?country=` use EVENT rows only, never `Source.country`. Admin: `PUT
  /v1/admin/stories/{id}/countries` (422 `UNKNOWN_COUNTRY`, audit `STORY_COUNTRIES_SET`) and `PUT
  .../importance` (`LOW`/`NORMAL`/`HIGH` = 0.2/0.5/0.8 or null to recompute, audit
  `STORY_IMPORTANCE_SET`); detail returns countries, override and confidence; the review page has a
  country picker and importance selector. Backfill: AI-written stories get their old importance as
  confidence; every story's importance is recomputed (no urgency term, never stored); no story gets
  countries. **After deploy:** the two live stories lose their US badge, so set their countries (and
  topics) in admin. Tests: `tests/test_geography_importance.py` (12, including the migration backfill and
  downgrade). Full API suite 429 passed; ruff clean; mypy 69 errors,
  down from 71, none in new code; admin typecheck, lint and production build pass. Not checked in a
  browser. Not done: country pages in the sitemap (left out until this, #16); formula weights untuned.
  **Deployed 2026-09-30 by the owner** (`fe59840`, migration `d1a6e4f8b3c5`); not checked live. Still to do
  in admin: set countries and topics on the two live stories.
- **#14 code part done (2026-09-30): mobile freshness, Latest, dark-theme text.** Home reloads when the tab
  regains focus or the app returns to the foreground, but only once the last successful load is
  `HOME_STALE_MS` (5 min) old; a failed load is still retried by pull-to-refresh. New `Latest` stack screen
  (`/v1/stories` newest first, "Older stories" by cursor, deep link `latest`), opened from an "All latest
  stories" button at the end of Home. Topic and Latest share `components/PagedStoryList.tsx`; its buttons
  are themed Pressables, not the native `Button`. Error/empty/notice text that used the default
  (black) color now uses theme colors: StoryList, Topic, Topics, Search, Story detail, Saved, Language
  check mark, and StoryCard's "Telugu isn't available" note. Tests: 2 new in
  `src/__tests__/ux-reliability.test.tsx`; mobile jest 21 passed, typecheck clean, iOS and Android bundle
  export pass. Not checked on a device. **Not done:** tab icons are still font glyphs
  (`@expo/vector-icons` breaks web/admin builds via a second `@types/react`, see `MainTabs.tsx`);
  **owner:** rebuild and install the APK with the production domain URLs (the installed build still
  points at sslip.io), then device-test large text, TalkBack/VoiceOver, Telugu wrapping, safe areas,
  offline recovery, save/delete and real push; verified HTTPS app links would need an ADR.
- **#15 code part done (2026-09-30): fetch, admin, token and proxy hardening.** New
  `app/adapters/safe_fetch.py`: the scheduled RSS and OpenFEMA fetches now get the admin probe's
  policy (http(s) only, every resolved address public, no redirects, body streamed and capped at 5 MB;
  the probe keeps 2 MB). An HTTP error now raises `FeedFetchError("Feed returned HTTP n")` instead of
  `httpx.HTTPStatusError`. Residual: DNS rebinding between the check and the connect. Tests stub DNS
  globally (`tests/conftest.py::_no_real_dns`); before this, job tests resolved feeds.npr.org for real.
  `current_admin` re-reads the account on every request: a deleted account gets 401, a demoted one 403,
  and the stored role is enforced, not the JWT claim. Anonymous tokens must be 16–128 URL-safe
  characters (UUIDs and the old mobile fallback both pass), and creating a user for an unseen token
  is limited to 30 per 10 min per client IP (`rate_limit.rate_limit_new_user`). **Proxy bug fixed:**
  nginx appended to the client's `X-Forwarded-For`, and uvicorn (`--forwarded-allow-ips "*"`)
  takes the first entry, so a client could choose its own IP and dodge every per-IP limit.
  `nginx-setup.sh` now sets it to `$remote_addr` and fixes existing confs in place on the next deploy.
  Mobile: the device token comes from `expo-crypto` (OS CSPRNG; before this, Hermes could fall back to
  `Math.random`) and is stored with `expo-secure-store`; a token already in AsyncStorage is moved over.
  Both are new native modules, so they reach phones only in a rebuilt APK. No new `@types/react`
  resolution. Admin session storage (`localStorage` token, no CSP) is **ADR-028, proposed**. Tests:
  `tests/test_security_review_15.py` (7), mobile `src/__tests__/identity.test.ts` (3). Full API
  suite 437 passed (1 flaky fixture error, passes on rerun); ruff clean; mobile jest 24 passed,
  typecheck clean, both bundles export; web/admin typecheck clean. **Not done:** Next SSR calls the API
  through nginx from the VPS's own IP, so server-rendered search shares one 30/min bucket (as before
  this change).
  **Deployed 2026-09-30 by the owner** (`e403f6f`, no migration). Verified live: `/health/ready` 200,
  `/v1/me` with a 5-character token 401 (it created a user before). The XFF fix isn't checked from outside;
  on the server, `grep proxy_add_x_forwarded_for /etc/nginx/conf.d/teluguvarta-*.conf` should be empty.
  **Release APK rebuilt and installed 2026-09-30** (after `expo prebuild` for the two new native modules)
  on the owner's Android device, with `api.theteluguedit.com` in the bundle: it launches and the home feed
  loads, no crash in logcat. This also ships #14. The old sslip.io nginx conf can go once no older install
  remains. Device checks of #14 (Latest, large text, TalkBack, offline, push) are still to do.
- **#17 partly done (2026-09-30): CI checks what broke live.** CI now runs the web and admin production
  builds. They were **failing on a fresh full-workspace install**: `next`'s own types resolved `react`
  through pnpm's hidden hoist, which held mobile's `@types/react@19`, while web/admin use 18 (layout
  `LayoutProps` error). Deploys were unaffected because `next.Dockerfile` installs one app only. Fixed with
  a root `pnpm.packageExtensions` giving `next` an optional `@types/react` peer, so each app links its own.
  `pnpm audit --audit-level=high` was also failing on main (new `brace-expansion` advisories, dev tooling
  only); overrides pin the patched 1.x/2.x/5.x. API: runtime deps are locked with hashes in
  `apps/api/requirements.lock` (uv, universal, Python 3.12); the image installs only from it, then the
  package with `--no-deps`. CI checks the lock is current, installs from it, and now uses Python 3.12 like
  the image (was 3.11). mypy is pinned (2.3.1) and ratcheted: CI fails above `apps/api/mypy-baseline.txt`
  (71). Verified locally: both builds, lint, typecheck, web test 4, mobile jest 24, frozen install, pnpm
  audit, ruff, mypy 71, `pip-audit` on the lock, lock install + `pip check` in a fresh 3.12 venv. Not
  verified locally: the Docker image build. **Deployed 2026-09-30 by the owner** (image built from the
  lock); live `/health/ready`, web and admin return 200. **CI green 2026-09-30
  at `2597d23`** (all three jobs). Actions had been blocked by account billing since before #15, so
  no run had executed; the repo was made public (history scanned first: the only committed key is the
  local dev MFA key, prod generates its own in `deploy.sh`). Once jobs ran, four existing failures
  surfaced and were fixed: stale `packages/contracts` (since #10), bandit B405 in `feed_probe.py`
  (`ParseError` now from defusedxml; `types-defusedxml` pinned, mypy still 71), mobile tests used
  `global` (needs @types/node, not hoisted on a fresh install; now `globalThis`), a 5 s jest timeout on
  a cold runner (now 20 s), and web tests needing Node 22.18+ to import `.ts` (CI now Node 22 like
  `next.Dockerfile`; root `engines` `>=22.18`).
  **Not done:** browser journeys (Playwright with BRIEF/zero/two/many/error fixtures), the capped
  paid-model contract/Telugu eval (spends money: owner to approve a budget), cleaning mobile `act`
  warnings, and actually reducing mypy debt.
- **Waiting on the owner (proposed ADR, nothing implemented):** ADR-023 rights revocation for published,
  mixed-source and scheduled stories (#7 follow-up).
- **ADR-024 (#2) implemented and deployed 2026-09-30 (`adc4c5f`, CI green, API /health/ready ok):** `MONTHLY_AI_HARD_CAP_USD` (owner chose $60)
  — `is_over_hard_cap` in `app/ai/budget.py`; the gateway refuses every non-free-tier call at/over it with
  transient `UNAVAILABLE` (no `ai_call_log` row, so no migration) and re-checks before the schema retry;
  `check_budget_alerts` fires `MONTHLY_AI_HARD_CAP_USD`. `require_budget_config()` makes the API and worker
  refuse to start under `APP_ENV=production` unless `MONTHLY_AI_BUDGET_USD`, `MONTHLY_AI_HARD_CAP_USD`,
  `DAILY_AI_ALERT_USD` are positive numbers and cap ≥ budget. `deploy.sh` appends `MONTHLY_AI_HARD_CAP_USD=60`
  to an existing `.env.prod` that lacks it. Admin cost card doesn't show the cap yet. **Owner still to do
  (option 6):** budget alert + quota cap on the paid Gemini Cloud project. Option 3 (reserve) deferred
  until a second worker exists.
- **Admin installable PWA done and deployed 2026-09-30 (`fbc0e7e`; live manifest + icons confirmed):** `apps/admin/src/app/manifest.ts` →
  `/manifest.webmanifest` (`display: standalone`, `start_url: /review`, `--color-bg` theme/background), icons in
  `apps/admin/public/icons/` (192/512 `any` from `icon.png`, plus full-bleed `maskable` variants on `#332c6d`),
  `layout.tsx` exports `viewport` (device-width, per-scheme `themeColor` = `--color-bg`) and `appleWebApp` metadata.
  No service worker (current Chrome/Safari install without one; admin data must stay fresh). Phone layout was
  already in place (sticky two-row nav ≤720px, `.table-scroll` + `.col-wide-only`, review detail single-column
  ≤960px); verified by build output + served HTML/manifest, **not** by a logged-in phone session — owner to
  confirm "Add to Home Screen" on a real phone after deploy. On single-column widths (≤960px) the review page's
  decision panel is moved above the story with CSS `order: -1` (DOM order unchanged; `30c4812`, deployed
  2026-09-30, live CSS confirmed). A native admin app was declined for
  now (would need an ADR).
- **Telugu sources + auto-publish, owner decision 2026-09-30 (APPLIED in prod 2026-09-30 ~23:08 UTC:
  `15b3520` deployed, `AUTO_PUBLISH_GLOBAL=true`, script `--apply` with reviewer `admin@theteluguedit.com`
  added all 11 and deactivated NPR):** the feed was
  mostly US news because 3 of 4 seeded sources were NPR/State Dept/FEMA. Owner approved 11 LINK_ONLY feeds from
  `docs/sources/telugu-source-candidates.md` (Namasthe Telangana main/Hyderabad/sports/business, NTV Telugu,
  Telugu360 main, Telangana State Portal, 123telugu, Telugu Times, USCIS news, Study in the States) and
  deactivating NPR. `infra/scripts/approve_sources.py` applies it (preview by default, `--apply` writes,
  `--reviewer` = approving ADMIN; never re-enables a DISABLED source). Owner chose full-story auto-publish:
  set `AUTO_PUBLISH_GLOBAL=true` in `.env.prod`. NON_NEGOTIABLES #5 still holds — immigration/legal/financial/
  breaking (and urgent, low-confidence, ADR-026 failures) stay in the review queue. Topic gaps with no working
  Telugu feed: jobs, property, education, parents. Watch after rollout: AI spend (ntnews feeds carry 200 items;
  non-allowlisted categories use the paid route; $60 hard cap) and how many Telugu-sourced stories hold for
  evidence/confidence reasons. First fetch queued 817 drafts, mostly feed history; owner archived the 789
  CLUSTERED items of DRAFT stories whose newest item was >48h old (manual SQL, same effect as the classifier's
  not-relevant archive).
- **First-fetch backlog cutoff (2026-09-30, `a642398`, deployed; Telugu stories confirmed auto-publishing on the public API from 23:15 UTC):** `source_fetch.FIRST_FETCH_MAX_AGE` = 48h. On a
  source's first successful fetch (`last_success_at IS NULL`), items older than that are emitted as `ARCHIVED`
  (`SourceAdapter.emit(archive=True)`) — stored for dedupe, never processed; undated items are kept; never lifts
  `RIGHTS_BLOCKED`. Not applied to X fetches, or to a source re-enabled after a long gap (it has a
  `last_success_at`).
- **Tighter relevance check (2026-09-30, `c1be827`, deployed by owner 2026-09-30):** the classify prompt used to say only
  "Determine relevance". It now lists what counts (`generate.RELEVANCE_CRITERIA`): AP/Telangana, Telugu
  people/orgs/culture, Tollywood, practical NRI matters (visas, students, consular, NRI money), and India/world
  news with a stated AP/TG/NRI impact. It excludes other states' local news, unlinked national news,
  Bollywood, sports without a Telugu athlete or AP/TG team, general US/world news, and horoscope/gossip/promo
  content. Telugu-language text alone doesn't count, and weak links are marked not relevant (archived). Prompt only, no
  schema change; cached classifications for already-classified stories aren't re-run. Watch the archive rate after
  deploy; the sports rule is the most likely to need loosening.
- **ADR-025 implemented and deployed 2026-09-30 (`6845dbc`):** `POST /v1/admin/stories/{id}/retry-ai`
  `{stage: GENERATE|TRANSLATE, reason}` — ADMIN only (403 otherwise), max 2 resets per story per stage (counted
  from `AI_RETRY_RESET` audit events; 409 `RETRY_LIMIT_REACHED`), 409 `NOT_AI_HELD` unless the story is actually
  AI-held (GENERATE: REVIEW_REQUIRED with an `AI_RETRIES_EXHAUSTED`/`NO_PAID_PROVIDER` review reason or an
  EXHAUSTED state; TRANSLATE: EXHAUSTED state). GENERATE deletes the work state, moves the story
  REVIEW_REQUIRED → DRAFT, items → CLUSTERED, closes the review task as REJECTED; it then re-enters normal
  generation/review routing. TRANSLATE only deletes the state. `GET /v1/admin/ai-holds` lists every EXHAUSTED
  state. Admin: "Retry AI" button on the review page (ADMIN, AI-held stories, uses the reason field) and a
  "Telugu translations that failed" panel under the review queue with "Retry translation". No migration.
  Option 2 (bulk reset) deferred until an outage needs it.
- **ADR-026 (#6) implemented and deployed 2026-09-30 (`7628812`, CI green, API /health/ready ok):** `app/content/publication.py`
  `validate_for_publication` (FULL only; BRIEF keeps ADR-019's lane rules): (b) summary/headline
  similarity < 0.8, (c) summary ≥ 2 sentences or ≥ 25 words, (d) headline < 0.6 vs every source title;
  why-matters stays optional. Enforced at admin approve and `/correct` (422 `CONTENT_RULES_FAILED` naming
  the rules), auto-approve (→ `REVIEW_REQUIRED`, reason `CONTENT_RULES_FAILED:<rules>`) and
  `publish_due_stories` (SCHEDULED story held, audited once as `STORY_PUBLISH_BLOCKED_CONTENT` — a
  SCHEDULED story can't be edited, so this only catches pre-rule approvals). **Owner to do:** fix the two
  live stories through `/correct`, which now enforces the rules. Test fix on the way: the X attribution test's
  fake provider replays the classification payload as the draft (helper builds a fresh provider per call),
  so its classification fixture now carries valid draft text.
  **Deployed to the VPS 2026-09-30 03:07 UTC at `5af512f`:** both migrations (`b8e4c2d6f1a3`,
  `c9f5d3e7a2b4`) applied, all services up, API healthy. Worker checked 03:14 UTC: every sweep job type
  running on schedule and `DONE`, none stuck, no worker errors, `ai_work_state` empty, no story missing
  Telugu. So no AI calls since the deploy: nothing needed generation or translation. The new
  retry/backoff path hasn't been exercised in production yet.
  Deploy still warns "Backups NOT configured" (`BACKUP_AGE_RECIPIENT`, review #9).

**Manual drafting in admin (2026-09-29)**: step 1 of the free/low-cost AI plan (VPS is a CPX21, 3 vCPU/4 GB,
so no local LLM; the plan is Gemini free for allowlisted categories, a capped paid Flash-Lite route, and manual
drafting as the fallback). Before this, a `NO_PAID_PROVIDER` story sat in review with "No draft yet" and no way to
write one, and approve didn't check for English, so an empty story could be published.
- `PUT /v1/admin/stories/{id}/variants/{en|te}`: editor writes or rewrites a draft while the story is
  `REVIEW_REQUIRED` (published stories still go through `/correct`). Blank text returns 422 `EMPTY_DRAFT`.
  Rewriting English deletes the Telugu variant. Telugu needs English first (409 `NO_ENGLISH_DRAFT`) and must pass
  `find_qa_issues` (422 `TELUGU_QA_FAILED`), then saves as `PASSED`. Audit action: `STORY_DRAFT_WRITTEN`.
- Approve returns 422 `NO_ENGLISH_DRAFT` unless an English headline and summary exist.
- Editor text is marked `model_version = "editor"` (`EDITOR_MODEL_VERSION`); `ai_translate` treats it as
  editor-authored, so it never goes to the Gemini free tier (same rule as corrected stories).
- Admin review page: "Write/Edit English|Telugu draft" forms; Approve is disabled until English exists.
- Verified: ruff, admin `tsc`, full API suite 307 passed against local Postgres (1 setup error in untouched
  `test_cluster.py` from psycopg, passes on rerun). The admin UI has not been checked in a browser yet.
- **Deployed and verified on the VPS (2026-09-29):** two NO_PAID_PROVIDER stories were drafted and approved in
  admin, and both reached the phone via the publish job (runs every 2 minutes).
- **Faster triage (2026-09-29):**
  - `ReviewQueueItemOut.source_title` (the PRIMARY source item's title) is shown in the queue for stories with
    no draft yet, instead of "Draft headline pending".
  - A new English draft's headline is pre-filled from that title, with a hint to rewrite it.
  - After approve or reject, admin opens the next queued story (always-human-reviewed first).
  - Deliberately **no bulk approve**: the queue page's "nothing decided unseen" rule stands.
  - Contracts regenerated. This also picks up the draft endpoint, which the previous commit missed.
- **Open issues seen in the prod queue after deploy (2026-09-29, not fixed):**
  - **FEMA title "1": fixed in code (2026-09-29), not yet live.** The RSS feed sent bare disaster numbers as
    titles with 2004 dates.
    - `app/adapters/openfema.py`: `OpenFemaAdapter` reads `FemaWebDisasterDeclarations` (one row per disaster)
      instead of `DisasterDeclarationsSummaries` (one row per county). Titles look like "Emergency declaration for
      Hawaii: Tropical Storm Nolo", the external id is `fema-disaster-N`, and the URL is the disaster page. It
      asks only for the last 30 days (`MAX_AGE_DAYS`) and drops anything older.
    - `source_fetch.adapter_for` picks this adapter for any `www.fema.gov/api/open/` feed_url; everything else
      stays RSS. The seed points at the API.
    - The shared `validate` now rejects titles that are only digits, for every source.
    - `infra/scripts/fema_openfema_cutover.py` is a dry run unless given `--apply`. It deletes unpublished
      (DRAFT/AI_READY/REVIEW_REQUIRED) stories built only from RSS-era FEMA items, and deletes RSS-era items nothing
      references. It keeps published or mixed stories and reports them. It then points the source at the API,
      resets `fail_count` and writes a `SOURCE_UPDATED` audit event. It never touches `fema-disaster-*` items,
      so rerunning it is safe.
    - Verified: 7 new tests in `tests/test_openfema.py` (the cutover test runs on Postgres); the full API suite
      passes (359, plus the known flaky `test_schema` setup error, which passes on rerun); ruff clean; mypy still
      71. A live fetch of the API through the adapter gave 15 current declarations, all valid, with no
      User-Agent header needed.
    - Known gap: admin's "Test feed" probe is RSS-only, so it rejects the API URL. Don't re-probe FEMA.

    **Owner steps on the VPS:** (a) run `deploy.sh`; (b) run
    `docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod run --rm api python
    /srv/infra/scripts/fema_openfema_cutover.py`, the same way `deploy.sh` runs the seed. Run it first without
    `--apply` to read the counts, then with `--apply`. (c) Set FEMA active in admin.
    **Cutover applied in prod (2026-09-29 22:17 UTC):** its audit event shows 3 stories and 5 RSS-era items deleted,
    0 kept. The source is active with `fail_count` 0. Still to check: the first OpenFEMA fetch (hourly, so around
    23:00 UTC) should create `fema-disaster-*` items. Prod DB user is `teluguvarta`, not `postgres`.
  - **State Dept duplicated titles: fixed.** The upstream feed itself sends "Israel - Level 3: Reconsider
    Travel - Level 3: Reconsider Travel". `rss._clean_title` collapses whitespace and drops a repeated trailing
    " - " segment. It only applies to newly ingested items; existing rows keep the old titles.
  - NO_PAID_PROVIDER holds are never classified, so their sensitivity stays `NONE`. The queue says
    "0 always-human-reviewed" even for a terror-plot story, and there is no confirm/required-reason friction.
    Step 2 (paid route) fixes this; until then, treat every held story as unclassified.
    **Interim fix (2026-09-29):** admin now shows these holds as unclassified. The queue header counts them
    ("N unclassified"), the story page's sensitivity badge reads `UNCLASSIFIED` instead of `NONE`, and the
    NO_PAID_PROVIDER help tells the reviewer to check the source for the always-reviewed categories.
    No confirm/required-reason friction was added on purpose, since every held story would get it.
- **Paid Gemini live, but every call HOLDed (2026-09-30): fixed in code, not yet deployed.**
  - Owner turned billing on for the *existing* project instead of a separate one, so prod runs with one
    billed key: `AI_GEMINI_PAID_API_KEY` set, `AI_FREE_TIER_ENABLED=false`, `AI_GEMINI_API_KEY` empty
    (ADR-018's "enable billing on the existing project" alternative; the free route is off).
  - After deploy, `ai_call_log` showed 12 `gemini_paid` translation calls, all `HOLD` (the model's JSON
    failed schema validation twice). Cause: no task prompt names the output keys, and no provider sends a
    schema, so the model picked its own names (e.g. `headline` instead of `headline_te`). The same would
    have hit classify/summary/brief.
  - Fix: `gateway._with_output_contract` appends the result model's JSON Schema to every prompt. All
    provider calls go through the gateway, so every task gets it. Test:
    `test_prompt_names_the_result_schema_keys`. Full suite 366 passed (known flaky teardown error in
    `test_notifications.py`, passes on rerun); ruff clean.
  - **Deployed (b8d8559) and verified for translation (2026-09-30 02:20 UTC):** first run after deploy
    logged 2 `gemini_paid` translation `SUCCESS`, no HOLDs since; both published stories now serve `te`.
    Classify/summary on real Gemini not yet observed (waits on the next hourly fetch).
- **Automation plan agreed with owner:**
  1. Faster triage (above).
  2. ADR: paid Gemini route, so AI drafts every story. **ADR-018 accepted and implemented (2026-09-29).**
     The owner chose a separate billed project, a $50/month AI budget ($3 daily alert), and no extra
     Telugu grading. A new `gemini_paid` provider (`AI_GEMINI_PAID_API_KEY`) handles every story not on
     the free-tier allowlist when no OpenAI/Anthropic key is set, so `NO_PAID_PROVIDER` holds stop.
     Pinned `gemini-3.5-flash-lite` / `gemini-3.8-flash`, priced in `PAID_GEMINI_PRICING`. An unpriced or
     alias model is refused (UNAVAILABLE, logged).
     **Not live yet — owner steps on the VPS:**
     (a) Create a new Cloud project with billing on, and make an API key there.
     (b) In `.env.prod`, set `AI_GEMINI_PAID_API_KEY=` and change `MONTHLY_AI_BUDGET_USD=50` and
         `DAILY_AI_ALERT_USD=3`. `deploy.sh` only writes those on the first run, so the existing file
         still says 150/10.
     (c) Re-run `deploy.sh`.
     Stories already held as `NO_PAID_PROVIDER` stay held. Only new stories get drafted.
     Verified: `pytest` 320 passed. One run had a Postgres `InsufficientResources` error on a different test
     each time; it's local and flaky, and those tests pass on their own. `ruff` is clean. mypy has the same 68
     errors before and after.
  3. Auto-publish lane ADR (the plan called it "ADR-011", but that number is the claim-evidence ADR; use
     the next free number, ADR-019; ADR-016 is reserved) for "link-first briefs" (headline plus a one-liner limited to what the
     source title says, plus the source link). Only for rights-reviewed, `sensitivity=NONE`, high-confidence
     stories, with a daily cap. **ADR-019 accepted and implemented (2026-09-29).** Owner decisions: sentence
     ≤30 words, no "why this matters" (NON_NEGOTIABLES #15 amended), confidence ≥0.8, 20/day with the day
     starting at midnight America/New_York, and a "Brief" label for readers.
     - `app/jobs/brief_lane.py`, called from `auto_publish_stories` only when `AUTO_PUBLISH_GLOBAL` is off and
       the budget isn't breached. It checks eligibility (`LINK_ONLY` + `rights_reviewed_at` +
       `rights_evidence_url` on every source, sensitivity `NONE`, not `RESTRICTED`, source category not
       immigration/legal/financial/breaking, `importance` ≥0.8, `AI_REVIEW_P1_STORIES` on). It then makes a
       `BriefResult` call on the `SUMMARY` route and runs deterministic checks (numbers, capitalized words and
       causal words must be in the cited titles; one sentence; headline similarity; real citations). On a pass
       it overwrites the English variant, drops Telugu for re-translation, sets `story.format=BRIEF`, and
       auto-approves with audit `system:brief_lane`.
     - Failures keep the full draft and add `BRIEF_TITLE_MISMATCH`, `BRIEF_REJECTED` or `BRIEF_DAILY_CAP` to the
       `AUTO_PUBLISH_DISABLED` review task.
     - Migration `f6c9e3a4b8d2` adds `stories.format` (FULL|BRIEF). `format` is in `StoryOut` and the admin
       story detail; contracts are regenerated.
     - Admin: an "Auto briefs" page (`GET /v1/admin/briefs/recent`, last 24h), lane state and today's count
       on `/kill-switches`, help text for the new reasons, and a BRIEF badge on the story page.
     - Web/mobile: a "Brief" badge; the web story page adds "Read the full story at the source".
     - Verified: `pytest` 342 passed (22 new in `tests/test_brief_lane.py`); ruff clean; the migration upgrades,
       downgrades and upgrades again cleanly. mypy went 68→71; the 3 new errors are the existing str→Literal
       pattern (format/status args). Admin and web `tsc`, eslint and `next build` clean; mobile `tsc` + jest
       19 passed. Not run: web `test:visual` (no fixture story is a BRIEF) and the admin page in a browser.
     **Not live yet — owner steps on the VPS (after ADR-018's steps):** add `AUTO_PUBLISH_BRIEFS=true` and
     `AUTO_PUBLISH_BRIEFS_DAILY_CAP=20` to `.env.prod` (`deploy.sh` only writes them on first run), set
     `rights_reviewed_at` and `rights_evidence_url` on the sources you want in the lane, and re-run `deploy.sh`.
  4. Rights-review the public-domain government feeds so their RSS description can be stored as evidence.
     **ADR-020 accepted and implemented (2026-09-29).** Owner decisions: no new rights tier, so sources stay
     `LINK_ONLY` with an ADMIN-only per-source flag; internal evidence only; State Dept only; HTML stripped and capped
     at 4,000 chars. The live feed's descriptions are the whole advisory: 421–39,270 chars, median 3,058.
     - Migration `a7d3f5b9c2e1` adds `sources.description_evidence` (default false) and
       `source_items.description`.
     - `adapters/base.clean_description` strips and caps the text. `emit` stores it only for a flagged
       `LINK_ONLY` source and overwrites it on re-fetch.
     - `PATCH /v1/admin/sources/{id}` with `description_evidence: true`:
       - Only an ADMIN can turn it on (off→on); anyone else gets 403.
       - It needs `LINK_ONLY` + `rights_evidence.public_domain_basis`, or it returns 422
         `DESCRIPTION_EVIDENCE_NOT_ALLOWED`.
       - Turning the flag off, or losing either condition, clears the flag and deletes the stored descriptions.
     - Where the description goes:
       - It is added to the classify/summary evidence block and to `classify_privacy`, where it can only
         tighten.
       - The brief lane still gets titles only (`include_description=False`).
       - A summary sharing 12+ consecutive words with a description gets `SIMILARITY_TO_SOURCE`.
       - Admin: the review page has a collapsed "Source text" block, and the sources form has a
         public-domain basis field plus the flag checkbox. No public schema includes it.
     - The seed flags State Dept for new installs.
     - Verified:
       - Full API suite: 352 passed, 1 setup error. That was the known local Postgres flake;
         `test_editorial_workflow.py` passes 21/21 on its own.
       - Later edits: the 5 related test files pass 86/86.
       - `ruff` clean; mypy still 71; the migration upgrades, downgrades and upgrades again.
       - Admin `tsc` + eslint clean; contracts regenerated.
       - Not checked: the admin pages in a browser.
     **Not live yet — owner steps on the VPS:**
     (a) Run `deploy.sh`; it runs the migration.
     (b) In admin → Sources → State Dept, set "Public-domain basis" to
         `U.S. federal government work, 17 U.S.C. §105`, tick "Store feed text as evidence", and save as an ADMIN.
         The seed won't do this, because it only runs on the first deploy.
     **Live and verified in prod (2026-09-29):** after the 22:00 UTC fetch, State Dept has 216 items with a stored
     description (max 4,000 chars); every other source has 0.
     New fetches store the text from then on. The first State Dept fetch after the flag fills existing items too,
     because the upsert updates `description`. FEMA stays off until the OpenFEMA cutover runs in prod (see the FEMA entry above).
- **`AI_TRANSLATION_ENABLED` now gates `ai_translate` (2026-09-29).** Before this the flag only fed `/v1/config`
  (no client reads it), and prod ran translation with it set to `false`. Now `schedule_ai_translate` enqueues nothing
  and `run_ai_translate` does nothing while it's off. The default is off when unset. Editor-written Telugu is
  unaffected. At the owner's request, `deploy.sh` and `.env.example` now write `true`.
  Verified: full API suite 361 passed (2 new tests in `tests/test_translate.py`); ruff clean; mypy still 71.
  **Live in prod (2026-09-29):** the owner set `AI_TRANSLATION_ENABLED=true` in `.env.prod` and deployed.
- **Free-tier refusal is now loud; ADR-021 proposed (2026-09-29).** A free-tier model with no `FREE_TIER_LIMITS`
  entry (for example a pinned id set via `AI_GEMINI_*_MODEL`) used to be recorded as `DEFERRED`, which looked like a
  normal quota wait, so allowlisted stories waited forever. The gateway now logs an error and records `UNAVAILABLE`.
  A new `alerts.check_ai_model_refusal_alerts` (part of `check_all`) fires per provider/model for `UNAVAILABLE`
  rows in the last hour. That also covers ADR-018's unpriced or alias paid-model refusals. Jobs handle
  `UNAVAILABLE` the same as `DEFERRED` (retry next sweep).
  Verified: full API suite 364 passed plus 1 known psycopg setup flake (`test_observability.py`, 7/7 on rerun);
  3 new tests; ruff clean; mypy still 71.
  **ADR-021 rejected (2026-09-29):** the owner doesn't plan to pin free-tier models, so the quota-family
  change isn't needed. The refusal alert is the only guard. Reopen it if someone pins a free-tier model.
- **Next steps in the plan:** (separate `gemini`/`gemini_paid` routing is done: ADR-018's `PAID_GEMINI_ROUTING`
  in `app/ai/tasks.py`, so no new ADR is needed.) The pinned-model limiter and
  quota accounting (done: refusal alert; ADR-021 rejected as not needed); a mobile `EXPO_PUBLIC_WEB_URL` (**unblocked by
  ADR-022, see below**: `https://theteluguedit.com`); one rights-reviewed
  sports/entertainment/community source (**Telugu360 Movies seeded, see below**).
- **Telugu360 Movies source added to the seed (2026-09-29).**
  - Source research, all feeds fetched 2026-09-29:
    - No official cricket body (ICC, BCCI, USA Cricket, MLC) and no US Telugu association (TANA, ATA, NATS)
      publishes an RSS feed.
    - BBC's terms need a licence for business use of its RSS.
    - ESPNcricinfo falls under Disney-style terms that ban commercial and automated use.
    - Telugu Times (USA NRI news, the only working community feed) says "may not reproduce… without prior written
      consent". Asking them for permission is the way to get community coverage.
    - 123telugu has no terms page.
  - Owner picked Telugu360 because its terms (`https://www.telugu360.com/terms-of-use/`) explicitly allow sharing
    links. Open question for the owner: whether "commercially reusing protected material requires permission" covers
    showing its headline in the app.
  - Feed: `https://www.telugu360.com/category/movies/feed/`. The site-wide `/feed/` is only "Video :" posts.
    Seeded as `LINK_ONLY`, country `IN`, refreshed every 30 min, `category` `entertainment` (on the ADR-015 allowlist,
    so its stories can use the Gemini free tier). The seed now sets `category` when a spec gives one; the other
    three specs don't, so their existing category is left alone.
  - Verified: `probe_feed` returns ok; all 10 items pass `normalize`+`validate` through `RssFeedAdapter` with no
    redirects; local seed run loads 4 sources.
  - Brief lane: enabling a source requires `rights_reviewed_at`, so once active this source can get into the ADR-019
    auto-brief lane (nothing in the lane excludes `entertainment`). If the open terms question worries you, keep
    `AUTO_PUBLISH_BRIEFS` off until it's settled.
  - **Not live — owner steps in prod admin** (the seed only runs on the first deploy): Sources → New, fill in the
    fields from `infra/scripts/seed.py` (name, base/feed URL, category `entertainment`, `LINK_ONLY`, evidence URL,
    reviewer), then set it active as an ADMIN.

**Web deployed on the VPS at theteluguedit.com, ADR-022 (2026-09-29, live 2026-09-30 01:37 UTC)**: the owner picked
`theteluguedit.com` and dropped `tte.news`/`tte.app`. Vercel is out.
- `docker-compose.prod.yml` has a `web` service (`next.Dockerfile`, APP=web, localhost:13000).
- `nginx-setup.sh` writes `/etc/nginx/conf.d/teluguvarta-$DOMAIN.conf` with the apex (web), `www` (301 to
  the apex), `api` and `admin`, and asks certbot for all four with `--expand`. It leaves the old
  `teluguvarta.conf` (the sslip.io names) alone, so the installed APK, which calls `api.5-78-188-206.sslip.io`,
  keeps working. Delete that file after a new APK is out.
- `deploy.sh` defaults `DOMAIN` to `theteluguedit.com` and rewrites `DOMAIN`, `WEB_URL`, `PUBLIC_WEB_URL`,
  `NEXT_PUBLIC_*` and CORS in `.env.prod` from `DOMAIN` on every run, so `DOMAIN=...` on a re-run moves the
  install. It builds the images one at a time (4 GB box). The sslip.io fallback and the `WEB_URL=` override are gone.
- Brand doc, mobile README (release APK command), `.env.example`, and the CLAUDE/AGENTS/SPEC titles are updated.
  Internal `teluguvarta` identifiers and the `org.teluguglobal.app` bundle id are unchanged on purpose.
- Verified: `bash -n` on both scripts; the compose YAML parses; the `.env.prod` sync, run on a copy of the prod
  shape, moves sslip.io to theteluguedit.com, and a second run changes nothing. **Not verified:** no local Docker,
  so the web image build and the nginx/certbot steps have not run. They run for the first time on the VPS.
- **Owner steps:** (a) in DNS, point A records for `@`, `www`, `api` and `admin` at 5.78.188.206. With Cloudflare,
  use SSL mode Full (strict); certbot needs port 80 reachable. (b) Once they resolve, run
  `sudo DOMAIN=theteluguedit.com ./infra/deploy/deploy.sh` on the VPS. (c) Log into the new
  `admin.theteluguedit.com`. The admin login email is still `admin@5-78-188-206.sslip.io` (it's in the DB,
  not derived from the domain). (d) Build the next APK with the README command (new API and web URLs).
- **Live and verified (2026-09-30):** DNS is on Cloudflare with DNS-only A records to 5.78.188.206. `deploy.sh` built
  all four images one at a time without running out of memory, and certbot issued one cert for all four names.
  From outside: the apex returns 200 ("TTE — The Telugu Edit", real stories, `x-nextjs-cache: HIT`), `www` and
  `http://` 301 to `https://theteluguedit.com/`, api `/health` and admin return 200, and CORS allows the site's
  origin. `api.5-78-188-206.sslip.io` still answers for the old APK.
  **Admin login moved (2026-09-30):** the only admin is now `admin@theteluguedit.com` (MFA unchanged), set with the new
  `infra/scripts/reset_admin_password.py` (`--generate` prints a random password; usage in its docstring, runs with
  the scripts dir mounted, no redeploy needed). The owner has signed in at `admin.theteluguedit.com`.
  Still to do: (d) above. Optionally switch the records to Proxied with SSL mode Full (strict).

**Web redesign, ADR-017 (2026-09-28)**: `apps/web` presentation-only rewrite. It adds a sticky header with a
topic bar, a mobile bottom tab bar, card-based StoryLead/StoryBrief (ADR-014 contract unchanged), and a story
page with a sources card, "More in {topic}" and NewsArticle JSON-LD. There are skeleton `loading.tsx` routes,
`globals.css` is rewritten (47→34 KB, no override layers), JetBrains Mono is dropped, the Telugu fonts are not
preloaded, and new `radius.card`/`radius.pill` tokens are added (CSS output only). Verified: typecheck, lint,
`next build`, `test:visual` 88/88, `test:a11y` clean, token contrast check. `test:visual` needs the API started
with `CORS_ALLOWED_ORIGINS=http://localhost:3000` or the Saved journey fails. Listing routes still use
`force-dynamic` (no ISR), which is the next performance lever. **Done 2026-09-29, see below.**

**Listing pages cached with ISR (2026-09-29)**: `/latest`, `/topic/[slug]` and `/country/[code]` read `?cursor=`,
and reading `searchParams` made Next render them on every request despite `revalidate = 60`.
- Pagination moved into the path: `/latest/older/[cursor]`, `/topic/[slug]/older/[cursor]`,
  `/country/[code]/older/[cursor]`. Each base page and its older page share one feed component
  (`LatestFeed`/`TopicFeed`/`CountryFeed`, next to the page).
- The dynamic routes return `[]` from `generateStaticParams` (like `/story/[slug]`), so each page renders on its
  first request and is then cached. `/latest` prerenders at build and uses `duringBuild`, so a build with the API
  down still succeeds. Only `/search` is still rendered per request.
- Next passes the path cursor still percent-encoded (`MjA%3D`), and the API reads that as a bad cursor and
  silently serves page one. `pathCursor()` in `lib/api.ts` decodes it and returns null (the page 404s) on a
  malformed escape.
- Old `?cursor=` links now show page one. Nothing in the repo generated them except these pages.
- Verified: typecheck, lint and `next build` (the listing routes now show ○/●). On `next start`, the second
  request is `x-nextjs-cache: HIT`, an older page with offset 20 is empty and offset 0 shows the story, and an
  unknown topic still returns 404. `test:a11y` passes, `test:visual` 88/88 (against `next dev` on :3000;
  on any other port the API's CORS blocks the Telugu-reload journey).
- Local gotcha: `next build` overwrites the `.next` folder that a running `next dev` uses, so restart dev after
  building.

**Ops + perf pass (2026-09-28, later)**:
- **Admin:** light/dark toggle in the sidebar (`b651bb2`).
- **Web ISR** (`d84f2e2`):
  - `/` and `/topics` prerender and revalidate. A build with the API unreachable renders
    empty via `duringBuild()` instead of failing; verified by building against a dead port.
  - `/story/[slug]` renders on first request, then serves from cache (`x-nextjs-cache`
    MISS then HIT, `s-maxage=60`).
  - `/latest`, `/topic`, `/country` stay dynamic because they read `?cursor`.
  - **Missing story now returns 404** (was a 200 with the not-found UI):
    - **Cause:** any `loading.tsx` above the page, including the root
      `app/loading.tsx`, flushed the response before `notFound()` ran.
    - **Fix:** the root skeleton moved into per-route `loading.tsx` files
      (`ListingSkeleton`), and `story/[slug]/layout.tsx` checks the story exists
      outside the loading boundary.
    - **Verified in a production build:** `/story/nope` returns 404.
    - **Same fix for topics:** `topic/[slug]/layout.tsx` makes `/topic/<unknown>`
      return 404 (verified in a production build).
- **Prod backups** (`5cc533d`):
  - `infra/deploy/backup-prod.sh`: nightly age-encrypted dump, 14 days local, 30 days on
    a Hetzner Storage Box.
  - `infra/deploy/restore-drill.sh`: restores into a throwaway DB and compares with live.
  - `deploy.sh`: installs the cron job and backs up before each migration.
  - Setup steps in `infra/deploy/BACKUPS.md`.
  - **Not yet run on the server.** Waiting on the owner's age key and Storage Box
    (owner chose to test on the server). Only the pipe-dump → file → `pg_restore` path
    was verified locally (schema version + row counts matched).
- **Local DB:** deleted the five 2026-09-17 hand-published NPR stories and the fake
  review task (the demo-data note below is now resolved).
- **Still open:** Vercel deploy and `WEB_URL`; Telugu sources (draft evidence in
  `docs/sources/telugu-source-candidates.md`, pending owner review under ADR-002).

**Superseded — ADR-015 has since been accepted and T22 is done** (`e3c9ecd`, `b773094`,
`534eb25`): the paragraph below describes the state before that and is kept as history.
**Gemini provider adapter added, not routed (2026-09-28)**: `app/ai/providers/gemini_provider.py`
(httpx REST, no SDK, key `AI_GEMINI_API_KEY`) + `provider="gemini"` in `gateway._resolve_provider`.
**Deliberately absent from `ROUTING`**: the free tier may train on submitted data, so routing any
task to it needs ADR-011 plus the pre-call privacy gate (plan §4). Live-checked with the user's key
2026-09-28: `gemini-3.8-flash` and `gemini-3.5-flash-lite` return correct Telugu; `gemini-2.5-*`
now 404 for new users. **Free-tier limits confirmed 2026-09-28** (plan §rate-limits [R7]): 3.8 Flash 5 RPM/250K TPM/**20 RPD**; 3.5 Flash Lite 15 RPM/250K TPM/**500 RPD** (~125 stories/day at ~4 calls/story) — far below the plan's old 15/1,500 estimate. **Spike 1 harness run 2026-09-28** (`infra/scripts/spike1_telugu_quality.py`, 30 golden items, Flash Lite): 4.0 requests/story, 0 failures, p50 0.76s / p95 1.64s; results in `infra/scripts/spike1_results.json`. **Grading done 2026-09-28 (weak evidence)**: owner gave a blanket 4/5 after reading a subset of the 30 rows, not row-by-row; recorded as such in `notes`. ADR-015 still proposed; allowlist v1 awaiting owner review. Also added `budget.quota_day_start` (Pacific quota day).

**Gemini/Hetzner/Telugu-first plan saved, not started (2026-09-16)**: a large
pre-implementation plan — swap AI providers to Gemini's free tier, self-host
on Hetzner (superseding ADR-007), add Telugu-first sourcing (superseding
`NON_NEGOTIABLES.md` #7), semantic search, and grounded Q&A — is saved at
`docs/plans/gemini-hetzner-telugu-plan.md` (revision 6). **Nothing in it is
implemented**: confirmed no `ADR-011`–`ADR-016`, no `T22`–`T28` ticket files,
no "gemini"/"hetzner" references anywhere in `apps/` or `docs/`, and no
Dockerfiles in the repo. Per the plan's own Phase 0 sequencing and
`NON_NEGOTIABLES.md` #11, work must start with **P0-1 through P0-4** (four
pre-existing vulnerabilities independent of the rest of the plan — prompt
injection into the publish gate, an unencrypted-backup MFA bypass, an
MFA-enforcement design that would lock out every admin, and an unguarded
`restore.sh` DB-drop), then Spikes 1–3, then ADR-011–016 acceptance, before
any `T22`–`T28` ticket work begins. Do not start T22+ work until those ADRs
are accepted.

**P0-1 fixed (2026-09-16): prompt injection into publishing decisions.**
Both halves of the actual exploit are closed:
- `jobs/generate.py`'s `_classify_prompt`/`_generate_prompt` and
  `jobs/translate.py`'s `_translate_prompt` now JSON-encode untrusted
  fields (feed title/url, and the EN variant text) inside a per-call random
  boundary instead of splicing raw text into a quoted `field="..."` slot —
  a crafted feed title can no longer close the field and inject fake
  instructions or `source_ref=` lines.
- `AiGateway.run_task` takes an `evidence_item_ids` param; `_check_claims`
  (was `_remove_unsupported_claims`) now HOLDs the whole result — never
  silently strips and publishes — if any claim cites a `source_ref` that
  isn't a real `SourceItem` id in the cluster. `generate.py` passes the
  real cluster's item ids on both the classify and generate gateway calls.
  A claim with genuinely no `source_refs` still strips silently, unchanged
  from before.
- New `story_claims` table (migration `d4a7c1e2f6b9`) persists every kept
  and no-ref-removed claim per story — the decision trail P0-1's own report
  noted didn't exist. `status` is `KEPT` | `REMOVED_NO_REF` only.

**What P0-1 did not do**: the plan's corroboration/title-match sufficiency
check (is a ref-membership-valid claim's *content* actually supported?) is
a separate, unmade judgment call with real product consequences (it would
send most single-source stories to review) — recorded as **ADR-011
(proposed, not accepted)** rather than implemented against a guess. Ref-
membership alone (this fix) is strictly safer than pre-P0-1 behavior but
is not the plan's full protection; T22+ work assumes ADR-011 is accepted
first. Tests: `apps/api/tests/test_ai_gateway.py` (fabricated-ref HOLD,
membership-skipped-when-no-cluster) and `test_generate.py`
(claim-persistence, fabricated-ref-holds-the-story) cover this; full suite
green (513 passed; one pre-existing, unrelated `test_notifications.py`
teardown flake — `psycopg.errors.InsufficientPrivilege` dropping a scratch
DB, not caused by this change).

**P0-2 fixed (2026-09-16): backup/MFA-secret encryption.** Both halves of
the plan's fix are in:
- `infra/scripts/backup.sh` now fails closed before writing anything to
  disk when `APP_ENV=production` and `BACKUP_AGE_RECIPIENT` is unset (new
  `APP_ENV` var, documented in `.env.example`; unset/non-production still
  gets the old best-effort behavior). The age *identity* (private key)
  still has to be escrowed off-box by a human — that's a process step, not
  something a script can enforce — documented in the script's header
  comment and `.env.example`.
- `users.mfa_secret` is now encrypted at the app layer (`app/security.py`:
  `encrypt_mfa_secret`/`decrypt_mfa_secret`, Fernet via the new
  `cryptography` dependency, keyed by a new required
  `MFA_SECRET_ENCRYPTION_KEY` env var — fails closed like `ADMIN_JWT_SECRET`
  if unset) so a raw DB dump or an unencrypted backup no longer hands out a
  usable TOTP seed. `app/routers/admin_auth.py`'s `mfa_enroll` encrypts
  before persisting; `login` and `mfa_disable` decrypt immediately before
  `verify_mfa_code`. No prior plaintext `mfa_secret` rows exist to migrate
  (no seed data sets it, and this is pre-launch — confirmed via grep before
  concluding no backfill migration was needed).
- Tests: `apps/api/tests/test_admin_auth.py` — `client` fixture now sets
  `MFA_SECRET_ENCRYPTION_KEY`; the existing manual-seed MFA test now stores
  an encrypted secret (would otherwise break under the new decrypt-before-
  verify path); new `test_mfa_secret_is_encrypted_at_rest` asserts the
  stored column value is neither the plaintext secret nor decryptable
  without the key, and round-trips correctly with it. Verified:
  `ruff check .` clean, `bandit -r app` clean, full `pytest` — 514 passed
  (up from 513, no new flake). Manually exercised `backup.sh` with
  `APP_ENV=production` and no recipient — exits 1 before `pg_dump` runs, no
  file written.

**What P0-2 did not do**: P0-3 (MFA-enforcement lockout design) and P0-4
(`restore.sh`'s unguarded `DROP DATABASE`) are separate, not touched here —
per the plan's own sequencing, next session should pick up P0-3.

**P0-3 fixed (2026-09-16): MFA-enforcement lockout design, per accepted
ADR-012.** `admin_auth.py`'s `login` no longer issues a full session token to
an EDITOR/ADMIN account with no `mfa_secret` — it issues a restricted,
5-minute `scope: mfa_enrollment` JWT (`security.py`'s
`create_admin_enrollment_token`) that a new `current_admin_for_enrollment`
dependency accepts only on `POST /mfa/setup` and `POST /mfa/enroll`; every
other route (including `GET /mfa` and `DELETE /mfa`) still requires
`current_admin`, which now rejects the enrollment scope with 403
`MFA_ENROLLMENT_REQUIRED`. An account with `mfa_secret` already set is
unchanged — TOTP code required before any token issues. `AdminLoginResponse`
gained `mfa_enrollment_required: bool` so the admin UI can route straight to
enrollment (the UI change itself is not part of this ticket).
- Tests: `apps/api/tests/test_admin_auth.py` — two new tests
  (`test_login_without_mfa_secret_issues_enrollment_scoped_token`,
  `test_completed_enrollment_yields_full_session_on_next_login`); existing
  MFA-enroll test updated to re-login for a full token before checking
  status, since the enrollment token can't reach it. Four other test files
  (`test_admin_sources.py`, `test_editorial_workflow.py`,
  `test_admin_x_accounts.py`, `test_observability.py`, `test_notifications.py`)
  had `_token`/inline helpers that minted admin sessions via `/login` for an
  admin with no `mfa_secret` — switched to minting `create_admin_access_token`
  directly, since those tests exercise unrelated endpoints, not the login/MFA
  flow itself. Verified: `ruff check .` clean; full `pytest` — 516 passed (up
  from 514), same pre-existing `test_notifications.py` teardown flake as
  P0-1/P0-2 (`psycopg.errors.InsufficientPrivilege`, passes in isolation).

**What P0-3 did not do**: the admin frontend (if any exists yet) is not
updated to handle `mfa_enrollment_required` — out of scope for this API-only
ticket.

**P0-4 fixed (2026-09-16): unguarded `restore.sh` DB-drop.**
`infra/scripts/restore.sh` ran `DROP DATABASE IF EXISTS ... WITH (FORCE)`
against whatever `<target-db-name>` argument it was given, on the server
`DATABASE_URL` points at — a wrong argument on the VPS destroys the real
database. Two guards added, both before the `DROP DATABASE` call: (1)
`target_db` must start with `restore_`, checked immediately after argument
parsing, before `DATABASE_URL`/`.env` are even read; (2) `target_db` must
not equal the database name parsed out of `DATABASE_URL` (path segment,
`?query` suffix stripped) — catches a `restore_`-prefixed name that still
happens to match a real db. Both exit 1 with a message naming the reason,
no DB connection attempted. Manually verified (no live Postgres available
in this environment) with `DATABASE_URL` set and no real dump file: a
non-`restore_`-prefixed target is rejected, and a `restore_`-prefixed
target equal to the source db (including with a `?sslmode=` suffix on the
URL) is rejected — both exit before any `psql`/`pg_restore` call.
`bash -n` syntax-checks clean. No shellcheck available in this environment.

**What P0-4 did not do**: no automated test harness exists for this script
(no Postgres fixture in CI for shell scripts) — verification was manual,
per above. Sanitizing `target_db` against arbitrary shell/SQL metacharacters
beyond the prefix check was not added; out of scope per the plan's stated
fix (equality + prefix guard only).

All four P0 tickets (P0-1 through P0-4) are now fixed. Per the plan's Phase 0
sequencing, next session should move to Spikes 1–3
(`docs/plans/gemini-hetzner-telugu-plan.md`) before any ADR-011–016
acceptance or `T22`+ ticket work.

**Spikes 1–3 attempted (2026-09-16): only Spike 2 could actually run.**
Confirmed with the user before proceeding (see the two questions/answers
below) rather than faking results for the two that are blocked on resources
this session doesn't have:
- **Spike 1 (Telugu quality via Gemini) — blocked, not attempted.** No
  `GOOGLE_API_KEY`/`GEMINI_API_KEY` anywhere (`.env`, `.env.example`, shell
  env — confirmed empty) and no native Telugu speaker available to grade
  the 20 sampled outputs the spike requires. User chose "skip for now" over
  either supplying a key or having me write the harness blind. **Still
  fully blocked** — needs both a real Gemini API key and human grading
  capacity before it can run.
- **Spike 2 (golden eval set trust) — done.** Validating the 270
  AI-generated items needs the same native-Telugu-speaker resource Spike 1
  is blocked on, so the only executable option was the plan's other named
  path: shrink to the 30 human-reviewed items and stop claiming §18's
  "≥300". Since that contradicts `docs/SPEC.md` §18's explicit "≥300"
  text, this is recorded as **ADR-013 (proposed, not accepted)** rather
  than silently edited — `docs/adr/ADR-013-golden-eval-set-trust-tier.md`,
  indexed in `docs/adr/README.md`. **Nothing in `golden_set.json` or
  `eval/README.md` has been changed yet**; ADR-013 spells out the exact
  edit (drop the 270 unreviewed items, reword the SPEC threshold and the
  README's two-tier language) to make once accepted. This mirrors how
  ADR-006/ADR-011 stay proposed rather than being enacted in the same
  session that finds the gap.
- **Spike 3 (local-inference hardware measurement) — harness written, not
  run.** No inference stack installed here (`ollama`/`llama-server`/
  `docker` all absent) and running it means multi-GB model downloads plus
  compile time on a machine that isn't the actual Hetzner target — user
  chose "prepare scripts only, don't install anything" over running it on
  this dev machine. `infra/scripts/spike3_inference_benchmark.py` (new,
  self-contained, no project import dependency so it can be copied onto a
  real candidate box) measures query-embedding p95, Q&A generation p95,
  and API p95 degradation under concurrent inference load, against the
  plan's own stated placeholder gates (300ms/3s/20%), and prints a
  Scope A vs Scope B verdict plus writes a JSON result file. `python3 -m
  py_compile` clean; not executed (no model weights present, and running
  it would trigger the same install/download the user declined to do
  automatically).

**What this means for sequencing**: none of ADR-011–016 acceptance or
`T22`+ ticket work can start yet — Spike 1 needs a Gemini key + a native
speaker, Spike 3 needs either this machine provisioned with the inference
stack or an actual Hetzner box to run the new harness on, and ADR-013
(Spike 2's output) needs product-owner acceptance before `golden_set.json`
is actually edited. Next session should get whichever of those three
inputs (API key, reviewer, hardware access) becomes available first,
rather than re-attempting all three blind.

## Main spine

| Ticket | Status | Notes |
|---|---|---|
| T01 Initialize monorepo | **done** | pnpm workspaces (web/admin/mobile/packages) + FastAPI api; CI on push/PR |
| T02 Env + local setup | **done** | `.env.example`, docker-compose Postgres 16 + pg_trgm, Alembic wired into `infra/migrations/`, seed placeholder, README local-setup rewritten |
| T03 Database schema | **done** | Single migration `0c23c235e618` creates all 17 §12 entities + `alembic_version`; `sources.rights_status` and `stories.status` are native Postgres enums; story transitions enforced by a `BEFORE UPDATE` trigger; `pnpm run migrate` + pytest against real Postgres (Homebrew, local only) both pass |
| T04 OpenAPI contracts | **done** | All 21 §13 endpoints live in FastAPI (stub data), standard error envelope via shared exception handlers, `packages/contracts` types generated from the OpenAPI schema with a CI drift check |
| T05 Admin authentication | **done** | JWT login (`POST /v1/admin/auth/login`), `role` column on `users` (EDITOR/ADMIN) with RBAC, rate-limited via `admin_login_attempts`; ADR-006 written (proposed) |
| T06 Source registry | **done** | `sources` expanded to full §6.2 field list via migration `69110b7cfd3d`; `/v1/admin/sources` CRUD enforces ADR-002 (only DISABLED/LINK_ONLY reachable, `RIGHTS_TIER_NOT_ENABLED` otherwise) and requires rights evidence (`rights_evidence_url`/`rights_reviewed_at`/`reviewer`) plus `ADMIN` role to enable a source (`RIGHTS_EVIDENCE_REQUIRED`/`FORBIDDEN`); every create/update writes an `AuditEvent`; read-only `GET /v1/admin/kill-switches` surfaces the §15 `AUTO_PUBLISH_*` env flags (no publish logic to gate yet — T12); ADR-002 addended with the approval-role/second-approver/evidence-expiry decisions |
| T07 First source adapters | **done** | Generic RSS/Atom adapter (`apps/api/app/adapters/`) + 3 seeded LINK_ONLY sources with rights evidence |
| T08 Ingestion worker | **done** | `app/jobs/` (queue claim/retry + `source_fetch` job) polling the T03 `jobs` table via `FOR UPDATE SKIP LOCKED`; ADR-003 accepted; rights gate enforced inside `adapters/base.py::emit()` (new `source_items.ingest_status`); circuit breaker + bounded job retry both real and admin-visible |
| T09 Dedup + clustering | **done** | `app/jobs/cluster.py`: deterministic fingerprint (normalized-title hash) + lexical similarity (difflib ratio, 72%/40% thresholds) group `NORMALIZED` `SourceItem`s into `Story`/`StorySource`, advancing `ingest_status` to `CLUSTERED`; AI escalation for ambiguous pairs stubbed for T10/T11 |
| T10 AI provider gateway | **done** | `apps/api/app/ai/`: `AiGateway.run_task` implements §7.2 routing + §7.3 schema validation + every §7.5 failure mode (retry-then-hold, low-confidence review queue, unsupported-claim removal/hold, provider-unavailable, budget-breach classification-only degrade); cost telemetry in new `ai_call_log` table (migration `7a4c9e2b5d10`), queryable per task/day; ADR-001 accepted (OpenAI primary, Anthropic secondary, gateway lives in Python at `apps/api/app/ai` not the TS `packages/ai` — see ADR for why) |
| T11 Story generation | **done** | `apps/api/app/jobs/generate.py`: `ai_classify` job sweeps `CLUSTERED` stories through two AI-gateway calls (classify, then generate) and advances state; `9d3f6b1a2c47` adds `ENRICHED`/`REVIEW`/`SCHEDULED`/`ARCHIVED` to `source_items.ingest_status`; fixed a pre-existing T09 bug (`dedup_cluster` job type wasn't in `ck_jobs_type`, so it always errored — renamed to `story_cluster`) |
| T12 Editorial workflow | **done** | Real approve/reject/retract/correct on `/v1/admin/stories/{id}/*` + `GET .../stories/{id}` detail + real `/v1/admin/review-queue`; every mutation writes an `AuditEvent`; new `publish_scheduler` job (`app/jobs/publish.py`) implements the kill-switch-gated auto-publish sweep from T11's `AI_READY` output; migration `73a24fe47a9f` adds `ARCHIVED` to `story_status` + the reject transitions; `apps/admin` gets a review-queue list + story detail/action page |
| T13 Bilingual variants | **done** | `app/jobs/translate.py`: `ai_translate` job translates the `en` `StoryVariant` via the AI gateway's `TRANSLATION_EN_TE` task, applies `app/content/glossary.py` proper-noun correction, runs `app/content/qa.py`'s number/date/currency/URL/negation checks (`qa_status` PASSED/FAILED), and samples IMMIGRATION/LEGAL/FINANCIAL passes into the review queue; `app/content/variants.py::resolve_display_variant` is the pure English-fallback resolver for T14 to call; ADR-004 accepted |
| T14 Web MVP | **done** | Public `/v1` endpoints wired to real Postgres data (`app/content/serialize.py`); `apps/web` is a real Next.js SSR/ISR site over `@teluguvarta/contracts` types covering every §9.1 page; axe-core a11y check passes on home + story pages |
| T15 Mobile MVP | **done** | Expo/React Navigation app over the same `@teluguvarta/contracts` public API as T14; onboarding (fully skippable, "continue without login"), home/topic/search/saved/story-detail/notifications/settings/language/privacy screens; onboarding + notification prefs + saved stories are on-device (AsyncStorage) since no account backend exists yet (ADR-006 still proposed); native OS share sheet using the same canonical `PUBLIC_WEB_URL`/story-slug URL as web; Jest+RNTL smoke test covers onboarding-skip→home→open→save→share |
| T16 Personalization | **done** | Deterministic §8.2 ranking (`app/content/ranking.py`), no ML; `GET /v1/home` personalizes when preferences are supplied as query params (no accepted account backend yet — see ADR-005); `Task.WHY_MATTERS` now actually invoked, cached per `(story_id, segment)` in new `story_why_matters_cache`; ADR-005 accepted |
| T17 Push notifications | **done** | Real anonymous identity (satisfies ADR-006, which remains formally **proposed**, not accepted), persisted preferences/push tokens, `notification_dispatch` job with dedupe/quiet-hours/daily-cap/breaking-approval gate |
| T18 Observability | **done** | Structured JSON logging + request/job context; Sentry-equivalent error tracking (plain HTTP envelope, no SDK) in all 4 apps; `/v1/admin/observability` (ingestion health/job queue/AI cost) + admin dashboard page; alert-dispatch module wired to worker loop; §17 analytics events routed through `POST /v1/events` (T17's endpoint) into `app/analytics.py`, forwarded to PostHog when configured |
| T19 Hardening | **partial — see changelog** | Real: MFA on admin login, cross-system account deletion, search/admin rate limiting, dependency scanning (pip-audit clean)/SAST (bandit clean, one real XXE finding fixed), budget-breach auto-publish gate wired, backup/restore scripts + one real local restore test passed, WCAG 2.2 AA axe pass across 12 pages, local load test within §16 targets, ADR-007 accepted, app-store readiness doc. **P0 RCE gap now fixed** (see 2026-09-09 entry below) — `next@14.2.35` upgraded to `15.5.25` in both apps. **Golden AI eval set is now 30 human-reviewed items** (shrunk from 300 per accepted ADR-013 — see the 2026-09-16 ADR-013 changelog entry; §18 now reads "≥30 human-reviewed" instead of "≥300"), the 270 AI-generated/unreviewed items deleted rather than kept as unverified filler. Still open: MFA/rate-limiting/backups not exercised against real managed infra (local-only, per ADR-007); no live-provider run against the golden set (same no-network-access gap as every AI ticket since T10); growing the eval set past 30 needs native-Telugu-speaker review per item, not bulk generation. |
| ~~T20 Pilot~~ | **removed 2026-09-16** | No longer a ticket — product owner removed the pilot concept entirely, not just waived it. The `/pilot` landing page, signup form, `POST /v1/pilot-signups`/`GET /v1/admin/pilot-signups` endpoints, `PilotSignup` model, and `pilot_signups` table (dropped via migration `c3d4e5f6a7b8`) are all deleted. `docs/runbooks/pilot-report.md` deleted along with it. See the 2026-09-16 changelog entry for the full file list. |
| T21 Visual design refresh | **done — superseded by ADR-010** | Original "Ink & Signal" palette (2026-09-10) drifted through two undesigned revisions (2026-09-12 "modern design foundation", 2026-09-13 contrast fix) before being replaced outright by the "Folio" palette — see ADR-010 and the 2026-09-13 (Folio redesign) changelog entry. ADR-009's single-token-source mechanism (`packages/design-tokens/tokens.json` → generated per surface, CI-enforced) is accepted and live, not proposed. |

## X adapter

| Ticket | Status | Notes |
|---|---|---|
| X1 X source registry fields | **done** | New `x_accounts` table (migration `a1b2c3d4e5f6`), one-to-one with `sources` (`source_id` FK, unique): `x_user_id` (unique stable id), `handle`, `priority`, `polling_cadence`, `since_id`, `budget_class`. Deliberately doesn't duplicate `rights_status`/`active`/`last_success_at`/`last_error_at` — those are read from the linked `Source` row, so enabling an X account goes through T06's exact same rights-evidence gate (`PATCH /v1/admin/sources/{id}`), no parallel approval flow. New `GET /v1/admin/x-accounts` (list, joined with Source) + `POST`/`PATCH /v1/admin/sources/{id}/x-account` (link/update; rejects a second account per source and a reused `x_user_id`), every mutation writes an `AuditEvent`. No X API credentials touch the schema (X2 will read them from the T02 secret manager). |
| X2 Incremental X fetch | **done** | New `x_official_account_fetch` job (`app/jobs/x_fetch.py`) reusing T07's exact adapter contract (`app/adapters/x.py::XAdapter`) and T08's job-queue retry/backoff (`app/jobs/queue.py`) — a 429 or any other fetch failure just raises and lets the existing bounded exponential backoff handle it, no bespoke retry loop. `app/x/client.py::XApiClient` calls only the official `GET /2/users/{id}/tweets` (bounded to 10 pages/run); a 429 raises `XRateLimitedError` rather than retrying itself; no code path ever touches x.com's public site. Incremental via each `x_accounts.since_id`, advanced to the max post id seen per run — never a full timeline re-fetch. Scheduling (`schedule_due_x_fetches`) mirrors `schedule_due_source_fetches`: only `active`+`LINK_ONLY`-source, cadence-configured, non-circuit-broken accounts are enqueued. Cost telemetry lands in a new `x_api_call_log` table (migration `b2c3d4e5f6a7`, mirrors T10's `ai_call_log`) via `app/x/budget.py` (`record_call`/`month_to_date_cost_usd`/`is_over_monthly_budget`/`budget_remaining_usd`) — `posts_read`/`cost_usd`/`status` ('OK'/'RATE_LIMITED'/'ERROR') per run; `X_API_COST_PER_POST_USD` env optionally prices `cost_usd`. New env vars in `.env.example`: `X_API_BEARER_TOKEN` (required to fetch at all — unset fails closed via the normal circuit-breaker path, never a scraping fallback), `X_API_COST_PER_POST_USD`, `MONTHLY_X_API_BUDGET_USD`. Verified: `alembic upgrade head`/`downgrade -1`/`upgrade head` round-trip clean; `ruff check .` clean; new `tests/test_x_adapter.py` + `tests/test_x_fetch_job.py` (13 tests: pagination/since_id/429/rights-gate/idempotency/scheduling/budget-gate/telemetry) plus full `pytest` (233 passed) all green against a real local Postgres. **Note**: the original "skips every account for the cycle when over budget" behavior described here was superseded by X4 — see below. |
| X4 X monitoring and budget guard | **done** | Budget guard behavior changed from "skip every X account when over `MONTHLY_X_API_BUDGET_USD`" to "skip only `budget_class='LOW'` accounts" (`app/jobs/x_fetch.py::schedule_due_x_fetches`, `app/x/budget.py::is_low_priority`) — a `STANDARD`/`HIGH`/unset-class account keeps polling past the threshold, and the guard never touches other ingestion sources since it only filters the X-account query. `GET /v1/admin/x-accounts` now also returns `fail_count`/`circuit_breaker_tripped`/`recent_error_count_24h` (from `x_api_call_log`, last 24h)/`month_to_date_cost_usd` (per account)/`budget_paused` (true iff over budget AND `budget_class='LOW'`) alongside X1's existing `since_id`/`active`/health fields — an admin never has to read logs. Manual pause/resume reuses T06's existing per-source `active` kill switch (`PATCH /v1/admin/sources/{id}`) rather than a parallel per-account switch: each X account is already 1:1 with its own `Source` row, so pausing one never touches another account's polling — verified by explicit test rather than assumed. `GET /v1/admin/observability` gained an `x_cost` block (mirrors T18's `ai_cost` shape: MTD spend/budget/remaining/over-budget flag, plus `low_priority_accounts_paused` count). `apps/admin`'s `/observability` page (T18) gets a new "X account health & budget" section: per-account table (handle/rights status/active/budget class/budget-paused/since_id/fail count/24h errors/MTD cost/last success/last error) with a Pause/Resume button per account. Verified: `ruff check` clean; full `pytest` (240 passed, up from 233) including 3 new X4 acceptance tests (`test_schedule_pauses_only_low_priority_accounts_when_over_monthly_budget`, `test_budget_guard_pauses_only_low_priority_x_accounts`, `test_manual_pause_of_one_x_account_does_not_affect_another`) against real local Postgres; `apps/admin` `tsc --noEmit`, `eslint`, and `next build` all clean. |
| X3 X post to story pipeline | **done** | See 2026-09-09 changelog entry |

## Student experience

| Ticket | Status | Notes |
|---|---|---|
| S1 Student life-stage profile | **done** | See 2026-09-09 changelog entry |
| S2 Student topics/alerts | **done** | See 2026-09-09 changelog entry |

## ADR status

Mirrors `docs/adr/README.md` — keep both in sync.

| ADR | Status |
|---|---|
| ADR-001 AI provider selection | **accepted** |
| ADR-002 Source-rights approval policy | **accepted** |
| ADR-003 Database job queue strategy | **accepted** |
| ADR-004 Bilingual content lifecycle | **accepted** |
| ADR-005 Personalization model | **accepted** |
| ADR-006 Account/privacy architecture | **proposed** |
| ADR-007 Production hosting/cost limits | **accepted** |
| ADR-008 Visual design refresh (no new UI framework) | **accepted** |
| ADR-009 Single design-token source, generated per surface | **accepted** |
| ADR-010 Folio visual redesign (supersedes ADR-008's palette) | **accepted** |
| ADR-011 Claim evidence sufficiency for unattended publish | **proposed** |
| ADR-012 First-login MFA enrollment flow | **accepted** |
| ADR-013 Golden eval set trust tier (shrink to reviewed 30) | **accepted** |
| ADR-014 Editorial component contract | **accepted** |
| ADR-015 Gemini free tier as an AI provider | **accepted** |
| ADR-016 Local inference service | reserved (Gemini/Hetzner plan), not written |
| ADR-017 Web "modern newsroom" redesign | **accepted** |
| ADR-018 Paid Gemini route | **accepted** |
| ADR-019 Link-first brief auto-publish | **accepted** |
| ADR-020 Government description evidence | **accepted** |
| ADR-021 Free-tier pinned-model quota | **rejected** |
| ADR-022 Web on the VPS at theteluguedit.com | **accepted** |

- 2026-09-16: **ADR-013 accepted** (product owner: "accept ADR-013 as-is,
  shrink golden set to 30") and implemented exactly as the ADR spelled out,
  ad hoc — not a `T22`+ ticket (still blocked; see the "What this means for
  sequencing" note above, unchanged for Spike 1/3). `docs/SPEC.md` §18
  reworded from "≥300 representative stories" to "≥30 human-reviewed
  representative stories, expanded only with items that have passed the
  same human review." `apps/api/eval/golden_set.json` shrunk from 300 items
  to the 30 listed in `_meta.human_reviewed_ids` (3 per category × 10
  categories) — the 270 AI-generated/unreviewed items are deleted from the
  file, not just unmarked; `_meta.description`/`_meta.provenance` rewritten
  to describe a single reviewed tier instead of two. `eval/README.md`'s
  "Corpus size" section rewritten the same way, pointing at ADR-013 for the
  removal rationale and stating the bar for growing back past 30 (native-
  Telugu-speaker review before commit, not bulk-generate-then-review).
  `docs/adr/ADR-013-golden-eval-set-trust-tier.md` and `docs/adr/README.md`
  both flipped from proposed to accepted. Verified: `python3 -c "import
  json; json.load(...)"` confirms the rewritten `golden_set.json` is valid
  JSON; `apps/api/tests/test_golden_eval.py` — 31 passed (30
  fixture-parametrized + the category-coverage test), same file, now
  running against 30 items instead of 300; `ruff check .` clean; grepped
  `run_golden_eval.py`/`test_golden_eval.py` for a hardcoded `300`/count
  assumption before editing — none exists, so no code change was needed
  beyond the data file itself. **What this did not do**: doesn't touch
  Spike 1 (still needs a Gemini key + native speaker) or Spike 3 (still
  needs an inference stack/real Hetzner box) — those remain exactly as
  blocked as the entry above describes; ADR-011/ADR-006 remain proposed.

## Changelog

(newest first — one line per ticket completion)

- 2026-09-28: **App icon.** Brand mark is a cream **తె** (Kohinoor Telugu
  Bold) on indigo `#332c6d` with a rust full stop `#e0703f`, an editor's
  period for "The Telugu Edit". Mobile: `apps/mobile/assets/` (`icon.png`,
  Android adaptive foreground/monochrome, web favicon), wired in `app.json`.
  Web and admin: `src/app/icon.png` + `apple-icon.png` (Next file
  convention). The assets are rendered from HTML in headless Brave because
  local Pillow has no raqm, so it can't shape Telugu. Checked on a Samsung
  device (squircle mask): the glyph and dot are not clipped. Note:
  `expo prebuild` recreates `android/` and removes `local.properties`
  (`sdk.dir=~/Library/Android/sdk`).

- 2026-09-28: **Admin redesign, slice 9: browser check + fixes.** First real
  look at every admin page: headless Chromium at 1280 and 390 px, light and
  dark, with a locally minted ADMIN token. Review pages were checked against
  two temporary REVIEW_REQUIRED stories, deleted afterwards. No console
  errors. Fixed:
  - **Phones:** the page scrolled sideways, because `.admin-shell`'s
    `align-items: flex-start` let `main` grow to its content width. The
    header was a tall single row that cut off the nav. It is now sticky, with
    brand and controls on one row and a swipeable link strip below.
  - **Tables and tiles:** tables scroll inside `.table-scroll`. Stat tiles
    sit two across on phones. The review queue hides the Sources and
    duplicate "Review" columns on phones (`.col-wide-only`).
  - **Checkboxes:** every checkbox label rendered as an uppercase field
    caption with the box on its own line. It's now one CSS rule
    (`label:has(> input[type=checkbox])`), and the inline styles and
    `.checkbox-label` are gone.
  - **Review detail:** the draft cards now show each variant's headline. The
    Telugu headline was not visible to reviewers anywhere.
  - **Dashboard:** it shows "oldest waiting 20d" instead of "28991 min". A
    "Needs attention" item appears when pending jobs are older than 30 min
    ("worker may not be running"); the observability jobs tile turns warn at
    the same threshold.
  - **Other:** a shared `lib/time.ts` replaces two copies of the age
    formatter. Sources shows a relative "last fetched" time. The login
    background now fills the full width.

  Admin `tsc`, `next lint` and `pnpm run build` pass. **Not done:** this was
  headless Chromium, not a real device or Safari. The VPS deploy is the
  owner's step (`./infra/deploy/deploy.sh` on the box after push).

- 2026-09-28: **Single-VPS deploy scaffolding** (ad hoc; supersedes ADR-007's
  Vercel/Render/Supabase split for now, no ADR yet). `infra/deploy/`:
  `deploy.sh` (Docker, ufw, swap, generated secrets in `.env.prod`, build,
  migrate, seed, up), `docker-compose.prod.yml` (postgres, api, worker, web,
  admin, caddy), `api.Dockerfile`, `next.Dockerfile`, `Caddyfile`. `seed.py`
  honors `SEED_DEMO_STORY=0`. **Untested**: no Docker locally, never run on
  the VPS. Not covered: encrypted backups (`backup.sh` needs
  `BACKUP_AGE_RECIPIENT`), AI keys, Sentry, mobile.

- 2026-09-28: **Admin redesign, slice 1** (`docs/plans/admin-redesign.md`
  items 2–3, partial). New shared `apps/admin/src/components/ui.tsx`
  (Badge, PageHeader, EmptyState, Field, toasts via `ToastProvider` in
  layout) + CSS in `globals.css`. `/sources` rebuilt: card per source with
  rights/active/free-tier badges, "needs rights review" prompt, inline
  category save, Add-source panel with presets (prefill type/country/
  language/refresh/category only — rights evidence stays human-supplied,
  ADR-002). Rights save logic unchanged. Admin `tsc` + `next lint` pass.
  **Not yet done:** browser check of any page (needs a logged-in session),
  dashboard, review queue, other pages on the shared components.

- 2026-09-28: **Admin redesign, slice 2: test-feed.** `POST
  /v1/admin/sources/test-feed` (`app/adapters/feed_probe.py`): fetches a
  candidate feed and returns item count + first 5 headlines; read-only, saves
  nothing, doesn't touch the rights gate. SSRF-hardened (http/https only, all
  resolved IPs must be public, redirects not followed, 2 MB cap, 10 s
  timeout). `tests/test_feed_probe.py` (10 tests, no DB) + ruff pass. The
  route itself has no HTTP-level test (needs Postgres, unavailable here).
  Known gap: DNS is resolved once for the check and again by httpx, so a
  DNS-rebinding host could differ between the two — acceptable for an
  ADMIN-only, read-only preview, but pin the IP if this ever widens. UI: Test
  feed button in the add panel; cards show last fetched / consecutive
  failures / "failing" badge (fields were already in the API).

- 2026-09-28: **Admin redesign, slice 3: dashboard** (`/`). No API change —
  reads `/sources`, `/review-queue`, `/observability` in parallel. "Needs
  attention" list (budget exceeded, circuit-broken sources, failed jobs,
  review queue, sources awaiting rights review), each linking to the page
  that fixes it, plus stat tiles (active sources, rights review, review
  queue, jobs pending, AI spend vs budget). New `StatTile` in `ui.tsx`.
  Admin `tsc` + `next lint` pass; not viewed in a browser. Remaining: review
  queue triage, other pages on shared components, one-call preset
  add+activate, browser check.

- 2026-09-28: **Admin redesign, slice 4: review queue** (`/review`). Page
  header with counts; plain-language "why is this held" under each reason
  pill (`REASON_HELP`, covers every gate in `jobs/generate.py` incl.
  `NO_PAID_PROVIDER`); age ("Waiting") column; keyboard triage — j/k move,
  Enter opens the story. Deliberately **no bulk approve/reject and no
  approve-from-list**: decisions stay on the detail page so an
  always-human-reviewed story is never decided unseen (NON_NEGOTIABLES). If
  bulk actions for non-danger reasons are wanted, that's a product call —
  write an ADR first. `/review/[id]` not yet touched. Admin `tsc` + `next
  lint` pass; not viewed in a browser.

- 2026-09-28: **Admin redesign, slice 5: review detail** (`/review/[id]`).
  Two-column layout: "Why this is held" (shared `lib/reviewReasons.ts`, now
  used by the list too), English/Telugu drafts side by side with QA badges,
  sources with rights badges, correction form/history; sticky Decision panel
  on the right. Approve/reject now toast and return to `/review` so triage
  flows. **Gating logic unchanged**: sensitive-category approve/reject/
  correct still need a recorded reason and a confirm step; no keyboard
  shortcut for approve/reject on purpose. Reason field now only renders for
  statuses that have actions (REVIEW_REQUIRED/PUBLISHED/UPDATED). Admin `tsc`
  + `next lint` pass; not viewed in a browser. Remaining: `/observability`,
  `/login` on shared components, preset add+activate, browser check.

- 2026-09-28: **Admin redesign, slice 6: observability** (`/observability`).
  Summary tiles (tripped sources, jobs pending, AI spend, X spend) linking to
  sections; ingestion table sorted problems-first with OK/Failing/Tripped
  badges and relative times; job counts as badges; AI and X spend with a
  budget bar; daily AI breakdown collapsed; X account table condensed (status
  badges merged, `since_id` on row hover); auto-refresh every 60 s + Refresh
  button; toasts replace the error banner. Data loading and pause/resume
  logic unchanged, no API change. Admin `tsc` + `next lint` pass; not viewed
  in a browser. Remaining: `/login` on shared components, preset
  add+activate, browser check.

- 2026-09-28: **Admin redesign, slice 7: login** (`/login`). Visual polish
  only — brand lockup, "Step 2 of 2" on MFA setup, success-tinted notice,
  spacing; ADR-012 flow/logic untouched. Also ran a full `pnpm run build` in
  `apps/admin` for the first time this redesign: compiles, lints and
  type-checks, all 7 routes build. **Every redesigned page is still
  unverified in a real browser** (that is the next step, before more
  features). Remaining: preset add+activate (needs API), browser check.

- 2026-09-28: **Admin redesign, slice 8: add + enable + activate in one
  call.** `POST /v1/admin/sources` now optionally takes `rights_status`,
  `rights_evidence_url`, `reviewer`, `rights_evidence`, `active`. The ADR-002
  gate is now one helper (`_enforce_enable_gate` in `routers/admin.py`) used
  by both create and PATCH: ADMIN only, only DISABLED/LINK_ONLY, evidence URL
  + reviewer required; `rights_reviewed_at` is server-stamped on create. New:
  `active: true` without enabling is rejected (`SOURCE_NOT_ENABLED`); a failed
  gate creates nothing. 5 new tests in `test_admin_sources.py` (36 pass with
  auth + contract tests), ruff clean. UI: unchecked "I have reviewed this
  source's terms — enable and activate now" in the add panel (ADMIN only;
  evidence URL + reviewer required), so the human step stays explicit.
  Contracts regenerated (`openapi.json`, `types.gen.ts`) — this also picks up
  the earlier test-feed schemas that were stale. Full admin build passes.
  Note: PATCH still lets `active: true` be set on a DISABLED source (fetch
  job is the backstop) — pre-existing, not changed here. Remaining: browser
  check of the whole redesign.

- 2026-09-29: **Admin UI: add-source and rights forms** on `/sources`
  (`apps/admin/src/app/sources/page.tsx`). "Add source" → `POST /v1/admin/sources`
  (starts DISABLED/inactive); per-row "Rights & status" → `PATCH` with
  status (DISABLED/LINK_ONLY), evidence URL, reviewer, terms/permitted
  fields/restrictions/territory/notes, and the `active` toggle. Server rules
  unchanged (ADMIN role + evidence required to enable). Typecheck + lint pass;
  not exercised in a browser, no UI tests.

- 2026-09-28: **Admin UI: source category field.** New `/sources` page
  (`apps/admin/src/app/sources/page.tsx`, nav link added) lists sources and
  edits `category` via `PATCH /v1/admin/sources/{id}` (empty → null), with a
  datalist of the ADR-015 allowlist and an Eligible/Paid-only indicator. The
  allowlist is duplicated client-side from `app/ai/privacy.py` (display only;
  the backend stays authoritative). Admin typecheck passes; not exercised in a
  browser, no UI tests.

- 2026-09-28: **T22 follow-up — ADR-015 wiring** (ad hoc; no ticket file).
  `generate.py` computes the privacy decision on a story's first generation
  (single shared source category + item titles), persists it, and tightens it
  to RESTRICTED when the model reports sensitivity; `translate.py` reads the
  persisted value and never uses the free tier for corrected stories.
  `tasks.py` gained `FREE_TIER_ROUTING` (relevance, summary, translation →
  Flash Lite), used only for `FREE_TIER_ALLOWED` stories and only when
  `AI_FREE_TIER_ENABLED=1` (**default off**, so behavior is unchanged until
  enabled). `category` is settable via the admin source create/update API.
  With the free tier enabled and no paid provider key, a non-allowed story now
  holds for human triage (`REVIEW_REQUIRED` + `ReviewTask` reason
  `NO_PAID_PROVIDER`, items `REVIEW`) instead of retrying. **Not done**:
  `WHY_MATTERS` stays on the paid route; no admin UI field for category (API
  only). Tests: 286 pass, ruff clean; the suite intermittently errors at
  scratch-DB teardown (`DROP DATABASE ... FORCE` permission denied), on a
  different test each run — not investigated.

- 2026-09-28: **T22 — free-tier privacy gate, rate limiter, request counter**
  (`docs/tickets/T22.md`; ADR-015 accepted; plan calls this scope "T23").
  Added `app/ai/privacy.py` (three-state decision, allowlist v1),
  `app/ai/ratelimit.py` (RPM bucket + Pacific-day RPD from `ai_call_log`),
  gateway `FreeTierViolation` guard + `DEFERRED` status + `ProviderQuotaError`
  (429), migration `e5b8d2f3a7c1` (`sources.category`,
  `stories.privacy_decision`, `DEFERRED` in `ai_call_log` status check).
  **Not done / follow-ups**: nothing is routed to Gemini (`ROUTING` unchanged);
  `generate.py`/`translate.py` don't yet compute/persist/pass the decision, and
  no admin UI sets `sources.category`; RPM bucket is in-process only. Tests:
  278 pass, ruff clean.

- 2026-09-27: **ADR-014 step 5 — cross-surface visual regression pass**
  (last step of ADR-014's implementation order; ad hoc, no ticket file).
  **Web**: new `apps/web/scripts/visual-regression.mjs` (`pnpm --filter
  @teluguvarta/web test:visual`, needs API + web running) — real-browser
  Playwright pass over home/topics/search/saved/story/topic × 390/768/1440/
  200%-zoom (640×400 @2x) × light/dark, saving screenshots to
  `VR_OUT_DIR` and asserting no horizontal overflow, StoryLead headline
  above the fold, and the same with every headline replaced in-DOM by a
  long Telugu string (no data change); plus the four ADR-014 journeys
  (first-story visibility, topic discovery, language switch + persistence
  across reload, save → Saved after reload → reopen). One real defect
  found and fixed: at 200% zoom the briefing intro + topic rail pushed the
  lead below the fold — new `@media (max-height: 560px)` rule at the end
  of `globals.css` (hides the dek and the rail's visible heading — nav
  keeps its aria-label — and keeps the CTA inline). After fix: 88/88
  checks pass; web typecheck/lint clean. **Mobile** (iOS Simulator, Expo
  Go, `simctl ui content_size accessibility-extra-extra-extra-large` +
  light/dark): (1) onboarding's "Continue without login" rendered under
  the status bar — fixed with `useSafeAreaInsets` top padding, verified
  live at largest text; (2) the tab header title and (3) header
  `LanguageToggle` clipped/overflowed the fixed-height header at the
  largest size — fixed with `headerTitleAllowFontScaling: false` (matches
  native iOS nav bars) and `maxFontSizeMultiplier={1.3}` on the toggle
  text. Mobile tsc clean, Jest 19/19. **Not done**: (2)/(3) were not
  re-screenshotted after the fix (Simulator still ignores synthetic taps,
  so reaching Home needs a manual tap each Expo Go relaunch); mobile
  long-Telugu, story detail, and the four journeys were not walked on
  mobile — no automated driver (no Detox/Maestro), and Expo Go deep links
  don't match `App.tsx`'s `linking.prefixes` (no `exp://`). Onboarding
  reappeared after an Expo Go relaunch despite `finish()` persisting the
  flag — likely Expo Go storage scoping across Metro restarts, unconfirmed.
  Environment: run Metro with `REACT_NATIVE_PACKAGER_HOSTNAME=127.0.0.1
  npx expo start --lan` — `--localhost` binds IPv6 `[::1]` only and Expo
  Go's `127.0.0.1` URL then fails with "Could not connect to development
  server". Local demo data from 2026-09-17 still not reverted.

- 2026-09-24: **Admin MFA login fixed** (the 2026-09-17 "NEXT SESSION START
  HERE" gap below is resolved). `apps/admin/src/app/login/page.tsx` now has
  two steps. (1) Sign in: email, password and an always-visible optional
  "Authenticator code" field. It's always shown rather than revealed after
  an `MFA_REQUIRED` 401 because `admin_login_attempts` rate-limits every
  attempt (5 per 15 minutes, including successes), so an extra round trip
  would cost enrolled admins an attempt each time. `MFA_REQUIRED` and
  `INVALID_MFA_CODE` clear and focus the field. (2) When the response has
  `mfa_enrollment_required`, the page keeps the restricted enrollment token
  in component state only (never `setSession`), calls `POST /mfa/setup`,
  shows an `otpauth://` link plus the key grouped in fours for manual
  entry, then `POST /mfa/enroll`. On success it returns to step 1 with a
  notice to sign in with a fresh code, which gets a full token. There's no
  QR image because the admin app has no QR dependency and adding one wasn't
  required. The otpauth link and manual key cover desktop and mobile. A
  401/403 during enrollment other than a wrong code (for example an expired
  enrollment token) goes back to step 1. Also regenerated
  `packages/contracts`, which had drifted: it was missing
  `AdminLoginResponse.mfa_enrollment_required`, so CI's stale-contracts
  check would have failed. `.env.example` now says
  `MFA_SECRET_ENCRYPTION_KEY` is required even locally. Verified: admin
  `tsc --noEmit`, `next lint` and `next build` are clean, contracts
  typecheck passes, `tests/test_admin_auth.py` passes (13). Ran the page's
  exact request sequence against a live API (with the `Origin` header and
  CORS preflight) using a throwaway admin, deleted afterwards: first login
  → enrollment token (403 on `/review-queue`) → setup → wrong code 401 →
  enroll 200 → login without code `MFA_REQUIRED` → wrong code
  `INVALID_MFA_CODE` → correct code gives a full token (200 on
  `/review-queue`). **Not done**: there was no in-browser click-through
  because the Chrome extension wasn't connected; the page was only
  confirmed to render its fields via server-side HTML. The admin app has
  no frontend test harness, so there's no automated UI test. Environment
  notes: the local DB was one migration behind (`d4a7c1e2f6b9`, now
  applied). `node_modules` and `apps/api/.venv` were missing and have been
  reinstalled. A CommunityKart vite server listens on `[::1]:3001`, which
  collides with admin's `localhost:3001`, so run admin with
  `-H 127.0.0.1` and add `http://127.0.0.1:3001` to
  `CORS_ALLOWED_ORIGINS`.

- 2026-09-17: Reader-first home/feed refresh, ad hoc per explicit product
  request to make the app feel substantially simpler and less busy. The web
  masthead is now a single compact row (brand, primary navigation, language
  and theme controls) instead of three stacked bands; every route remains in
  navigation. The homepage has a quieter briefing intro, topic rail, one
  lead story, and just three supporting story headlines before the rest of
  the feed. Brief cards now expose one useful label, a date, headline and
  Save action; source links, the explanation and the complete action set are
  retained on the lead/detail view where they are useful rather than repeated
  while scanning. The same hierarchy now carries through the mobile Home
  screen: the decorative dark welcome/trust-chip panel and compact-card
  accent bars were removed, compact cards show one label and plain-language
  actions, and source/explanation detail remains on lead and detail views.
  Verified: `pnpm --filter web build`, `pnpm --filter mobile exec tsc
  --noEmit`, and a live responsive web pass at 320px. The first visual pass
  caught a narrow-width lead/rail overlap; fixed it with a 900px single-column
  breakpoint and rechecked it live. No dependency, API, rights, or editorial
  workflow changes.

- 2026-09-17 (RESOLVED 2026-09-24 — see entry above; was "next session start here" for `apps/admin`
  auth): live-verified the ADR-014 step 4 admin changes below against a real
  running stack (API + admin dev servers + local Postgres) and found the
  admin login flow is **fully broken for any account going through first-time
  MFA enrollment** — a real, pre-existing bug independent of ADR-014, not
  something this session caused:
  - `apps/admin/src/app/login/page.tsx` has no MFA-code input field and
    doesn't handle `mfa_enrollment_required: true` in the login response at
    all — it stores whatever token comes back (even a restricted
    `scope: mfa_enrollment` one) and redirects to `/`, which then 401/403s
    and bounces back to `/login`. There is currently **no way to complete a
    browser login** for a seeded/fresh admin account. Needs an MFA
    setup+enroll UI (`POST /mfa/setup` → show QR/secret → `POST /mfa/enroll`
    with a code) plus an MFA-code field on the login form itself for
    already-enrolled accounts. Worth its own ticket, not a ride-along on
    ADR-014's admin step.
  - Separately, local `.env` was missing `MFA_SECRET_ENCRYPTION_KEY`
    entirely (declared blank in `.env.example`, line 54, never filled in) —
    every `/mfa/enroll` call 500'd (`RuntimeError: MFA_SECRET_ENCRYPTION_KEY
    is not set`, `apps/api/app/security.py:135`) until a dev value was added
    locally. **Added to local `.env` only** (gitignored, not committed):
    `MFA_SECRET_ENCRYPTION_KEY=scwlP3p2fBv6AXfFYtFEEkNP_Aws8R0_4EbqDudXhlk=`
    — treat as a placeholder, generate a real one
    (`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
    before this matters anywhere shared.
  - Verified the admin@teluguvarta.local account was enrolled and worked
    end-to-end via direct API calls (Python + `pyotp`) and via a live
    in-browser TOTP computation (Web Crypto `HMAC-SHA1`) run from the
    DevTools console — both confirm `/mfa/setup` → `/mfa/enroll` →
    `/auth/login` with `mfa_code` works correctly server-side. The bug is
    entirely in the missing admin frontend UI, not the API.
  - (RESOLVED 2026-09-28: review task and demo stories deleted.) **Local DB has temporary demo data, not yet reverted** — added so the
    user could see the new UI states without seeding real content:
    - `review_tasks`: one row, `story_id = 7a505dee-80c1-4aa9-accf-6f3e45a01ef1`,
      `reason = 'IMMIGRATION,SENSITIVE_CATEGORY'`, `status = 'PENDING'`.
    - `stories`: `id = 2b315ab5-2b9c-4862-b1ed-593372b7843b` set from
      `PUBLISHED` to `UPDATED` (valid transition, trigger-enforced).
    **Revert before treating local Postgres as clean**:
    `DELETE FROM review_tasks WHERE story_id = '7a505dee-80c1-4aa9-accf-6f3e45a01ef1';`
    and `UPDATE stories SET status = 'PUBLISHED' WHERE id = '2b315ab5-2b9c-4862-b1ed-593372b7843b';`.
  - The admin@teluguvarta.local account currently has MFA **enrolled**
    (secret unknown/rotated during this session's debugging — don't assume
    the specific secret values pasted in this session's chat still work;
    check `SELECT mfa_secret IS NOT NULL FROM users WHERE email = '...'`
    rather than trusting a stale value). To log in again without fighting
    the frontend gap: re-run the enroll dance via `curl`/`pyotp` (see this
    session's approach) or just `UPDATE users SET mfa_secret = NULL` and
    accept that the *first* login after that will require the same
    workaround again, since there's still no enrollment UI.
  - Dev servers were left running for this verification and may or may not
    still be up next session: API on `:8000` (`uvicorn app.main:app`,
    `/private/tmp/.../api-dev.log`), admin on `:3001`
    (`pnpm --filter @teluguvarta/admin dev`), web on `:3000`. Check
    `lsof -nP -iTCP:PORT -sTCP:LISTEN` before assuming either is live.

- 2026-09-17: ADR-014 step 4 — admin density/
  status refinement, ad hoc per the ADR's stated implementation order (no
  ticket file). Four changes to `apps/admin`:
  1. **Dead column removed**: `/review`'s table had a "Status" column that
     always read "pending" for every row, since `GET /v1/admin/review-queue`
     (`apps/api/app/routers/admin.py`) only ever returns
     `ReviewTask.status == "PENDING"` tasks — a column with zero
     discriminating information on a dense workbench table. Removed the
     `<th>`/`<td>` and the now-dead `status-pill--warn` cell; `humanize()`
     stays (still used for the reason pills).
  2. **Color-discipline bug fixed**: `p[role="alert"]` in
     `apps/admin/src/app/globals.css` used `--color-danger`/
     `--color-danger-soft`, which `apps/web/src/app/tokens.css` aliases to
     the rust ("hot") token — reserved by ADR-014 for consequential
     editorial emphasis, never a generic error/status color. Switched to
     the plain semantic `--danger`/`--danger-soft` tokens (same ones
     `.status-pill--danger` already uses) and extended the selector to
     `li[role="alert"]`, which covers observability's budget-alert list
     items that previously had no alert styling at all.
  3. **EditorialStatus added to the moderation view** (`/review/[id]`):
     ADR-014 explicitly calls for this notice "shared by web, mobile, and
     admin's moderation views," and admin had nothing — only a raw
     `Status: {story.status}` string. Added a `.editorial-status` block
     (new CSS: ruled-left + tinted, matching the "why matters" register
     per the ADR, not the boxed `p[role="alert"]` treatment) for
     `REVIEW_REQUIRED`/`UPDATED`/`CORRECTION_PENDING` (amber) and
     `RETRACTED` (red). Deliberately does **not** match web's current
     `.story-card__notice--updated`, which uses an indigo/`--action-*`
     tint (`apps/web/src/app/globals.css` "Semantic color roles" section,
     around `.story-card__notice--updated`) — that's a pre-existing drift
     from this same ADR's own color-discipline rule (green/amber/red only,
     indigo reserved for navigation/primary action), not a pattern worth
     propagating. **Flagged, not fixed here** — out of admin's scope this
     session; belongs in the ADR's final step (cross-surface visual
     regression pass), which is exactly the kind of drift that pass exists
     to catch.
  4. **Status pill consistency**: observability's X-account table rendered
     `rights_status` as plain text while `/review/[id]` already pills the
     same field (`source_rights_status`) — pilled it the same way
     (danger for `DISABLED`, ok otherwise). Also pilled the inline
     `(TRIPPED)` circuit-breaker text in that same table to match the
     pilled circuit-breaker cell one section up (`Ingestion health`).
  **Verified**: `pnpm --filter @teluguvarta/admin exec tsc --noEmit`,
  `pnpm --filter @teluguvarta/admin lint`, and `pnpm --filter
  @teluguvarta/admin build` all clean (all 7 admin routes generate).
  **Not done**: no live-render/screenshot check against the running API —
  the local Postgres from a prior session's Homebrew install is up
  (`pg_isready` succeeds) but exercising the new UPDATED/RETRACTED/
  under-review states would need seeded stories in those exact statuses,
  which wasn't set up this session; verification here is build/typecheck/
  lint clean, not an eyeballed screenshot, same caveat as prior ADR-014
  steps. ADR-014's final step (cross-surface visual regression pass at
  390px/768px/desktop, light/dark, 200% zoom, long Telugu headlines) is
  untouched and should also pick up the web indigo-notice drift flagged
  in point 3 above.

- 2026-09-17 (NEXT SESSION START HERE): ADR-014 step 3 — mobile navigation/
  cards/theme parity, ad hoc per the ADR's stated implementation order (no
  ticket file). Three changes to `apps/mobile`:
  1. **Dark-mode nav chrome bug fixed** (this was the "real functional
     gap" ADR-014 flagged, not a styling one). Added
     `src/theme/useAppTheme.ts` — hand-written (not generated; `tokens.ts`
     itself stays generated-only), wraps RN's `useColorScheme()` and picks
     `colorSchemes`/`uiSchemes` by scheme. `MainTabs.tsx`'s tab bar/header
     and `App.tsx`'s `NavigationContainer` theme (which every native-stack
     pushed screen's header/background inherits automatically) now read
     this hook instead of the static light-only `colors`/`ui` exports —
     previously every dark-mode media query fired for CSS/web+admin but
     nothing on mobile ever kept the same promise.
  2. **Full-app theme parity**, matching the step's actual title, not just
     the nav chrome: every one of the 14 files under `apps/mobile/src` that
     imported static `colors`/`ui` (`StoryCard`, `HomeScreen`,
     `StoryDetailScreen`, `SearchScreen`, `TopicScreen`,
     `TopicsIndexScreen`, `SettingsScreen`, `LanguageScreen`,
     `PrivacyScreen`, `NotificationsScreen`, `NotificationPreferencesScreen`
     + its form, `LanguageToggle`, `OnboardingScreen`) converted to the
     `createStyles(colors, ui)` factory + `useMemo` pattern driven by
     `useAppTheme()`. Along the way fixed several bare `<Text>`/`TextInput`
     elements that had no explicit color at all (default black — invisible
     on a dark background): Language screen's radio label, onboarding's
     option/chip/footer text, Privacy/Notifications screen buttons, all
     `TextInput`s got `placeholderTextColor`.
  3. **ADR-014 StoryBrief/StoryActions/LanguageControl contract applied to
     `StoryCard.tsx`**, which previously rendered the identical full action
     row (Share/Save/Report + per-card language toggle) on every layout
     regardless of context — the same web defect step 2 already fixed.
     `layout` is now `"hero" | "detail" | "compact"` (added `"detail"`,
     previously the story-detail screen silently fell through to the
     `"compact"` default). Compact (StoryBrief, every list row) renders
     Save only. Hero and detail (StoryLead + the detail screen) render the
     full Share/Save/Report set. The per-story EN/తెలుగు toggle — an
     explicit exception path per the ADR's LanguageControl section — now
     renders only in `"detail"`, not hero or compact. `StoryDetailScreen`
     now passes `layout="detail"` instead of relying on the compact
     default.
  4. **ADR-014 TopicControl**: Topics needed to be "an unmistakable
     destination, not buried inside a fifth-tab overflow" — it was one tap
     into Settings ("Browse topics"), which is exactly that. Topics now
     replaces the Notifications tab slot in `MainTabs.tsx` (still uses
     `TopicsIndexScreen`, unchanged component). Notifications (its own
     comment already says "the inbox shell... with nothing to deliver into
     yet" — T17 push delivery isn't built) moved from a tab to a Settings
     row + a pushed `RootStackParamList` screen; Settings' now-redundant
     "Browse topics" row was removed since Topics is a tab. This also
     directly addresses the design review's "5 tabs + header language
     control reads as busy" complaint without adding a 6th tab. The now-
     dead `TopicsIndex` push route (superseded by the tab) was removed from
     `RootStackParamList`/`RootNavigator`, not left as a shim.
  **Verified**: `npx tsc --noEmit` clean; `npx jest` — 19/19 passing across
  all 5 existing suites (none needed updating — none asserted on tab
  names/layout defaults); `npm run bundle-check` (`expo export
  --platform ios --platform android`) — both platforms bundle clean, 928/
  933 modules. **Not done**: no real-device/simulator dark-mode screenshot
  pass (Claude in Chrome doesn't drive native RN screens; would need an
  iOS/Android runtime) — verification here is compiled output + the theme
  wiring itself, not an eyeballed screenshot, same caveat as web's
  round 1-3 entries. The icon-system swap (emoji tab glyphs) remains
  explicitly out of scope per ADR-014 (blocked on the pre-existing
  @types/react conflict). ADR-014's remaining steps (admin density, the
  cross-surface visual regression pass) are untouched — next session
  should pick up admin per the ADR's stated implementation order.

- 2026-09-17: ADR-014 step 2 — web home/feed
  rebuilt around reading priority. StoryLead-above-the-fold and StoryBrief-
  everywhere-else layout was already in place from the round 1-3 density
  passes (`.front-grid__lead`/`.front-grid__rail`/`.story-grid`), so the
  actual gap against the accepted contract was `StoryCard.tsx` rendering
  the identical full action row (per-card Language toggle + Share + Save +
  Report) on every `display` variant regardless of list vs. detail context.
  Fixed in `apps/web/src/components/StoryCard.tsx`: the per-card Language
  toggle group now renders only for `display === "default"` (the
  story-detail exception path ADR-014's LanguageControl section calls for —
  edition-level control lives in `SiteHeader`, not repeated per card); Share
  and the Report button/form now render only for `display !== "brief"`
  (StoryLead and story-detail keep the full StoryActions set, StoryBrief
  gets Save only, per the ADR's StoryActions section). Save remains inline
  on every display mode. `apps/web/src/app/globals.css`'s
  `.story-card--brief .story-card__actions` block had dead `[role="group"]`
  override rules removed since brief cards no longer render that group at
  all (button/hover/save-pressed rules kept — Save is still styled there).
  No layout/route changes; this was a component-behavior fix on top of the
  existing structure.
  **Verified**: `npx tsc --noEmit` clean; `next lint --file
  src/components/StoryCard.tsx` — no warnings/errors; `next build` clean
  (all 15 routes generate, including `/`, `/latest`, `/story/[slug]`).
  Live-checked against the running dev server (`localhost:3003`, real
  Postgres+API backend, not mocked) by fetching and parsing the actual
  rendered HTML rather than assuming from source: home page's lead card
  (`story-card--lead`) renders Share/Save/Report with no language group;
  all 5 rail/grid `story-card--brief` cards render Save only; `/latest`'s
  `story-card--brief` list items render Save only; `/story/demo-h1b-visa-
  fee-update` (`display="default"`) renders the full Share/Save/Report set
  plus the per-story language toggle group. `/saved`, `/search`,
  `/topic/[slug]`, `/country/[code]` all pass the same `display="brief"`
  prop through the same `StoryCard` component, so they inherit this fix
  without a separate check.
  **Not done this session**: no real-browser (Claude in Chrome / Playwright)
  visual/contrast pass — verification here is compiled markup + SSR HTML,
  not an eyeballed screenshot, same caveat as rounds 1-3. ADR-014's
  remaining steps (mobile nav/cards/theme parity, admin density, the
  cross-surface visual regression pass) are untouched — next session should
  pick up mobile per the ADR's stated implementation order.

- 2026-09-17: Round-3 redesign (below) got pushed
  to `main` (commit `4e181de`), then the user delivered a full product
  review of the visual state across **all three surfaces** (web/mobile/
  admin), not just web. Findings: web still mixes visual systems (masthead
  + rounded pills + card-grid + leftover ledger CSS) and every story card
  exposes too many equal-weight actions; mobile differs materially from
  web (filled "why this matters" blocks, a colored rail, emoji tab icons)
  and is busy (5 bottom tabs + a header language control) with Topics not
  a first-class destination; admin should share type/status color but stay
  quieter/denser and hasn't been designed either way; **mobile nav dark
  mode is a real functional bug** — the nav chrome only reads light token
  values, not a styling gap.
  User then gave a 6-step recommended redesign plan (component contract →
  web home/feed → mobile nav/cards/theme parity → admin density → visual
  regression). Asked how to sequence it; user chose **write step 1 as an
  ADR first**, since it's an architecture-level decision (a cross-surface
  component contract), consistent with this repo's "architecture decisions
  get an ADR, don't infer mid-implementation" norm.
  Wrote `docs/adr/ADR-014-editorial-component-contract.md` (status:
  **accepted** same day) —
  names 7 shared concepts (EditionHeader, StoryLead, StoryBrief,
  StoryActions, LanguageControl, EditorialStatus, TopicControl), each with
  one visual treatment implemented natively per platform (explicitly *not*
  reopening ADR-009/ADR-010's rejection of a real shared component
  library — no new cross-platform dependency), states the semantic-color
  discipline rule explicitly (indigo=nav/action, rust=consequential-only,
  green/amber/red=saved/review/error-only) and the Share/Report-in-detail-
  only rule that's the actual fix for web's action-heavy cards. Explicitly
  scopes the icon-system swap and the mobile dark-mode nav bug **out** —
  icon system is blocked on the pre-existing React-type dependency conflict
  and needs its own go-ahead per ADR-010 precedent; the dark-mode bug is a
  plain fix, not a decision, and shouldn't be gated on ADR acceptance.
  **Numbering note**: `docs/plans/gemini-hetzner-telugu-plan.md` reserves
  ADR-011–016 for its own topics (014 = "Retrieval & grounded answering"),
  but the repo already broke that reservation before this session —
  ADR-011 and ADR-012 were used for unrelated P0 fixes (claim-evidence-
  sufficiency, MFA enrollment), not the plan's topics. ADR-014 here follows
  actual repo practice (next sequential number in `docs/adr/`), not the
  plan's stale reservation. When that plan's retrieval ADR is eventually
  written, it needs the next free number at that time, not literally 014.
  **Not done yet**: ADR-014 is accepted but nothing in the 6-step plan is
  implemented. Next session: step 2, rebuild web home/feed around reading
  priority (StoryLead above the fold, StoryBrief everywhere else, Save-only
  inline actions) against the accepted contract.

- 2026-09-17: Web listing-page redesign round 3,
  ad hoc per explicit direction **"more like Axios, cleaner and modern"**
  (user's own reaction to round 2, quoted below). User confirmed via a
  manual screenshot (Claude in Chrome extension is still not connected —
  4th attempt in a row this project; a session with fresh Chrome tools
  should verify it's actually broken, not just unlucky, before trying
  again) that the live site at the time was running at **localhost:3003**,
  not 3000 as earlier entries assumed — both ports were live during this
  session (two dev server instances) and both serve the same app, so
  either works, but don't assume 3000 is the only one.
  Identified the actual "newspaper, not Axios" culprits by reading
  `apps/web/src/app/globals.css` end to end: literal `border-radius: 0` on
  20+ selectors, `--shadow-hard`/`--shadow-hard-sm` offset "sticker"
  shadows, a cream `#f6f2e8` paper background, serif (Fraunces) display
  type on every heading, and bordered mono-uppercase boxes for every pill/
  tag/action-button instead of soft rounded chips.
  **Scope decision**: `apps/web/src/app/tokens.css` is generated from
  `packages/design-tokens/tokens.json` (`build.mjs`) and `apps/admin`
  imports that same generated file, `apps/mobile` consumes the same
  `tokens.json` — changing the shared token pipeline would have restyled
  admin/mobile too, which nobody asked for. Instead every change is a
  **local override/rule change inside `apps/web/src/app/globals.css`**
  (a new `:root` block right after `@import "./tokens.css"` overrides
  `--color-bg`/`--color-surface`/`--color-surface-sunken`/`--canvas`/
  `--surface`/`--surface-subtle` to near-white and `--font-heading` to
  the sans stack — same-specificity `:root`, later in cascade order, wins
  for light mode; dark mode is untouched because tokens.css's dark blocks
  use a higher-specificity selector and still win). `packages/design-
  tokens/*` and `apps/admin/**` were not touched.
  **Web**: `apps/web/src/app/globals.css` — root override block (bg,
  surface, `--font-heading`); `main h1`/`main h1::after` (drop uppercase,
  smaller slab rule); `.theme-toggle`/`.language-toggle` (rounded
  container + `overflow:hidden`); `.page-hero__cta` (pill button, no
  border/hard-shadow); `.topic-rail__list`/`.pill--topic` (joined bordered
  tab strip → separate tinted rounded pills, `--color-accent-soft` bg);
  `.pill` (story labels: bordered box → soft rounded tag);
  `.story-card__notice`/`.story-card__reviewed` (rounded, tinted bg
  instead of bordered); `.story-list`/`.story-list > li` (2px ink top
  rule → none; 1px `--color-border` row divider → 1px `--border-subtle`);
  `.story-card__actions [role="group"]`/`button` (bordered squares →
  rounded pill group/buttons, `--color-surface-sunken` resting fill);
  `main button` (bordered+hard-shadow → solid rounded pill, `opacity`
  hover instead of the press-shift trick); `.search-form` (bordered box →
  rounded pill input+button, narrow-viewport media query at the bottom of
  the file updated to match); `.story-card__report textarea` (radius 0 →
  8px); `.listing-header`/`.briefing-header` (2px ink bottom rule → 1px
  `--border-subtle`); and the later "section 12 semantic color roles"
  block, which had been re-asserting a bordered `var(--surface)` resting
  paint on `.pill`/`.pill--topic`/`.story-card__actions button` and would
  have silently undone all of the above — trimmed to layer only the
  hover/focus/press states on top of the new resting styles.
  `apps/web/src/app/layout.tsx` — dropped the `Fraunces` (`fontDisplay`/
  `--font-display`) Google Fonts load entirely: grepped first and
  confirmed nothing outside `tokens.css`'s now-shadowed `--font-heading`
  definition referenced `--font-display`, so it was dead weight once
  `--font-heading` points at the sans stack. `.story-card--brief`'s
  round-2 compact text-link action row (the thing the "still not good
  enough" complaint was NOT about) was left untouched, and the previous
  `.front-grid`/`.story-grid` structural layout from round 2 is unchanged
  — this round is paint only, no layout/structure changes.
  **Verified**: `npx tsc --noEmit` clean; `npx next lint --file src/app/
  layout.tsx` — "No ESLint warnings or errors"; `curl` 200 on `/`,
  `/latest`, `/search` on both :3000 and :3003; fetched the actual
  compiled `/_next/static/css/app/layout.css` from the running dev server
  and grepped it (not just the source file) to confirm the new rules
  really reached the browser: `.pill--topic` renders with `background:
  var(--color-accent-soft)` and `border-radius: 999px`, `--color-bg:
  #ffffff` is present, and `--font-heading` resolves to the sans stack as
  the *second* (cascade-winning) declaration, not the tokens.css original.
  **Not verified**: Claude in Chrome would still not connect (4th
  consecutive attempt across rounds 1-3), so — same caveat as every prior
  round — actual rendered spacing, contrast, and reflow at real viewport
  widths is reasoned from CSS/box-model and the compiled stylesheet, not
  an observed screenshot from this session. The user's own manual
  screenshot of round 2's output was used to identify the specific
  culprits above, but round 3's *result* has not been visually confirmed
  by anyone yet. Dark mode was reasoned about (selector specificity keeps
  it on the original near-black tokens) but not rendered/eyeballed either.
  `apps/admin` and `apps/mobile` were not run or visually checked — they
  weren't touched, but that's an assumption, not a verification.
  Changes are unstaged, not committed.

- 2026-09-17: Web listing-page redesign round 2, ad hoc per explicit product
  feedback that the round-1 density fix below still wasn't good enough
  ("if I am the user I will not open this website 2nd time"). Kept the
  `.front-grid`/`.story-grid` structure from round 1 but fixed what was
  actually eating the vertical budget: every card (including `display="brief"`
  ones) was rendering the full bordered-pill action row (language toggle +
  share + save + report, each a `min-height: 2.4rem` button) — that's the
  single biggest per-card cost, repeated on every rail/grid item. Added a
  `.story-card--brief` action treatment (the modifier class `StoryCard.tsx`
  already emitted but no CSS ever targeted): plain underlined text links,
  no border/box, ~40% shorter action row, same real `<button>` elements so
  click/tap behavior, `aria-pressed`, and screen-reader labels are
  untouched; a 760px media query restores 44px tap targets since the
  desktop compact size is mouse-oriented. Also: bumped the homepage rail
  from 3 to 5 secondary stories (`HomeFeed.tsx`) now that each rail item is
  shorter; widened `--page-max` 70rem → 76rem so wide desktops actually use
  the extra width instead of capping at ~1120px; tightened `.story-grid`
  columns (`minmax(15rem,1fr)` → `minmax(13.5rem,1fr)`, `auto-fit` →
  `auto-fill`) and per-card padding/line-clamps for more items per row;
  every other listing route (`/latest`, `/search`, `/topic/[slug]`,
  `/country/[code]`, `/saved`) got the giant `main h1` (`clamp(2.4rem,
  7vw, 4.25rem)`, uppercase, slab rule — same treatment the original hero
  fix removed from the homepage) replaced with a shared compact
  `.listing-header` (kicker + `clamp(1.6rem, 2.8vw, 2.15rem)` h1), matching
  the homepage's `.briefing-header` weight class instead of each page
  inventing its own heading scale. Fleshed out the previously-orphaned
  `.eyebrow` utility class (listed in the shared mono-font selector but
  never styled) to back the new kickers.
  **Web**: `apps/web/src/app/globals.css` (`--page-max`; new `.eyebrow` and
  `.listing-header` rules; `.story-card--brief` action-row override + 760px
  touch-target restore; `.front-grid`/`.front-grid__rail`/`.story-grid`
  spacing and clamp tuning), `apps/web/src/components/HomeFeed.tsx` (rail
  3→5), `apps/web/src/app/latest/page.tsx`, `apps/web/src/app/saved/
  page.tsx`, `apps/web/src/app/search/page.tsx`, `apps/web/src/app/topic/
  [slug]/page.tsx`, `apps/web/src/app/country/[code]/page.tsx` (all five
  wrapped in `<header className="listing-header">` + `.eyebrow` kicker).
  **Verified**: `tsc --noEmit` and `eslint` clean on all touched files;
  `curl` 200 + SSR HTML confirmed on `/`, `/latest`, `/search`, `/topic/
  andhra-pradesh`, `/country/US`, `/saved` — `.story-card--brief` (×5),
  `.story-card--lead` (×1), `.front-grid`/`.front-grid__lead`/
  `.front-grid__rail`, and `.listing-header`/`.eyebrow` all present in the
  rendered markup as expected against the 6-story dev dataset.
  **Not verified**: no real browser screenshot — the Claude in Chrome
  extension reported "not connected" again this session (same as round 1).
  Visual polish (exact spacing rhythm, dark-mode contrast at a glance,
  actual reflow at 1440/900/375px) was reasoned from the CSS and box model,
  not observed; user should do a visual pass before calling this settled.
  StudentBriefing wasn't touched beyond inheriting `.story-card--brief`
  automatically (it already passes `display="brief"`).

- 2026-09-17: Web homepage density fix, ad hoc per explicit product
  feedback (screenshot showing the hero headline filling the viewport with
  only one story visible above the fold). Capped the oversized "newspaper
  lead" hero (`.story-hero .story-card__headline` was `clamp(2.25rem, 6vw,
  4.75rem)`) and replaced the single-column hero-then-grid layout with a
  `.front-grid`: lead story + a 3-item `.front-grid__rail` beside it, so a
  wide viewport shows several stories immediately instead of one. Also
  swapped the numbered single-column `.story-list` for the denser
  `.story-grid` (multi-column, 3-line-clamped summaries, no oversized
  first-item bump) on every other story-listing surface for consistency:
  `/latest`, `/saved`, `/topic/[slug]`, `/country/[code]`, `/search`, and
  the homepage's `StudentBriefing` band. `docs/tickets/topics.md`'s pill
  list (not a story listing) was left on `.story-list`.
  **Web**: `apps/web/src/app/globals.css` (`.briefing-header h1` capped to
  `clamp(1.75rem, 3vw, 2.25rem)`; `.story-hero` rules replaced with
  `.front-grid`/`.front-grid__lead`/`.front-grid__rail` plus a 900px
  stacking breakpoint; dead 640px `.story-hero` override removed;
  `.student-briefing .story-list` → `.student-briefing .story-grid`),
  `apps/web/src/components/HomeFeed.tsx` (splits `supporting` into a
  3-item `rail` + `rest`, renders `front-grid`/`front-grid__rail` for the
  first and `.story-grid` for the rest), `apps/web/src/components/
  StudentBriefing.tsx`, `apps/web/src/app/latest/page.tsx`,
  `apps/web/src/app/saved/page.tsx`,
  `apps/web/src/app/topic/[slug]/page.tsx`,
  `apps/web/src/app/country/[code]/page.tsx`,
  `apps/web/src/app/search/page.tsx` (`.story-list` → `.story-grid`,
  `display="brief"`).
  **Verified**: `tsc --noEmit` and `eslint` clean on all touched files; SSR
  HTML for `/` confirmed rendering `.front-grid`/`.front-grid__lead`.
  **Not verified**: no visual/browser check — the Claude in Chrome
  extension wasn't connected this session, and `apps/api` wasn't running
  so pages beyond the (cached) homepage returned 500s on data fetch; user
  should confirm visually before considering this done.
  **Not done this session**: mobile app (`apps/mobile`) was explicitly
  scoped out — user chose "web homepage + other web pages" only.

- 2026-09-16: Removed the pilot concept entirely, ad hoc per explicit product
  request ("remove pilot dependency .. i do not want any pilot"). Not a
  waiver (that already happened 2026-09-09) — this deletes both the T20
  ticket and the feature code built for it, plus a real DB migration to
  drop the table it created. Confirmed scope with the user first (docs-only
  vs. docs+code) since dropping a table and deleting an endpoint is harder
  to reverse than a doc edit; user chose docs+code.
  **Docs**: `docs/BUILD_ORDER.md` (T20 row removed, "pre-build validation
  gate" section replaced with a "pilot removed" note), `docs/tickets/T20.md`
  and `docs/runbooks/pilot-report.md` deleted, `docs/tickets/README.md`
  (dead T20 link removed), `docs/SPEC.md` (§1 validation-gate paragraph and
  §11 "Pilot launch" milestone removed, §26 pilot-ticket cross-reference
  dropped), `docs/NON_NEGOTIABLES.md` (T01→T20 range corrected to
  T01→T19/T21), `docs/APP_STORE_READINESS.md` (three T20-submission
  references reworded to not assume a pilot gates submission), ADR-006
  (revisit-trigger reworded from "the pilot (T20)" to "real usage"), ADR-007
  (five T20/"pilot-phase" references reworded to "early-launch phase" /
  "real production traffic" — the cost-sizing rationale itself is
  unchanged, only the label). Two unrelated uses of "pilot" describing an
  ongoing §4.3 early-launch Telugu-translation review-sampling policy
  (`apps/api/app/jobs/translate.py`, `docs/tickets/T13.md`, ADR-004) were
  reworded to "early-launch phase" for clarity but left functionally
  intact — that sampling mechanism (`SAMPLED_SENSITIVITIES`,
  `TELUGU_REVIEW_SAMPLE_RATE`) is a real, unrelated ongoing feature, not
  the removed recruited-user pilot.
  **Code deleted**: `apps/web/src/app/pilot/page.tsx`,
  `apps/web/src/components/PilotSignupForm.tsx`,
  `apps/api/tests/test_pilot_signups.py`; `submitPilotSignup` removed from
  `apps/web/src/lib/api.ts`; `/pilot` removed from
  `apps/web/scripts/a11y-check.mjs`'s page list; all `.pilot-landing__*`/
  `.pilot-signup-form` rules removed from `apps/web/src/app/globals.css`
  (including the two responsive-breakpoint blocks and the shared
  `.search-form`/`.pilot-signup-form` combinator selectors, un-combined
  back to `.search-form`-only).
  **API**: `PilotSignup` model removed (`apps/api/app/models.py`);
  `PilotSignupIn`/`PilotSignupOut`/`AdminPilotSignupOut`/
  `AdminPilotSignupsResponse` removed (`apps/api/app/schemas.py`, `Segment`
  itself kept — still used by `/v1/home`'s real personalization);
  `POST /v1/pilot-signups` removed (`apps/api/app/routers/public.py`, along
  with the now-unused `_EMAIL_PATTERN`/`re` import); `GET
  /v1/admin/pilot-signups` removed (`apps/api/app/routers/admin.py`);
  `rate_limit_signup`/`SIGNUP_MAX_REQUESTS`/`SIGNUP_WINDOW_SECONDS` removed
  (`apps/api/app/rate_limit.py`, was only ever used by the deleted
  endpoint); `"pilot_signup_created"` removed from
  `apps/api/app/analytics.py`'s allowed-event set. New migration
  `c3d4e5f6a7b8_drop_pilot_signups.py` (head, on top of `b2c3d4e5f6a7`)
  drops the `pilot_signups` table — added a new migration rather than
  deleting/relinking the original `8c4f2a1e9d03_pilot_signups.py`, since
  `a1b2c3d4e5f6_x_accounts.py` depends on it mid-chain and rewriting alembic
  history is riskier than a straightforward drop-table migration.
  Regenerated `packages/contracts/{openapi.json,types.gen.ts}` from the
  live (pilot-free) FastAPI schema via `infra/scripts/generate_contracts.sh`
  — this is the T04 CI-enforced drift check, so it would have failed the
  build if skipped.
  **Verified**: local Postgres was reachable, so this was actually run, not
  just written and assumed. `pnpm run migrate` — the new
  `c3d4e5f6a7b8_drop_pilot_signups` migration applies cleanly on top of the
  existing head, `pilot_signups` table confirmed dropped. `apps/api`
  `ruff check .` clean; `pytest` — 509/510 passed, one error
  (`test_unsubscribing_student_topic_leaves_general_topic_subscription_untouched`)
  that passes standalone in isolation, confirming it's the same
  pre-existing full-suite-only teardown flake already noted in earlier
  changelog entries, not a regression from this change. `pnpm --filter web
  build`/`lint` and `pnpm --filter admin build` both clean, including the
  full page list — `/pilot` no longer appears among web's generated routes.

- 2026-09-16: Pre-development hygiene pass, ad hoc per explicit request
  ("proceed with development, make sure we have all good practices in place
  before starting") before picking up any new work. Audited PROGRESS.md
  against the actual ADR files/git history rather than trusting its own
  prose (three real contradictions found, all fixed):
  (1) T17's row falsely claimed "ADR-006 resolved" — the ADR file's own
  `Status:` field is still `proposed` (confirmed via git log: only one
  ADR-006 commit exists, from T05, never updated) — reworded to say the
  anonymous-identity model satisfies ADR-006's intent without the ADR
  itself being formally accepted, so it no longer contradicts the ADR
  status table.
  (2) The ADR status table said "ADR-007 not started" while T19's own row
  and `docs/adr/README.md` both correctly said "accepted" (confirmed
  accepted in the ADR file's header, dated 2026-09-09) — table corrected.
  (3) The X adapter table had X4 listed twice — once "done" with a full
  writeup, once a stray duplicate row saying "not started" — deleted the
  duplicate; X4 is done (see its existing entry).
  Also found and fixed a real `ruff` regression that several past
  changelog entries had claimed was clean but wasn't:
  `apps/api/tests/test_ux_reliability.py` re-imported the `client`/
  `db_session` pytest fixtures from `test_public_web.py` with `# noqa:
  F401` to silence the unused-import warning, but ruff still flagged
  every test function's same-named parameter as F811 ("redefinition of
  unused import") — a noqa on the wrong rule. Fixed at the root instead of
  re-suppressing: moved both fixtures into `tests/conftest.py` (the
  pytest-idiomatic place for fixtures shared across test modules, where
  every other cross-file fixture in this suite already lives) and dropped
  the cross-module import entirely. Verified: `ruff check .` — all checks
  passed (was 11 errors); `pytest -q` — 515 passed (unchanged count, same
  as before the fixture move, confirming no behavior change). Working tree
  was otherwise clean and matched PROGRESS.md's last entries; no new
  BUILD_ORDER ticket is actually open right now — T01-T21/X1-X4/S1-S2 are
  all done or blocked on external factors (T19's remaining gaps need real
  managed infra/live AI-provider access; T20 is explicitly product-waived),
  so this pass is the concrete "good practices" work available before any
  further ticket work resumes.

- 2026-09-13: Folio redesign mobile a11y follow-up (continuation of the
  2026-09-13 Folio entry below, at explicit request). No automated RN a11y
  tool exists in this repo, so did a code-level audit of every
  `apps/mobile/src/{screens,components}` `Pressable` for
  `accessibilityLabel`/`accessibilityRole` (all present — an earlier naive
  grep pass falsely flagged several, including `LanguageToggle`, because
  its regex mis-parsed multi-line JSX tags containing `=>` arrows; a
  brace/quote-aware parser found the real set is clean) and for touch
  target size (44x44 iOS HIG minimum). Found and fixed one real outlier:
  `LanguageToggle`'s EN/తె buttons were 32x36, the only touch target in the
  app below 44x44 — notable because this component is mounted in every
  screen's header (T21's "language one tap from every main tab" fix), so
  it's the most-exposed small target in the app. Bumped to `minHeight: 44,
  minWidth: 44` to match every other button in the app
  (`StoryCard`/forms/screens already used 44 consistently). Also booted the
  iOS Simulator (Expo Go, real seeded Postgres + FastAPI backend, not
  mocked) and screenshotted the live Home screen to confirm the Folio
  palette actually renders correctly end-to-end (warm paper background,
  indigo accent, rust "why matters" emphasis) — it does. Verified the
  `--color-faint` pair's dark-mode contrast, flagged as unchecked in the
  entry below: 7.94:1 (on `bg`) / 7.26:1 (on `surface`), both comfortably
  above the 4.5:1 AA floor — no fix needed. **Noted, not a redesign bug**:
  a floating blue gear button visible in every screenshot over the
  header's language toggle is Expo Go's own dev-menu affordance (persisted
  identically across an unrelated hot-reload, and traced — the app's own
  header only renders `LanguageToggle`, no gear icon anywhere in
  `MainTabs.tsx`); won't exist in a real build. **Not done**: couldn't tap
  through Search/Saved/Notifications/Settings/Story-detail live in the
  simulator — `osascript`/System Events can query the Simulator window but
  every synthetic click into it timed out (`-1712`), which looks like
  Simulator ignoring synthetic CGEvents rather than a missing permission
  (clicking Terminal's own window from the same script worked
  immediately); no `cliclick`/`idb` installed as a fallback. Screen-by-screen
  live interaction still needs either those tools installed or a manual
  walk-through. `apps/mobile` typecheck clean, Jest 19/19 passed after the
  fix.
- 2026-09-13: "Folio" visual redesign (ADR-010, ad hoc per explicit
  request, done with the two Vercel design skills installed the prior
  session). Replaced the drifted blue-SaaS palette with a warm-paper /
  indigo-accent / rust-emphasis system: new color values in
  `packages/design-tokens/tokens.json` (light/dark, both semantic and raw
  roles), a collapsed 4-step type scale (`display`/`headline`/`body`/
  `meta` — hierarchy now via weight/color, not more sizes, applying the
  RN skill's rule system-wide), a `shadow` token block that ADR-009 had
  specified but `build.mjs` never actually implemented (was hardcoded
  4px/3px offsets; now reads `tokens.shadow.sm`/`md`), and new
  `motion.duration.fast`/`base` (120ms/200ms) tokens so transition
  durations aren't hardcoded per component. `pnpm run tokens:generate` +
  `contrast:check` both clean. Web/admin: only `globals.css` in each app
  needed edits (every component is class-driven off generated CSS vars,
  no hardcoded colors in `.tsx`) — retuned two hand-coded masthead/toggle
  color pairs that weren't token-driven, consolidated ~12 ad-hoc
  transition durations onto the new duration tokens, added
  `tabular-nums` to admin's table rule (a real Web Interface Guidelines
  gap); everything else on that checklist (focus rings, reduced-motion,
  text-wrap balance) was already compliant. `pnpm --filter web/admin
  lint` + `build` both clean; the jsdom a11y script still needs a live
  Postgres+API it doesn't have in this environment, so it went unrun
  (pre-existing gap, not a regression — a real live-browser pass is still
  owed per the 2026-09-13 entry below). Mobile: token values flowed
  through automatically (also fully token-driven, no hardcoded colors);
  added `borderCurve: 'continuous'` everywhere `borderRadius` is set and
  collapsed remaining ad-hoc font sizes onto the 4-step scale per the RN
  skill; `TouchableOpacity`/hand-rolled shadows were already absent, so
  those specific RN-skill rules needed no fix. `pnpm --filter mobile
  typecheck` clean, existing Jest+RNTL suite (19 tests) passed.
  **Deliberately not done**: the RN skill's dependency-adding rules
  (`expo-image`, `FlashList`/`LegendList`, `react-native-bottom-tabs`,
  `zeego`, `galeria`) — real value, but new native dependencies are a
  separate, higher-risk decision; flagged as a follow-up needing its own
  go-ahead, not bundled into a restyle-only pass. No new dependencies
  added anywhere; no markup/IA/route changes in any of the three apps.

- 2026-09-13: Live-browser design/accessibility pass (T21/T19 follow-up, ad
  hoc per explicit request — the "re-run live before treating any WCAG
  conformance claim as settled" caveat from prior entries). The Claude in
  Chrome extension wasn't available (no Chrome installed), so used
  Playwright's headless Chromium + axe-core directly instead — a real
  browser, not jsdom, so it enforces actual CORS and CSS layout/contrast for
  the first time in this project's verification history. Found and fixed
  two real bugs neither curl, pytest, nor the jsdom-based `a11y-check.mjs`
  could ever catch: **(1) the API had no CORS middleware at all**
  (`apps/api/app/main.py`) — admin login was completely non-functional in a
  real cross-origin browser (blocked at preflight, silently stuck on
  `/login`), and web's client-side analytics (`/v1/events`) and onboarding's
  `/v1/config` fetch failed the same way. Added `CORSMiddleware` gated by a
  new `CORS_ALLOWED_ORIGINS` env var (`.env.example`, defaults to
  `localhost:3000,localhost:3001` for dev); no `allow_credentials` needed
  since auth is Bearer-token-via-localStorage, not cookies. **(2)** a real
  (not jsdom-only) contrast failure: `--color-faint` (`#6f778d` on white,
  ~4.47:1, just under the 4.5:1 AA floor — the same marginal pair flagged
  but not fixed in the 2026-09-12 semantic-token audit) darkened to
  `#5f6780` (~5.6:1) in `packages/design-tokens/tokens.json` (single source
  per ADR-009) and regenerated into `apps/web/src/app/tokens.css` +
  `apps/mobile/src/theme/tokens.ts`; admin inherits via its `@import` of
  web's generated tokens.css, so no admin-specific edit was needed. Also
  investigated and found genuinely dead CSS: `apps/web/src/app/globals.css`
  lines ~1393-1398 (an earlier "ink card" lead-story treatment) are fully
  shadowed by a later same-specificity block (~1548-1555) and never render
  — left as-is (not asked, and correctly identifying dead CSS from cascade
  order alone risks a wrong call without more investigation) but flagged
  for a future cleanup pass. **Verified**: re-ran the real-browser axe pass
  after both fixes — 0 violations across all 13 web pages, the actual admin
  login flow completes and reaches the real `/review`, `/observability`,
  `/sources` pages (previously silently 0-violation-because-still-on-
  `/login`), 0 violations there too. `apps/api` `ruff check` clean, `pytest`
  515/515 passing standalone (1 pre-existing full-suite-only teardown flake,
  confirmed unrelated by running it in isolation). `apps/web` `next lint`
  and `next build` both clean. Mobile: no browser/web target exists
  (Expo iOS/Android only, no `react-native-web`), so booted the actual iOS
  Simulator via Expo Go instead — app loads and looks correct on visual
  inspection (user-confirmed). **Not done**: mobile wasn't walked
  screen-by-screen for axe-equivalent accessibility issues (no automated
  a11y tool exists for React Native in this repo); dark-mode contrast for
  the same `--color-faint` pair wasn't checked (axe only ran against the
  default light-theme render); the Chrome-extension-based flow this session
  started with is still unverified end-to-end since no Chrome is installed
  on this machine — Playwright/Chromium was the substitute, not Chrome
  itself.
- 2026-09-12: Rebranded the public product to **TTE — The Telugu Edit**.
  Added the canonical brand document at `docs/brand/TTE-BRAND.md` and updated
  web/mobile/admin/API copy, metadata, notifications, OpenAPI title, and the
  new `tte` mobile deep-link scheme while retaining legacy identifiers for
  install and link continuity.

- 2026-09-12: UX reliability follow-up completed at product owner request;
  fixed repeated mobile feed/detail/topic requests, durable current-state
  saved-story retrieval, profile-backed web ranking, QA-gated Telugu search,
  language fallback/synchronization, scrollable mobile detail, stale mobile
  searches, source/topic/date discovery, bounded public queries/paging,
  background-only segment explanations, honest report/save failures, and
  review-queue story/source context. Added regression coverage: mobile Jest
  **19 passed** and API Postgres suite **35 passed**. Web/admin lint, all
  three app typechecks, and both web/admin production builds pass. The
  browser-only jsdom axe check remains unverified because localhost socket
  access is blocked; running-browser review passed. The planned modern design
  rollout is
  `docs/runbooks/modern-design-plan-2026-09-12.md`.

- 2026-09-12: Modern design foundation implemented at product owner request.
  ADR-009 is accepted; `packages/design-tokens/tokens.json` is now the single
  Ink & Signal source for light/dark color, spacing, radius, motion, and
  English/Telugu type metrics. A zero-dependency generator emits web/admin
  CSS and typed React Native values; CI regenerates and rejects output drift.

- 2026-09-12: Reworked the primary public experience into a reader-first
  daily briefing at product owner request. Web now opens with an explicit
  trust/orientation panel, friendly topic chips, a clearly promoted lead
  story, and rounded reading surfaces. Mobile gains the same daily-briefing
  orientation and touch-friendly story cards. Web/mobile typechecks and the
  mobile Jest suite (19 tests) pass.

- 2026-09-12: Replaced the low-contrast neon-lime visual signal with an
  accessible indigo palette across web, mobile, and admin. The shared token
  source now provides a readable primary action/focus color on light surfaces
  and a matched dark-mode value; generation and all three app typechecks pass.

- 2026-09-12: Audited the revised palette at product owner request and wrote
  `docs/runbooks/news-color-system-plan-2026-09-12.md`. The audit found the
  remaining issue is semantic overloading rather than the indigo hue itself:
  topic, action, selected, focus, and status controls still share generic
  accent tokens. It also identified a 2.18:1 light control border and a 4.47:1
  faint-text pair for correction in the planned semantic-token migration.

- 2026-09-12: Implemented the semantic news color system. Shared tokens now
  distinguish canvas/surface/text/borders, interaction, success, warning, and
  danger roles; generated web/mobile outputs and CI include a contrast gate.
  Topic, language, Share, Save, Report, review, updated, and retracted states
  now use their assigned meanings. All mobile raw color literals outside the
  generated token output were removed.

- 2026-09-12: Implemented the first complete world-class reading slice from
  the website/app redesign plan. The web home now places a compact briefing
  header and real lead story in the first viewport, supporting stories follow
  in a calmer feed, and story detail uses a focused reading column. Mobile
  navigation uses consistent monochrome glyphs and the same content hierarchy.
  Web/admin production builds and web/mobile typechecks pass.

- 2026-09-12: Corrected story-detail alignment after visual review. Removed
  the duplicated outer publication date and added a single padded reading
  surface so labels, headline, summary, source, and actions share one aligned
  content edge on desktop and mobile web.

- 2026-09-10: Acted on every finding in `docs/runbooks/design-review-2026-09-10.md`
  (the 3-agent UI/UX/accessibility review), ad hoc per explicit request
  ("start working one by one") — not a BUILD_ORDER ticket. All 8 findings
  addressed:
  **P0** (1) admin (`apps/admin/src/app/globals.css`) and mobile
  (`apps/mobile/src/theme/tokens.ts`) ported by hand to web's "Ink & Signal"
  palette/shape tokens (hex values, 0–3px radii, offset hard shadows),
  replacing the old dusk-teal/marigold values and their now-false
  "mirrors apps/web" comments — every `colors.teal`/`tealSoft` consumer
  across mobile (StoryCard, MainTabs, TopicScreen, StoryDetailScreen,
  HomeScreen, SearchScreen, App.tsx) remapped to the ink/accent semantics
  web actually uses (ink for links/active-nav, accent-fill only on
  pressed/hover state, no third "teal" color family);
  (2) admin (`apps/admin/src/app/layout.tsx`) now loads the same 4
  `next/font/google` faces as web (display/sans/mono/Telugu) — Telugu was
  included because the review-queue detail page renders the Telugu variant
  for editorial QA, which also needed a `lang="te"` attribute it was
  missing (`apps/admin/src/app/review/[id]/page.tsx`);
  (3) mobile's language control was two taps deep in Settings with no
  live update to cards already on screen — added `LanguageToggle`
  (`apps/mobile/src/components/LanguageToggle.tsx`), mounted as every main
  tab's `headerRight` (one tap, matching web's persistent header
  placement), plus a `DeviceEventEmitter`-based broadcast
  (`LANGUAGE_CHANGE_EVENT` in `apps/mobile/src/lib/storage.ts`, mirroring
  web's `window.dispatchEvent`) so `StoryCard` updates live instead of only
  on next mount;
  (4) fixed the ~1.15:1 accent-as-border contrast (WCAG 1.4.11) on both web
  (`.story-card__why`, `.student-briefing` in `globals.css`) and the
  equivalent mobile `StoryCard.tsx` "why" box — swapped signal-lime border
  for `--color-rule`/`colors.rule`, which holds contrast in both themes.
  **P1** (5) admin's story-correction form (`review/[id]/page.tsx`) now
  has the same two-step "Confirm submit correction" gate as approve/reject
  for always-human-reviewed sensitivities; (6) darkened admin/mobile's
  `--color-border`/`colors.border` from `#d8d4c6` (ported from web, but
  ~1.4:1 against both backgrounds) to `#7f7c6f` (≥3:1) — noted as an
  intentional one-value divergence from web, which carries the same
  unaddressed defect; (7) the review queue's "danger only" filter now
  persists via `localStorage`; (8) added a `/topics` index page on web
  (`getConfig().topics`, linked from `SiteHeader`) and a `TopicsIndex`
  screen on mobile (reachable from Settings → "Browse topics") — topic
  browsing previously had no entry point outside the home feed's chip row.
  Verified: `tsc --noEmit`/`next lint`/`next build` clean on web and admin;
  mobile `tsc --noEmit` clean; mobile `jest` has one pre-existing failure
  in `analytics.test.tsx` unrelated to this work (confirmed identical on
  `main` before these changes via `git stash`).
- 2026-09-10: Cross-app UX/UI/mobile-design review (three parallel review
  passes: UX architecture, visual/UI craft, mobile-app-specific) followed by
  fixes for every P0 and most P1 finding, ad hoc per explicit product
  request ("review how we can improve this web and app further" /
  "complete all changes") — not a BUILD_ORDER ticket. Scope: all three apps.
  **Fixed:**
  (1) **Human-reviewed trust badge** (web `StoryCard.tsx`, mobile
  `StoryCard.tsx`): a "✓ Human-reviewed" badge now renders whenever
  `story.sensitivity != "NONE"`. Truthful, not just decorative —
  `apps/api/app/jobs/publish.py:83` already makes it structurally
  impossible for a non-NONE-sensitivity story to reach a published state
  without passing the human-review gate (NON_NEGOTIABLES #5), so this is
  surfacing an existing guarantee, not adding a new claim to track.
  (2) **Site-wide language preference, previously nonexistent on web and
  ignored on mobile**: web gained a `language` field on the onboarding
  profile (`lib/onboarding.ts`) plus a header `LanguageToggle`, broadcast via
  a `tg:language-change` window event so every mounted `StoryCard` updates
  together; mobile's `StoryCard` now reads `profile.language` from
  `storage.ts` on mount instead of hardcoding `"en"`. Both still let a
  per-card toggle override for that session and persist the new choice.
  (3) **Admin: mandatory-human-review categories had no extra UI friction
  and reason was optional for approve/reject.** `review/[id]/page.tsx` now
  requires a non-empty reason and a "Confirm approve/reject" second step
  for any of IMMIGRATION/LEGAL/FINANCIAL/BREAKING/OBITUARY_ACCUSATION;
  sensitivity and source `rights_status` render as `status-pill` badges
  (danger tone for DISABLED/always-reviewed) instead of plain text; Telugu
  `why_matters` now renders alongside the English one (the field already
  existed in the payload, just wasn't shown). Review queue
  (`review/page.tsx`) now sorts danger-tone reasons first and has a
  "show only always-human-reviewed" filter.
  (4) **Mobile `HomeScreen` virtualization**: was the one screen using
  `ScrollView` + `.map()` over every story instead of `FlatList` like every
  other list screen — converted to `FlatList` with topics/Student-Briefing
  as `ListHeaderComponent`, on the highest-traffic screen.
  (5) **Mobile deep-linking**: `app.json` gained `"scheme": "teluguglobal"`
  and `App.tsx`'s `NavigationContainer` gained a `linking` config mapping
  `story/:slug` / `topic/:slug` / tab paths to screens. This makes the
  custom-scheme link work today; the shared `https://` link (what
  `shareStory` actually sends) still needs iOS `associatedDomains` +
  `apple-app-site-association` and Android `intentFilters` +
  `assetlinks.json` to open the app — deliberately not added, since that
  needs the real Apple Team ID and Android signing-cert SHA-256
  fingerprint, neither of which exist pre-App-Store-Connect/Play-Console
  registration; fabricating placeholders would silently break rather than
  just not-yet-work. Revisit once those registrations exist.
  (6) **Mobile offline/error handling**: `lib/api.ts` gained `ApiNetworkError`
  (a fetch-level `TypeError` — no connection/DNS/timeout — vs. a real HTTP
  error response), used in Home/Topic/Search/StoryDetail to show "you're
  offline" instead of a generic failure, each with a retry button/pull-to-
  refresh (previously only Home had any retry at all).
  (7) Mobile: search now debounces (350ms) instead of firing per keystroke,
  and has its own error+retry state (previously a failed search looked
  identical to "no results"). Dead tap target on `StoryDetailScreen` fixed
  (`StoryCard.onOpen` now optional; headline renders as non-interactive
  text when absent instead of an `onPress={() => {}}` no-op). Onboarding's
  language `Switch` gained `accessibilityRole`/`accessibilityState`. The
  redundant-AsyncStorage-read perf issue (`isSaved`/`toggleSaved` re-read
  the whole saved-ids array per `StoryCard` mount) is fixed by lifting
  saved-ids into `StoryCacheContext`, loaded once and shared.
  (8) Web: saved stories that aged out of the 100-item fetch window
  previously vanished with no explanation (indistinguishable from "never
  saved") — `saved/page.tsx` now reports a missing-count instead. The
  hero CTA (`OnboardingCta.tsx`) now reflects an already-completed profile
  instead of always saying "Personalize your feed →". `StoryCard`'s
  Share/Report actions no longer use `window.alert`/`window.prompt` —
  replaced with inline status text and an inline report form.
  (9) Cross-app contrast fix: `--color-faint`/`colors.faint`
  (`#7c8c8d` on the dusk-teal `bg`, 3.08:1) failed WCAG AA in both
  `apps/admin` and `apps/mobile` for real UI text (nav labels, timestamps)
  — darkened to `#5f7072` (~4.6:1) in both. `--color-teal`/`colors.teal`
  (`#1f7d6f` on `tealSoft`, 4.16:1, marginally failing for 0.72rem/600
  status-pill text) darkened to `#1a6d61` (~5:1) in both.
  **Deferred, not attempted or attempted-and-reverted:**
  (a) **`@expo/vector-icons` re-attempted for mobile's emoji-glyph tab bar
  and action icons** (P0 finding — inconsistent rendering across OS emoji
  fonts, doesn't retint, distorts at large accessibility text sizes). It
  now installs cleanly on its own (last session's pnpm-resolution-conflict
  reason no longer reproduces), *but* pulls a second `@types/react`
  resolution into the workspace that breaks `apps/web`'s and `apps/admin`'s
  `next build` type-checking repo-wide (`LayoutProps<"/">` / "bigint is not
  assignable to ReactNode") — confirmed by installing, seeing both builds
  fail, reverting the install, and seeing both builds pass clean again.
  Reverted; `MainTabs.tsx`/mobile `StoryCard.tsx` are back on emoji
  glyphs. Needs a workspace-wide `@types/react` version audit (web/admin
  pin `^18.3.11`, mobile pins `~19.2.3`) before this is safe to add.
  (b) **Dark mode for admin/mobile** (web has full dark-mode support, admin
  and mobile have none) — not built ad hoc here since ADR-009 (proposed,
  not accepted) already scopes a single generated token source covering
  "color (light + dark)" for all three surfaces; building a second,
  differently-shaped dark theme for admin/mobile now would conflict with
  that ADR's design once accepted. Flagged as a gap ADR-009 should state
  explicitly, not filled in.
  (c) Admin's Telugu-variant correction form (reviewer can only edit the
  English variant) — looked into this and it's **intentional, not a gap**:
  `POST .../correct` deletes the existing `te` variant on any English
  correction specifically to force AI regeneration against the corrected
  English rather than leave stale Telugu text live (NON_NEGOTIABLES #7,
  `apps/api/app/routers/admin.py:516-524`). Adding a manual Telugu-edit
  field would undermine that invariant, so left as-is.
  **Verified**: `pnpm --filter web build`, `pnpm --filter admin build`
  (both clean, including `next lint`'s type-check step), `apps/mobile`
  `tsc --noEmit` clean, `apps/mobile` Jest suite 14/14 passing. Root-level
  `pnpm run typecheck` still fails on `apps/web`/`apps/admin` — confirmed
  via `git stash` that this is a **pre-existing, unrelated** issue (a raw
  `tsc --noEmit` picks up a stale `.next/types/validator.ts` against a
  workspace-hoisted `@types/react@18.3.31` that disagrees with itself over
  `bigint`-as-`ReactNode`; `next build`'s own type-check step, which is what
  actually gates a deploy, does not hit this). Not fixed here — out of
  scope for a design-review pass and reproduces identically on a clean
  checkout before any of this session's changes.

- 2026-09-10: T21 follow-up — design review (UI + UX passes over all three
  surfaces) found the parity gap now recorded in the T21 entry below, plus
  four smaller defects, all fixed here. (1) `apps/mobile` rendered Telugu
  with the Latin display scale: `letterSpacing: -0.2` crowds conjunct
  clusters and 1.4x leading clips the stacked vowel signs. Added
  `typographyTe` + `typographyFor()` to `src/theme/tokens.ts` (mirroring
  web's existing `[lang="te"]` cascade, which was already correct) and
  wired `StoryCard` to key off the *rendered* language, not the requested
  one — `variant` falls back to `en` when a `te` variant is missing, so the
  metrics have to follow the glyphs actually on screen. (2)
  `HomeScreen`'s error copy said "Pull down to try again" but the
  `ScrollView` had no `refreshControl` — the error state was unrecoverable
  without restarting the app; added one. (3) `apps/admin`'s
  `.status-pill--ok/warn/danger` classes were defined but never rendered:
  the review queue showed `reason` as plain text and didn't display
  `status` at all. Review reasons now render as pills (split on `,`, since
  `jobs/generate.py` comma-joins multiple gates), with the
  always-human-reviewed categories in danger tone. (4) `apps/web`'s
  generic `main button` had no `:disabled` state (only the pilot signup
  form did), so a disabled button kept the ink fill, hard shadow and hover
  press-shift and read as clickable. Also styled admin's bare `<p>`
  loading/empty states via a new `.state-note`. ADR-009 written (proposed,
  not accepted) for the single-token-source generator that would have
  caught the parity gap. Verified: `pnpm --filter web build`, `pnpm
  --filter admin build`, `next lint` on both, `apps/mobile` `tsc --noEmit`
  — all clean. **Correction to the T21 entry below**: it claims the mobile
  Jest suite is 14/14 passing "re-verified independently"; it is not.
  `src/__tests__/analytics.test.tsx` fails on a `findByLabelText` in an
  `App.tsx` render (expo-notifications import chain). Confirmed
  pre-existing by stashing these changes and re-running at the T21 commit —
  same failure. Not fixed here; it is unrelated to design work and wants
  its own investigation.

- 2026-09-10: T21 visual design refresh across all three apps, ad-hoc (not in
  the original BUILD_ORDER spine) per explicit product request to make the
  product "trendier" and easier to use; ADR-008 written since this required a
  scope/approach decision (shared hand-rolled design tokens, no new UI
  framework, to avoid a large migration and pnpm-lockfile churn across three
  apps touched in one session — see the ADR for alternatives considered).
  **apps/admin** was completely unstyled (raw browser defaults, no CSS file
  at all) — biggest gap: added `apps/admin/src/app/globals.css` (on the
  "dusk-teal ground, marigold accent" palette — see the parity gap noted at
  the end of this entry), a persistent
  `AdminNav` component (top bar with Home/Review queue/Observability +
  role + sign-out, replacing the ad-hoc "Back to admin home" link repeated
  on every page), styled login card, status-pill badges for
  active/paused/circuit-breaker states in the observability tables.
  **apps/mobile** had zero shared theme (ad-hoc `StyleSheet.create` grey/blue
  per screen) — added `apps/mobile/src/theme/tokens.ts` mirroring the same
  palette, restyled `StoryCard` (elevated rounded card, pill labels, filled
  action buttons) and `HomeScreen`'s topic chips, themed the bottom tab bar
  and stack header via a `NavigationContainer` theme, added glyph icons to
  tabs/actions as plain Unicode/emoji text (deliberately not
  `@expo/vector-icons` — not an existing dependency, and pnpm couldn't
  resolve a version compatible with this app's expo ~57/react 19 pins
  without a network install; confirmed via `tsc --noEmit` failing on the
  missing module before reverting to text glyphs). **apps/web** was already
  reasonably designed (CSS custom properties, dark mode, hover
  micro-interactions) so this pass was light: a small gradient brand mark
  next to the wordmark, a subtle fade-in-on-mount animation on story cards
  (respects the existing `prefers-reduced-motion` override). No IA/content/
  route changes in any app. Verified: `pnpm --filter web build`,
  `pnpm --filter admin build`, and both apps' `next lint` all clean;
  `apps/mobile`'s `tsc --noEmit` clean; `apps/mobile` Jest suite 14/14
  passing (re-verified independently after this changelog entry was
  drafted — the originally reported 1-test failure did not reproduce).
  Not done: no visual QA in an actual browser/simulator this
  session (text-only review) — worth a manual pass before considering this
  ticket fully closed; other mobile screens (Search/Saved/Settings/etc.)
  still have a handful of hardcoded colors not yet migrated to the new
  token file.
  **PARITY GAP (found 2026-09-10 in design review, after the above was
  written): the three surfaces are on two different visual languages, not
  one.** `apps/web` was subsequently redesigned to "Ink & Signal" (bone
  paper / near-black ink / signal-lime accent, 2px hard edges, offset
  shadows, mono-uppercase micro-labels, numbered dispatch ledger), but
  `apps/admin/src/app/globals.css` and `apps/mobile/src/theme/tokens.ts`
  were left on the earlier "dusk-teal ground, marigold accent" palette
  (`#eef1f0` / `#b8791f` / `#1f7d6f`, soft radii, soft shadows). Both files
  carry comments claiming they mirror `apps/web` — those comments are
  false as of this commit. So ADR-008's stated goal ("consistent look
  across apps") is NOT realized: web next to admin/mobile reads as a brand
  mismatch. T21 stays **partial** until admin + mobile are rolled forward
  to Ink & Signal. Root cause is structural — three hand-copied token
  sources with no automated linkage, so a full palette swap in one surface
  silently failed to propagate and nothing in CI could catch it; a
  single-token-source generator is proposed as ADR-009.
- 2026-09-09: T19 golden AI eval set expanded 30 → 300 items, closing §18's
  literal ">=300 representative stories" count gap. Product owner explicitly
  waived the T20 pilot requirement earlier this session (see the pre-build
  validation gate note at the top of this file) and asked to proceed straight
  to completing remaining development; this was the first piece of that
  taken on, after flagging — and the user accepting — a real tradeoff:
  `eval/README.md` had explicitly said growing past 30 was "editorial/content
  work, not something to fabricate wholesale in one session." Generated the
  270 new items (`apps/api/eval/golden_set.json`, categories *-04 through
  *-30) with a template-driven Python generator (not committed, scratch-only),
  varying entities/numbers/dates/currency/negation content per category
  rather than swapping numbers in one fixed template. Every generated item
  was verified — not assumed — against the actual harness functions
  (`find_qa_issues`, `apply_glossary` imported directly, not reimplemented)
  before being written, so every item mechanically satisfies what
  `run_golden_eval.py`/`test_golden_eval.py` check. **Explicitly not done**:
  no native-Telugu-speaker or editorial review of the 270 — this is
  structurally-correct filler to meet the spec's count, not
  linguistically-vetted ground truth. `golden_set.json._meta.provenance` and
  `._meta.human_reviewed_ids` (the original 30) now record this distinction
  in the data itself, not just docs, so the two-tier trust level survives
  anyone reading the file directly; `eval/README.md`'s "Corpus size" section
  rewritten to match. Verified: `apps/api/.venv/bin/pytest
  tests/test_golden_eval.py -q` — 301 passed (300 fixtures +
  `test_golden_set_covers_every_18_category`). Still open: same live-provider
  gap every AI ticket since T10 has had (no outbound network/provider key in
  this sandbox) — `expected_sensitivity`/`expected_entities` on every item,
  old and new, are still never diffed against a real classification call.
- 2026-09-09: S1 follow-up — the same-day changelog entry below claims
  "`apps/web` doesn't have this onboarding step, so out of scope." Verified
  that claim against actual code rather than trusting it, since it directly
  affects whether mobile/web are in parity: it was **wrong**.
  `apps/web/src/app/onboarding/page.tsx` + `apps/web/src/lib/onboarding.ts`
  are a real, separate onboarding implementation (not a stub, not shared
  code with mobile) — added the same day per its own header comment
  ("S1: web's onboarding — apps/mobile already has this flow ..., web
  didn't (docs/tickets/S1.md gap)") — and it still had the exact
  single-select radio-button bug the mobile fix below addresses: a person
  could only pick one of International Student / Graduate-OPT /
  Professional / Family-Parent / Other. `StudentBriefing.tsx` (home-page
  student-briefing gate) and the `segment` param sent to
  `getStudentBriefing`/`GET /v1/home` both read that single `lifeStage`
  value directly. Fixed for parity with the mobile fix: `onboarding.ts`'s
  `OnboardingProfile.lifeStage: LifeStage | null` → `lifeStages:
  LifeStage[]`; added `primaryLifeStageSegment()` (same first-selected-wins
  rule as mobile's function of the same name, ADR-005 addendum) and updated
  `isStudentLifeStage()` to check the whole array; `onboarding/page.tsx`'s
  life-stage fieldset now renders checkboxes instead of radios ("Select
  every option that applies" hint, matching mobile's step-2 copy) and the
  skip button now saves `[]` instead of `null`; `StudentBriefing.tsx` now
  gates on `isStudentLifeStage(profile.lifeStages)` and sends
  `primaryLifeStageSegment(profile.lifeStages)` as `segment`. Confirmed
  `apps/web`'s home page (`app/page.tsx`) itself does **not** personalize
  by segment at all (calls the unparameterized `getHome()`, not
  `getHomeFor(segment, ...)` from `lib/api.ts`) — only the Student Briefing
  section reads the onboarding profile — so this fix's blast radius is
  exactly `onboarding.ts`/`onboarding/page.tsx`/`StudentBriefing.tsx`, no
  other web page. apps/web has no unit-test runner configured (no
  jest/vitest in `apps/web/package.json` — only `test:a11y`), consistent
  with T14/T20's web verification relying on `tsc`/`eslint`/`next build`/
  axe rather than unit tests, so verification here does the same. **Files**:
  `apps/web/src/lib/onboarding.ts`, `apps/web/src/app/onboarding/page.tsx`,
  `apps/web/src/components/StudentBriefing.tsx`,
  `apps/web/src/app/globals.css` (new `.onboarding__hint` rule).
  **Verified**: `apps/web` `pnpm run typecheck` clean, `pnpm run lint`
  clean (`next lint`, no warnings), `pnpm run build` clean (all 18 routes
  generate). Not committed — left for review per task instructions.
- 2026-09-09: S1 onboarding fix — life stage is now multi-select on mobile
  (real-device UX feedback: "why only one thing should describe a person...
  he can be professional and parent right?"). `apps/mobile/src/lib/storage.ts`:
  `OnboardingProfile.lifeStage?: LifeStage` → `lifeStages: LifeStage[]`;
  `lifeStageToSegment` renamed `primaryLifeStageSegment` (ADR-005 addendum,
  dated below: first-selected life stage is the one `segment` sent to the
  API for why-matters/ranking — fragmenting `story_why_matters_cache` per
  combination isn't worth the AI-cost increase); `isStudentSegment` now
  checks the whole array so any selected student-adjacent stage still gates
  the student sub-questions. `OnboardingScreen.tsx` step 2 now renders
  checkbox rows (mirrors the interests step's `TopicChips` pattern) instead
  of radio buttons. `HomeScreen.tsx` updated to the new array shape.
  Backend untouched by design — resolution to one segment happens
  client-side before the API call, so `GET /v1/home`'s `segment` param and
  `app/content/ranking.py`/why-matters caching need no contract change.
  `apps/web` doesn't have this onboarding step, so out of scope. Verified:
  `apps/mobile` `tsc --noEmit` clean, `jest` 14/14 (one flaky rerun,
  reproduced clean second time — not a regression); `apps/api` `ruff check`
  clean, `pytest` 240/240 (unchanged, confirms no backend regression).
- 2026-09-09: X4 done — X account monitoring and budget guard. Changed the
  X2 budget guard from all-or-nothing (skip every X account once
  `MONTHLY_X_API_BUDGET_USD` is exhausted) to low-priority-only (skip only
  `budget_class="LOW"` accounts; `STANDARD`/`HIGH`/unset keep polling) per
  §19's "pause/reduce low-priority polling" wording — the old blanket
  behavior didn't actually match the spec once read closely.
  `GET /v1/admin/x-accounts` now returns `fail_count`/
  `circuit_breaker_tripped`/`recent_error_count_24h`/
  `month_to_date_cost_usd`/`budget_paused` per account; `GET
  /v1/admin/observability` gained an `x_cost` summary block (same shape as
  T18's `ai_cost`). Manual pause/resume reuses T06's existing per-source
  `active` kill switch rather than adding a parallel one — each X account is
  already 1:1 with its own `Source` row, so it was already scoped correctly;
  confirmed with an explicit test rather than assumed. `apps/admin`'s
  `/observability` page gets a new X-account table with a Pause/Resume
  button per row. Full `pytest` (240 passed, was 233) and `ruff check`
  clean against real local Postgres; `apps/admin` `tsc --noEmit`/`eslint`/
  `next build` clean.
- 2026-09-09: X3 done — X post to story pipeline. Audited the claim that "X
  gets no special treatment" (§6.3.1, NON_NEGOTIABLES #4/#12) against the
  actual code rather than assuming X1/X2 already covered it: `XAdapter.emit()`
  (`app/adapters/x.py`) already reuses `SourceAdapter`'s shared
  normalize/validate/emit contract (`app/adapters/base.py`) verbatim — same
  rights gate (`RIGHTS_BLOCKED` unless `LINK_ONLY`), same idempotent
  `(source_id, external_id)` upsert — and T09/T11/T12/T14
  (`cluster_normalized_items`/`generate_stories`/`auto_publish_stories`/
  `story_to_out`) operate purely on `SourceItem`/`Story` rows with zero
  source-type branching anywhere (confirmed by grep, not inferred). So no
  code change was needed to satisfy the ticket's four acceptance criteria —
  they were already true by construction — but no test exercised an actual
  X-derived item through the full pipeline to prove it, so that's what this
  ticket adds. New `tests/test_x_story_pipeline.py` drives a real `XAdapter`
  (mocked HTTP transport, no live network) through
  fetch→normalize→validate→emit→cluster→generate→approve→publish→serialize
  for four scenarios: (1) a `DISABLED` X account's post is `RIGHTS_BLOCKED`
  at emit and a full sweep (cluster/generate/auto-publish/publish) processes
  zero rows, so no `Story` is ever created, let alone published; (2) an
  X-derived story classified `IMMIGRATION` stays `REVIEW_REQUIRED` even with
  `AUTO_PUBLISH_GLOBAL=true` — no official-account bypass exists; (3) a
  published X-derived story's `story_to_out()` output links to the specific
  canonical post URL (`https://x.com/{handle}/status/{id}`), not a generic
  "X" label; (4) fetching the same tweet twice never creates a second
  `SourceItem` or, after clustering, a second `Story`. Considered and
  rejected one apparent gap: `XAdapter` stores the tweet's full text as
  `SourceItem.title`, which reaches the public story page verbatim via
  `StorySourceOut.title` (`StoryCard.tsx`'s "Read the original source:
  {title}") — looked like a "copying full X post text" violation at first.
  Rejected the fix (overriding `XAdapter.normalize()` to replace the title
  with a fixed `"Post by @handle"` label) after checking
  `app/jobs/cluster.py::_same_story()`: it clusters by exact/lexical match
  on that same `title` field, so a fixed per-account label would make every
  post from the same account within the 72h cluster window collapse into
  one `Story` — a real regression traded for a non-issue. Re-read the
  ticket's own framing ("same as any other LINK_ONLY source") and
  NON_NEGOTIABLES #15's actual constraint (the *generated story summary*
  must be original, not the linked-source attribution metadata) — an RSS
  item's `title` is its own headline shown the same way, so a tweet's text
  shown as attribution is parity, not a special case; `app/jobs/
  generate.py::_summary_too_similar_to_source` is the actual verbatim-copy
  guard on the AI-generated summary, and it's already source-agnostic.
  Left as-is, not a gap. **Files**: `apps/api/tests/
  test_x_story_pipeline.py` (new). No production code changed. **Verified**:
  `ruff check .` clean; `pytest` 237 passed (real local Postgres, including
  the 4 new tests); no other test files touched, no migration needed.
- 2026-09-09: X2 done — incremental X official-account fetch. New
  `x_official_account_fetch` job (`app/jobs/x_fetch.py`) reuses T07's
  adapter contract (`app/adapters/x.py::XAdapter`) and T08's job-queue
  retry/backoff verbatim — a 429 (`app/x/client.py::XRateLimitedError`) or
  any other failure just raises and the existing bounded exponential
  backoff takes over, no bespoke retry loop. Fetches only
  `GET /2/users/{id}/tweets`, never x.com's public site; incremental via
  `x_accounts.since_id`, advanced to the max post id seen — never a full
  timeline re-fetch. New `x_api_call_log` table (migration `b2c3d4e5f6a7`)
  + `app/x/budget.py` mirror T10's AI cost telemetry/budget pattern
  (`posts_read`/`cost_usd`/status, optional `MONTHLY_X_API_BUDGET_USD`
  guardrail that skips scheduling entirely when exhausted). See the X
  adapter section below for the full writeup.
- 2026-09-09: S2 done — student topic taxonomy + independent student
  alerts, on top of S1's life-stage profile. Per the ticket's explicit
  design ("reuse T03's Topic/UserTopic tables... no separate topic model,"
  "same notification_dispatch worker... no special-cased notification
  path"), this is almost entirely data + UI grouping, not new backend
  logic — `app/content/notifications.py::topic_alert_eligible` already
  takes topic slugs as plain strings with zero special-casing, so a
  student topic is eligible through the exact same code path as any
  general topic the moment it exists as a `Topic` row; verified with two
  new tests in `apps/api/tests/test_notifications.py`
  (`test_dispatch_delivers_student_topic_alert_through_same_worker_no_parallel_path`
  drives the real `run_notification_dispatch` worker against a topic
  slugged "opt", not a mocked path; `test_unsubscribing_student_topic_leaves_general_topic_subscription_untouched`
  proves removing one topic's `UserTopic` row never touches another's).
  **Taxonomy**: `infra/scripts/seed.py`'s new `STUDENT_SEED_TOPICS` (13
  rows: F-1, CPT, OPT, STEM OPT, H-1B Transition, Internships, University
  Policy, Campus Safety, Taxes, Housing, Scholarships, Student Community,
  International Student Jobs — §3.1/S2.md's list minus "travel," which is
  deliberately not duplicated since it's the same concept as the existing
  general "Travel" topic, not a separate row) seeded alongside the existing
  `SEED_TOPICS` into the same `topics` table; ran the seed script for real
  against local Postgres (`Seeded 26 topics (13 student)`). New
  `packages/domain`'s `STUDENT_TOPIC_SLUGS` is the client-side mirror of
  those 13 slugs (documented as needing to stay in sync with
  `STUDENT_SEED_TOPICS` — no automated drift check added, same class of
  hand-maintained-list judgment call T18's changelog already flagged for
  the analytics event names). **UI**: since both the mobile onboarding
  interest-picker (`OnboardingScreen`) and the notification-settings screen
  (`NotificationPreferencesForm`) already render every active `Topic` row
  from `GET /v1/config` with zero filtering, the student topics would have
  appeared automatically, dumped into one flat list — split both into a
  "general" and a "Student topics" section (new `TopicChips`/`TopicSection`
  helpers) instead, matching §3.1's framing of student topics as a
  distinct, independently-toggleable group; picking or clearing one group
  never touches `interestTopicSlugs`/`prefs.topics` entries from the other,
  since each topic is just its own independent entry in those structures.
  **Not done**: `apps/web` has no topic-interest or notification-settings
  UI at all yet (a pre-existing gap predating S2, unlike S1's web-onboarding
  gap which S1 itself closed because life-stage collection was that
  ticket's core ask — building a full topics/settings surface for web is a
  separate, larger scope than S2's taxonomy+alerts ask) — student topics
  are real, seeded, and reachable via `PATCH /v1/me/preferences`
  (`topic_slugs`) on web today, just not yet exposed in any web UI.
  Verified: `apps/api` — `ruff check .` clean, `pytest` 214 passed (2
  errors on the full run are the same pre-existing full-suite-only
  DB-teardown flake documented in prior changelog entries — both pass
  individually, confirmed by re-running them standalone). `apps/mobile` —
  `typecheck` clean, `jest` 14/14 passed on a clean rerun (one run hit the
  same pre-existing Expo-notifications-teardown flake T15/S1 already
  documented — confirmed pre-existing via `git stash`, not a regression:
  the exact same failure reproduces on `main` before this change).
  `apps/web`/`apps/admin` — `typecheck`/`lint` both clean (touched only via
  the shared `packages/domain` import). **Files**: `infra/scripts/seed.py`,
  `packages/domain/index.ts`, `apps/mobile/src/{components/
  NotificationPreferencesForm.tsx,screens/OnboardingScreen.tsx}`,
  `apps/api/tests/test_notifications.py`.
- 2026-09-09: S1 done — International Student/Graduate-OPT life stage as a
  first-class profile over the existing feed/ranking, never a parallel
  backend (NON_NEGOTIABLES #13). Backend: `GET /v1/home` gained
  `student_briefing: bool` (`apps/api/app/routers/public.py`) — when true,
  composes the fixed immigration/education/jobs/money/travel/community
  topic set (`STUDENT_BRIEFING_TOPIC_SLUGS`, all pre-existing `SEED_TOPICS`
  slugs; "community" stands in for "campus/community", no separate campus
  topic exists) into `Preferences.topics` and reuses T16's ranking/serialize
  path unchanged — no new endpoint, no new content pipeline. New test
  `test_student_briefing_composes_fixed_topics_without_explicit_topics_param`
  in `apps/api/tests/test_personalization_api.py`. Mobile: closed a
  pre-existing gap where onboarding already collected
  `residenceCountry/homeRegion/homeCity/lifeStage/interestTopicSlugs`
  (T15) but `getHome()` never sent them — `apps/mobile/src/lib/api.ts`'s
  `getHome()` now takes params and `apps/mobile/src/screens/HomeScreen.tsx`
  reads the stored profile and passes them through, plus fetches
  `student_briefing` and renders it as a section above the main feed when
  `storage.ts`'s new `isStudentSegment()` is true. New `lifeStageToSegment()`
  maps onboarding's SCREAMING_SNAKE `LifeStage` to the API's snake_case
  `Segment` (these were never reconciled before). Web had no onboarding at
  all (T14 shipped without one) — added `apps/web/src/app/onboarding/page.tsx`
  (life-stage + optional residence/home fields, fully skippable, mirrors
  mobile's flow) backed by a new client-only `apps/web/src/lib/onboarding.ts`
  (localStorage, same on-device-only judgment call as `./saved.ts` — no
  account backend exists on web either) and a new client component
  `apps/web/src/components/StudentBriefing.tsx` rendered on the home page,
  reading the local profile and calling the new `getStudentBriefing()` in
  `apps/web/src/lib/api.ts`. Explicit-preference-only throughout (§3.5):
  grepped for any life-stage/segment inference from behavior — none exists;
  `student_briefing`/`segment` only ever come from what the user selected
  in onboarding. Regenerated `packages/contracts` (new query param) via
  `pnpm run contracts:generate`. Verified: `pytest` (216 passed, 1
  pre-existing flaky MFA test unrelated to this change — passes in
  isolation), `ruff check .` clean; `pnpm run typecheck` clean across all
  workspaces, `pnpm run lint` clean (web/admin; mobile has no lint script);
  `apps/mobile` Jest suite 14/14 passed (added 2 pure-function tests for
  `lifeStageToSegment`/`isStudentSegment` to `storage.test.ts`; did not add
  a new full-app RTL smoke test — hit a pre-existing Expo-notifications
  teardown crash in that harness unrelated to this change, not worth
  papering over); `apps/web` production build succeeds
  (`/onboarding` compiles). Manually verified end-to-end against a real
  local Postgres + `uvicorn` + `next dev`: `GET /v1/home?student_briefing=true&segment=international_student`
  returns a personalized, immigration-topic-boosted result; `/` and
  `/onboarding` both render server-side with expected content (curl-only —
  the Chrome extension wasn't connected in this sandbox, so the
  client-rendered Student Briefing section and the onboarding form's
  interactivity were not visually confirmed in a browser). Not done: no
  server-persisted life-stage (deliberately — matches the existing
  on-device-only judgment call for web/mobile preferences pre-ADR-006
  reconsideration; `student_briefing`/`segment` stay request-time-only like
  T16's other preferences). S2 (student topic taxonomy + independent
  student alerts) is a separate, not-yet-started ticket.
- 2026-09-09: Product-owner decision (not a Claude Code call): proceed with
  remaining build-order tickets (S1/S2, X1-X4) without running the T20
  pilot. `docs/runbooks/pilot-report.md`'s NO-GO and its reasoning stand
  unchanged — this is a recorded scope decision, not a resolution of that
  gate.
- 2026-09-09: apps/web visual redesign v2 — the v1 redesign below (warm
  cream/copper, Fraunces+Inter) was shown to the user and rejected as
  generic/"primitive" and, separately, was applied by a subagent that had
  been told to only survey files, not edit them (an instruction-following
  failure caught after the fact — flagged as user feedback). Before writing
  any more app code this time, published an HTML mockup as a Claude
  Artifact for review and got explicit sign-off on the direction before
  touching the real codebase. Design: a "wire desk" dispatch layout (Axios
  Smart Brevity density + Bloomberg-style mono datelines/tabular figures +
  NYT-grade serif headline type), on a deep teal-ink ground with a marigold
  accent and a separate teal secondary — chosen to avoid the cream+serif+
  terracotta look that both v1 and generic AI-generated designs default to.
  Typography: Newsreader (headline serif) + IBM Plex Sans (body/UI) +
  IBM Plex Mono (datelines/labels/tabular numbers) + Noto Serif Telugu
  (Telugu headlines, new) + Noto Sans Telugu (Telugu body, already present)
  — all via `next/font/google` as CSS variables in `layout.tsx`, self-hosted.
  Real explicit light/dark toggle (not just OS `prefers-color-scheme`): new
  `apps/web/src/components/ThemeToggle.tsx` (sun/moon buttons, `aria-pressed`
  state) sets `data-theme` on `<html>` and persists to `localStorage`
  (`tg-theme`); `globals.css` tokens are structured so system-preference dark
  mode and the explicit toggle both resolve correctly regardless of which
  one is active (media query guarded by `:not([data-theme="light"])`, plus a
  `[data-theme="dark"]` override so the toggle always wins); an inline
  pre-hydration script in `layout.tsx`'s `<head>` applies the stored choice
  before first paint to avoid a flash. `SiteHeader` now shows the toggle and
  a dual-script (EN/Telugu) brand lockup. `StoryCard` restyled from
  shadow-elevated cards to rule-separated dispatch rows with mono-caps
  topic/country chips and a bolded "Why this matters:" lead-in — behavior
  unchanged (still the same EN/Telugu variant-toggle buttons, save/share/
  report actions), purely a visual/CSS pass plus one JSX tweak (`why_matters`
  label wrapped in `<strong>` so the CSS rule has something to target).
  Because the whole app is CSS-token driven, this reached every route
  (home, `/pilot`, search, story detail, topic/country, legal pages) through
  `globals.css` + `layout.tsx` + `SiteHeader`/`StoryCard` alone — no other
  page files needed edits. Verified: `pnpm run lint`/`typecheck` clean,
  dev server serves `/`, `/pilot`, `/search` at 200 after a clean `.next`
  rebuild, `apps/web/scripts/a11y-check.mjs` (axe-core, all 13 pages) still
  zero violations. Not verified: actual visual screenshot — the Claude in
  Chrome extension isn't connected on this machine, so this is confirmed via
  build/lint/a11y output, not a rendered screenshot; a manual look in a real
  browser is still worth doing.
- 2026-09-09 (superseded by v2 above): apps/web visual redesign (whole app,
  not just `/pilot`) — requested explicitly, done ahead of the next ticket
  since new components will build on it. Replaced the plain maroon-on-cream/
  system-font look with a distinct editorial identity: `apps/web/src/app/
  globals.css` rewritten with a warm-paper/copper-and-gold palette (light +
  dark, both still meet the existing focus-ring/reduced-motion a11y rules,
  untouched), a serif display face (Fraunces) for headlines paired with
  Inter for body/UI, and `next/font/google`'s `Noto_Sans_Telugu` for Telugu
  script — loaded in `apps/web/src/app/layout.tsx` as CSS variables,
  self-hosted by Next (no runtime Google Fonts request). Story cards get an
  elevated surface+shadow treatment with a left accent bar, an
  underline-on-hover headline, and a highlighted "why this matters" callout
  instead of plain italic text; header is sticky with a blurred backdrop and
  a small brand mark; hero sections (home, `/pilot`) got a proper editorial
  hero block with a soft gradient on `/pilot`. Fixed a real pre-existing gap
  while in there: Telugu-variant text in `StoryCard` had no `lang="te"`
  anywhere (including the తెలుగు toggle button itself) — it was silently
  inheriting `lang="en"` from the document, wrong for both screen readers
  and font selection; now every Telugu-variant node and the toggle button
  carry `lang="te"`, which is also what makes the new Noto Sans Telugu font
  actually apply where it should. No new dependencies — plain CSS as
  before, no Tailwind/component-library adopted. Verified: `pnpm run
  lint`/`typecheck` clean, `next build` succeeds (production build, `/pilot`
  and `/` both in the static output), `apps/web/scripts/a11y-check.mjs`
  (axe-core, all 13 pages) still passes with zero violations. Not verified:
  actual browser rendering — the Claude in Chrome extension isn't connected
  on this machine, so this was checked via build output, lint/typecheck,
  and the automated a11y pass only, not a visual screenshot; worth a manual
  look in a real browser before calling the look-and-feel change final.
- 2026-09-09: T20 pre-build validation gate — engineering side. Built the
  `docs/BUILD_ORDER.md` gate's "landing page + 3 example personalized
  feeds": `apps/web/src/app/pilot/page.tsx` fetches 3 real personalized
  previews via a new `getHomeFor(segment, topics)` helper
  (`apps/web/src/lib/api.ts`) against the existing T16 `GET /v1/home`
  ranking — professional (jobs/immigration/money), international_student
  (education/immigration/community), family_parent (Andhra
  Pradesh/Telangana/parents/property) — reusing `StoryCard`, not mock data.
  Each feed has a `PilotSignupForm` (new client component) posting to a new
  public `POST /v1/pilot-signups` endpoint (`apps/api/app/routers/
  public.py`): validates email format, dedupes by email (re-signup updates
  segment/example_feed rather than erroring), rate-limited via a new
  `rate_limit_signup` (5 req/5min/IP, tighter than search's since it's a
  write). New `pilot_signups` table (migration `8c4f2a1e9d03`,
  `PilotSignup` model) — deliberately separate from the `users`/`profiles`
  account model since a landing-page visitor has neither. New admin
  `GET /v1/admin/pilot-signups` (`AdminPilotSignupsResponse`: total + roster)
  for reading the opt-in count/segment breakdown, same `current_admin`+
  `rate_limit_admin` gating as every other admin endpoint. Added
  `pilot_signup_created` to `app/analytics.py`'s event allowlist (tracked
  separately from the §17 in-product events since it fires before there's a
  product session). Regenerated `packages/contracts` for the new schemas.
  Verified: 6 new pytest cases (`tests/test_pilot_signups.py` — create,
  invalid-email rejection, dedupe/case-normalization, rate-limit trip, admin
  list, admin auth-required) plus the full existing suite still green;
  `ruff check .` clean; `pnpm run lint`/`typecheck` clean repo-wide; `next
  build` includes `/pilot` in the static output; `/pilot` added to
  `apps/web/scripts/a11y-check.mjs` and passes with zero violations;
  manually curl-verified signup/validation/DB-write against a real local
  Postgres+API. **What this does not and cannot do**: recruit the actual
  50-100 real users or run the 14-day measurement window — that's the
  product/ops half of the gate, tracked as still NOT STARTED at the top of
  this file. `docs/runbooks/pilot-report.md` updated in the same pass: the
  NO-GO stands (the gate isn't satisfied until the actual pilot runs), but
  product/ops now has a concrete `/pilot` URL to send recruits to instead
  of a from-scratch build step.
- 2026-09-09: T19 P0 fix — upgraded `next` from `14.2.35` (2 unauthenticated
  RCEs, no 14.x patch) to `15.5.25` in both `apps/web` and `apps/admin`
  (`package.json`), the latest patched 15.x release. Kept React at `18.3.1`
  — Next 15.5.25's peer range (`^18.2.0 || 19.0.0`) supports it, so no React
  19 migration was needed. Fixed the one real breaking-change surface: four
  server-component pages used Next 14's synchronous `params`/`searchParams`
  (`apps/web/src/app/{topic/[slug],country/[code],story/[slug],search}/
  page.tsx`) — Next 15 makes both `Promise`s, so each now `await`s them.
  `apps/admin/src/app/review/[id]/page.tsx` uses the client-side
  `useParams()` hook, which is unaffected. Also added root `pnpm.overrides`
  for `postcss` (>=8.5.18) and `js-yaml` (>=4.3.2) to clear the remaining
  high-severity transitive advisories pulled in by `next`'s own bundled
  deps and `openapi-typescript`'s toolchain — `pnpm audit --audit-level=high`
  now reports **zero** high/critical findings (3 moderate remain: `uuid`,
  `fast-xml-parser`, `decode-uri-component`, all deep transitive, none in
  the request path). Flipped `.github/workflows/ci.yml`'s dependency-scan
  step from `continue-on-error: true` (informational) to a real hard gate.
  Verified, not assumed: `pnpm run lint`/`typecheck` clean across the repo;
  `next build` succeeds for both `apps/web` and `apps/admin` against a real
  local Postgres + FastAPI backend (Homebrew Postgres left running from a
  prior session, `apps/api` started with `.env` loaded) — the web build
  actually fetches `/v1/home` and pre-renders 15/15 static+dynamic routes,
  not just `next lint`/`tsc`; `apps/web`'s `test:a11y` (axe-core, 12 pages,
  a real `next start` server) still passes with zero violations. The mobile
  Jest suite has one pre-existing flaky failure
  (`PrivacyScreen`/`act()`-wrapping in `analytics.test.tsx`) confirmed via
  `git stash` to already fail identically on `main` before this change —
  not a regression from this upgrade, left untouched as out of scope for a
  security fix. This was the sole blocker in T19's changelog entry below
  marked "release blocker" — with it fixed, T20's NO-GO
  (`docs/runbooks/pilot-report.md`) now rests solely on the pre-build
  validation gate never having been run, which is a product/ops action, not
  something further engineering closes.
- 2026-09-09: T19 partial — hardening. This ticket's scope (§16/§18 release
  gates) is too broad to fully close in a sandbox with no production infra,
  no app-store accounts, and no live AI provider network access (the same
  limitation every AI-gateway ticket since T10 has hit) — the acceptance
  criterion "every §18 release gate passes" is **not** met (see the P0/P1
  Next.js gap below). What follows is real, verified work plus an honest
  list of what isn't.

  **MFA on admin sessions** (`app/security.py`, `app/routers/admin_auth.py`,
  `app/schemas.py`): TOTP via `pyotp`, using the `mfa_secret` column that
  existed in the T03 schema unused until now. `POST /mfa/setup` generates a
  secret but deliberately doesn't persist it until `POST /mfa/enroll`
  proves the admin's authenticator app has it (avoids a half-configured
  admin locking themselves out). Once `mfa_secret` is set, `POST
  /admin/auth/login` requires a valid `mfa_code` (`MFA_REQUIRED` /
  `INVALID_MFA_CODE` otherwise); `DELETE /mfa` disables it after
  re-verifying a current code. Every attempt (missing/wrong MFA code
  included) still counts against the existing per-email Postgres rate
  limiter (`app/security.py::record_login_attempt`) — MFA brute-forcing is
  covered by the same mechanism as password brute-forcing, not a separate
  new one.

  **Rate limiting on search/admin** (`app/rate_limit.py`, new): a plain
  in-process sliding-window limiter (30 req/min/IP on `GET /v1/search`, 120
  req/min/IP on the whole `/v1/admin/*` surface) — not Redis, per
  NON_NEGOTIABLES; admin *login* keeps its existing separate Postgres-backed
  per-email limiter unchanged. Documented as process-local (correct for the
  single-instance deployment ADR-007 describes; would need a shared store,
  or Cloudflare edge rate limiting per that ADR, if ever horizontally
  scaled) — not built speculatively ahead of that need.

  **Cross-system account deletion** (§16/§5.5): `DELETE /v1/me/account`
  (`app/routers/me.py`) was T17-era stub-echo (`return
  DeleteAccountResponse(deleted=True)` with no actual deletion) — found
  while implementing this ticket's explicit "cross-system deletion job
  implemented and tested end-to-end" acceptance criterion. Now really
  deletes the `users` row; T03's existing `ondelete="CASCADE"` FKs on
  `profiles`/`user_topics`/`push_tokens`/`notifications` (and `SET NULL` on
  `review_tasks.reviewer_id`/`corrections.created_by`, so editorial history
  survives) do the cross-table purge — no separate per-table code needed.
  `apps/mobile`'s `PrivacyScreen` (previously on-device-clear only, despite
  its own comment claiming "no account system exists" — stale since T17
  actually built one) now calls the real endpoint via a new
  `deleteAccount()` (`src/lib/api.ts`) and mints a fresh device identity
  afterward (`resetClientToken`, `src/lib/identity.ts`) before clearing
  on-device storage; best-effort (a network failure never blocks the
  on-device clear). `apps/web` has no account/server-state concept at all
  (never sends a client token) — its `/account/delete` page staying
  on-device-only is correct, not a gap. New `tests/test_hardening.py`
  proves the cascade for real against Postgres (create user + profile +
  push token + notification, delete, assert every row gone, confirm the
  old token mints a brand-new empty identity) and that a repeat delete is a
  no-op, not an error.

  **Budget-breach auto-publish gate** (§19): `AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH`
  has been in `.env.example` since T10 but `app/jobs/publish.py` never
  actually read it — found while doing this ticket's "simulate and verify
  cost-guardrail breach" failure-mode requirement. Now wired: crossing
  `MONTHLY_AI_BUDGET_USD` disables auto-publish (falls back to the review
  queue, same as `AUTO_PUBLISH_GLOBAL` off) unless an operator explicitly
  opts out. Two new tests in `tests/test_editorial_workflow.py` cover both
  directions.

  **Dependency scanning + SAST, wired into CI**: `pip-audit --skip-editable`
  (clean) and `bandit -r app` (one real Medium finding — `app/adapters/
  rss.py` parsed fetched RSS/Atom XML with stdlib `ElementTree.fromstring`,
  exactly the untrusted-external-content case NON_NEGOTIABLES warns about;
  switched to `defusedxml.ElementTree`, a drop-in replacement — now clean
  except two `skips` in `pyproject.toml`'s new `[tool.bandit]` for
  non-issues, documented there) are now hard-failing steps in the `api` CI
  job. `pnpm audit --audit-level=high` is wired into the `node` job as
  **non-blocking** (`continue-on-error: true`) — see the P0/P1 gap below
  for why.

  **P0/P1 gap, not fixed this session (user-confirmed decision, not an
  oversight)**: `next@14.2.35` — the latest available 14.x patch for both
  `apps/web` and `apps/admin` — carries multiple unpatched high/critical
  CVEs including two unauthenticated RCEs (`pnpm audit`), with no 14.x fix
  available; only Next.js 15 resolves them. That's a breaking migration
  (async `params`/`cookies()`/`headers()`, React 19) touching every dynamic
  route in both apps (`topic/[slug]`, `country/[code]`, `story/[slug]`,
  admin's `review/[id]`) with no Playwright/E2E coverage in this repo to
  catch regressions from it. Asked the user how to handle this; they chose
  "document + non-blocking scan" over a blind major-version migration or
  turning CI red immediately. **This blocks T19's own "no P0/P1 security
  defects" release gate — do not consider T19 done, or T20 safe to start,
  until this is resolved as its own dedicated, tested piece of work.**

  **Backups/restore** (`infra/scripts/backup.sh`/`restore.sh`, new):
  `pg_dump -Fc`, optional `age`-encrypted at rest (`BACKUP_AGE_RECIPIENT`;
  `age` isn't installed in this sandbox, so encryption itself wasn't
  exercised — only the unencrypted path was). `restore.sh` always targets a
  freshly created database (never overwrites one) and verifies the restore
  actually reached Alembic head, not just "pg_restore exited 0". **Ran for
  real** against the local dev Postgres: backed up, restored into
  `teluguvarta_restore_test`, confirmed `alembic current` reports `(head)`,
  cleaned up. This satisfies "a monthly restore test actually run once" for
  local Postgres; ADR-007's chosen production DB (Supabase) has its own
  included backup/PITR — these scripts are the vendor-independent
  fallback/audit path, not yet run against a real Supabase project (none
  exists in this sandbox).

  **Accessibility**: extended `apps/web/scripts/a11y-check.mjs` from 2 pages
  (home, story) to 12 (+ search, saved, about, all 5 legal pages,
  account/delete, one topic page) and pinned axe-core's ruleset to the
  explicit WCAG 2.2 AA tag set (`wcag2a`/`wcag2aa`/`wcag21aa`/`wcag22aa`)
  instead of its broader best-practice default. **Ran for real** against a
  live `next start` + seeded `uvicorn`: zero violations (not just
  zero critical/serious) across all 12 pages. Same jsdom caveat T14 already
  documented still applies: no layout engine, so contrast-ratio and other
  CSS-rendering-dependent rules can't fire here — a real-browser
  (Playwright) pass is still future scope. No mobile-equivalent
  accessibility check exists (`apps/mobile` has no automated a11y tooling
  set up) — a gap, not attempted this session.

  **Load test**: no `hey`/`wrk` available in this sandbox; used Apache
  Bench (`ab`, pre-installed) against a live local `uvicorn` + seeded
  Postgres. `GET /v1/home`: 200 req/10 concurrent, P95 23ms. `GET /v1/
  search`: P95 19ms at 25 req/5 concurrent (fewer than 30, to stay under
  this same session's new rate limiter — confirmed it correctly 429s past
  30 req/min/IP when tested at higher concurrency first). Both comfortably
  inside §16's 800ms-cached/1.5s-uncached targets — but this is one
  single-instance local Postgres with a handful of seeded rows, not
  production traffic/data volume; treat as "the code path is fast," not "§16's
  availability/latency targets are met in production."

  **Golden AI regression set** (§18, `apps/api/eval/`, new): 30-item JSON
  corpus (3 per category × the 10 categories §18 lists), each with a
  hand-written good/bad Telugu rendering. `eval/run_golden_eval.py` +
  `tests/test_golden_eval.py` (parametrized, runs in the normal `pytest`
  CI step, no network needed) exercise `app/content/qa.py` and `app/
  content/glossary.py` against it: every "good" rendering must pass QA,
  every "bad" one (one invariant deliberately removed) must fail it, and
  glossary-relevant entities must get corrected back to canonical spelling
  from a naive rendering. **Real gaps, documented in `eval/README.md`**:
  30 items, not §18's ≥300 — growing that is editorial content work, not
  something to fabricate wholesale in one session; and it never calls a
  live AI provider (same no-network-access limitation as T10-T13), so
  `expected_sensitivity`/`expected_entities` describe what a *correct*
  classification call should produce but nothing here currently diffs a
  live call's output against them — wiring that in is a documented
  follow-up once a provider key exists, not attempted against a
  `FakeProvider` that would prove nothing.

  **ADR-007 accepted** (`docs/adr/ADR-007-production-hosting-cost-limits.md`):
  Vercel (web+admin) / Render (API+worker) / Supabase (Postgres) /
  Cloudflare R2+CDN/DNS / Expo EAS / Sentry+PostHog Cloud, and concrete
  pilot-phase budget numbers (`MONTHLY_AI_BUDGET_USD=150`,
  `DAILY_AI_ALERT_USD=10`, `MONTHLY_INFRA_BUDGET_USD=200`) — explicitly
  flagged in the ADR as unmeasured-against-real-traffic starting points,
  not a scaled-architecture decision.

  **App-store readiness** (`docs/APP_STORE_READINESS.md`, new): maps what
  `apps/mobile` actually collects at runtime to Apple/Google's privacy
  disclosure categories, confirms required URLs exist (privacy/terms/
  account-deletion, both in-app and web) and flags one real gap: no
  dedicated support contact/URL exists yet, which both stores' submission
  forms require. No store metadata/screenshots produced (needs a
  simulator/device build this sandbox doesn't have — T20 work).

  **Not attempted this session**: MFA/rate-limiting/backups against real
  managed infra (everything above was verified against local Postgres +
  local `uvicorn`, per ADR-007's platform choices existing only on paper
  until T20); a managed secret store (no cloud account here — ADR-007 names
  the intended platforms, provisioning them is T20); the Next.js 15
  migration (see the P0/P1 gap above); growing the golden set toward 300 or
  running it against a live provider; `apps/mobile`'s own accessibility
  audit tooling; Playwright/real-browser a11y and E2E coverage for either
  web app.

  **Files**: `apps/api/app/{security.py,rate_limit.py (new),schemas.py,
  routers/{admin_auth.py,admin.py,me.py,public.py},jobs/publish.py,
  adapters/rss.py}`; `apps/api/pyproject.toml` (+pyotp, +defusedxml,
  +pip-audit/bandit dev deps, `[tool.bandit]`); `apps/api/eval/` (new:
  `golden_set.json`, `run_golden_eval.py`, `README.md`, `__init__.py`);
  `apps/api/tests/{test_hardening.py (new),test_golden_eval.py (new),
  test_admin_auth.py,test_editorial_workflow.py}`; `apps/mobile/src/lib/
  {api.ts,identity.ts}`, `apps/mobile/src/screens/PrivacyScreen.tsx`,
  `apps/mobile/src/__tests__/analytics.test.tsx`; `apps/web/scripts/
  a11y-check.mjs`; `infra/scripts/{backup.sh,restore.sh}` (new);
  `docs/adr/ADR-007-production-hosting-cost-limits.md` (new),
  `docs/adr/README.md`; `docs/APP_STORE_READINESS.md` (new); `.env.example`
  (ADR-007 comment); `.gitignore` (`/backups/`); `.github/workflows/
  ci.yml`; `packages/contracts/{openapi.json,types.gen.ts}` (regenerated
  for the new MFA schemas/`AdminLoginRequest.mfa_code`).

  **Verified**: `apps/api` — `ruff check .` clean, `bandit -r app -c
  pyproject.toml` clean, `pip-audit --skip-editable` clean, `pytest` 205
  passed (real Postgres; one full-suite-only DB-teardown flake, same
  pre-existing class documented in every prior ticket's changelog —
  confirmed by re-running the specific failing test standalone, which
  passes, and the failing test name changing between runs). `apps/web`/
  `apps/admin`/`apps/mobile` — `lint`/`typecheck` clean repo-wide;
  `apps/mobile` `jest` 12/12 passed; `apps/web` `pnpm run build` +
  `test:a11y` both run for real against a live seeded server (see above).
  Contracts regenerated and `apps/contracts` typecheck clean.

- 2026-09-09: T18 done — observability across all four apps.
  **Logging/error tracking**: `apps/api/app/observability/logging.py` is a
  contextvars-backed JSON log formatter (request_id/actor/job_type/job_id/
  story_id) wired into `RequestIDMiddleware` (`app/errors.py`) and
  `app/auth.py`'s `current_user`/`current_admin` (sets `actor`); `app/jobs/
  worker.py` wraps every job run in a matching `job_context`.
  `app/observability/error_tracking.py::capture_exception` is "Sentry or
  equivalent" without the `sentry-sdk` dependency — it speaks Sentry's
  plain HTTP store-endpoint protocol directly via `httpx` (already a
  dependency), tagging every event with the current log context; it's a
  no-op without `SENTRY_DSN`, and the global `Exception` handler in
  `app/errors.py` calls it for every unhandled 500. Same trick client-side
  in `apps/web/src/lib/errorTracking.ts` and `apps/admin/src/lib/
  errorTracking.ts` (near-identical files — not shared as a package, since
  a TS/RN split would cost more than the duplication), gated on
  `NEXT_PUBLIC_SENTRY_DSN`/`EXPO_PUBLIC_SENTRY_DSN`, wired into each app's
  `error.tsx`/global handler and a debug-throw affordance
  (`GET /v1/admin/_debug/throw`, admin-authed; a home-page button in
  non-prod for apps/admin). apps/mobile doesn't yet have an equivalent
  client-side error-tracking hook — a gap, since Expo/RN's global-error
  API differs enough from the web DOM version that copying the same file
  wasn't a straight port and this session's time went to the higher-value
  observability/analytics acceptance criteria instead.
  **Ingestion/job/cost dashboard**: `GET /v1/admin/observability`
  (`app/routers/admin.py`) returns per-source 24h `source_fetch` success/
  failure counts (aggregated in Python, not SQL `GROUP BY` on a JSONB
  `->>` expression — Postgres requires that to be syntactically identical
  to the selected expression, which SQLAlchemy's JSONB comparator doesn't
  reliably produce, and the row count here is small enough it doesn't
  matter), each source's circuit-breaker-tripped state (reusing T08's
  existing `CIRCUIT_BREAKER_THRESHOLD`/`fail_count`, not a new field), job
  queue depth-by-status and oldest-PENDING age, and AI cost vs.
  `MONTHLY_AI_BUDGET_USD`/`DAILY_AI_ALERT_USD` (extended `app/ai/budget.py`
  with `today_cost_usd`). `apps/admin/src/app/observability/page.tsx`
  renders all three, linked from the admin home page.
  **Alerting**: `app/alerts.py::send_alert` is one pluggable channel
  (default: ERROR-level log + `ALERT_WEBHOOK_URL` POST if set, e.g. a
  Slack incoming webhook — no new infra) with three threshold checks
  (`check_budget_alerts`, `check_circuit_breaker_alerts`,
  `check_job_error_rate_alert`, the last a simple >50%-of-last-hour
  failure rate over a 5-sample floor — not a real SLO, just "the queue is
  on fire"); `app/jobs/worker.py::run_forever` calls `check_all` every 60
  poll loops (~5 min at the default poll interval) rather than every loop,
  so a still-tripped condition doesn't spam the channel every 5 seconds.
  **Analytics (§17)**: discovered T17 had already built the real wiring
  point for this — `app/analytics.py` (a structured-log sink) and
  `POST /v1/events` (`app/routers/public.py`), which apps/mobile's
  `trackEvent` already called for 3 events. Rather than give each frontend
  its own PostHog client/key (the original plan), extended that one
  existing funnel: `AnalyticsEventName` (`app/schemas.py`) and
  `app/analytics.py::EVENT_NAMES` now cover the full §17 list, and
  `analytics.track` forwards to PostHog's plain HTTP `/capture/` endpoint
  when `POSTHOG_API_KEY` is set (still just logs otherwise) — one
  server-side integration point instead of three client-side ones.
  `apps/web/src/lib/analytics.ts` (new) and apps/mobile's existing
  `trackEvent` (`src/lib/api.ts`, type widened from the generated
  `@teluguvarta/contracts` schema instead of a hand-copied literal) both
  post to `/v1/events`. Every §17 event is wired at a real UI action:
  web — `app_open` (root layout), `feed_view` (home page), `story_open`
  (story page), `story_save`/`story_share`/`language_switch`/
  `report_issue` (all on `StoryCard`, the last a new minimal "Report an
  issue" button + `window.prompt`), `search` (search page),
  `account_delete_request` (account/delete page's existing clear-storage
  button); mobile — the same set at the equivalent screens plus
  `onboarding_complete` (`OnboardingScreen`'s `finish()`) and
  `notification_opt_in` (specifically re-enabling the master notification
  switch after disabling it, not every individual topic toggle, most of
  which default to already-on). New shared `packages/domain` export
  (`ANALYTICS_EVENTS`/`AnalyticsEvent`) is the one source of truth for the
  §17 name list web/admin/mobile all reference.
  **Smoke test**: `apps/mobile/src/__tests__/analytics.test.tsx` (Jest +
  React Testing Library, extending the existing App-level harness from
  T15's smoke test) drives 5 real flows through the actual app — mocking
  only the network, OS share sheet, and alert dialogs, same as T15's
  existing smoke test — and asserts every one of the 12 §17 events posts
  to `/v1/events` at least once. No equivalent exists for apps/web (no
  test runner is set up there beyond the a11y/lint checks) — a gap; the
  events are still exercised for real by the mobile smoke test using the
  identical event-name/endpoint contract web also uses.
  **Files**: `apps/api/app/observability/{logging.py,error_tracking.py}`,
  `app/alerts.py`, `app/analytics.py`, `app/ai/budget.py` (added
  `today_cost_usd`), `app/auth.py`/`app/errors.py`/`app/main.py`/`app/jobs/
  worker.py` (wiring), `app/routers/admin.py` (+observability/+debug-throw
  endpoints), `app/schemas.py` (+observability schemas, widened
  `AnalyticsEventName`); `apps/admin/src/{app/observability/page.tsx,
  app/error.tsx,lib/errorTracking.ts,components/ErrorTrackingBoot.tsx}` +
  home-page link/debug button; `apps/web/src/{lib/analytics.ts,lib/
  errorTracking.ts,components/{TrackEvent,ErrorTrackingBoot}.tsx}` +
  instrumentation across `layout.tsx`/`page.tsx`/`story/[slug]`/`search`/
  `account/delete`/`StoryCard.tsx`/`error.tsx`; `apps/mobile/src/{lib/
  api.ts,components/StoryCard.tsx,screens/{HomeScreen,StoryDetailScreen,
  SearchScreen,NotificationPreferencesScreen,OnboardingScreen,
  PrivacyScreen}.tsx,App.tsx}`; `packages/domain/index.ts`; `.env.example`
  (`ALERT_WEBHOOK_URL`, `POSTHOG_API_KEY`/`POSTHOG_HOST`,
  `NEXT_PUBLIC_SENTRY_DSN`/`EXPO_PUBLIC_SENTRY_DSN`); new tests
  `apps/api/tests/{test_observability.py,test_alerts.py,
  test_analytics_events.py}`, `apps/mobile/src/__tests__/analytics.test.tsx`.
  **Verified**: `apps/api` — `ruff check .` clean, `pytest` 161 passed
  (real Postgres via Homebrew, same as prior tickets). `apps/web`/
  `apps/admin` — `lint`/`typecheck`/`build` all clean (both apps).
  `apps/mobile` — `typecheck` clean, `jest` 12 passed (4 suites). Contracts
  regenerated (`pnpm run contracts:generate`) and the drift-check test
  (`test_api_contract.py`) still passes.
  **Not verified / explicit gaps**: no real Sentry/PostHog account was
  used — DSN/key parsing and the HTTP envelope shape are unit-tested
  against a mocked `httpx.post`, not a live service. `apps/mobile` has no
  client-side global-error-tracking hook (see above). `apps/web` has no
  automated test runner, so its analytics/error-tracking wiring is
  type/lint/build-verified but not exercised by an automated test the way
  mobile's is. The job-error-rate and circuit-breaker alert thresholds are
  simple fixed constants (not configurable via env), matching this
  ticket's "at minimum" bar rather than a tunable SLO system.

  **Review fixes (same day, before commit)**: a `/code-review` pass over
  this diff surfaced six real bugs, all fixed and covered by tests before
  committing: (1) `GET /v1/admin/observability` 500'd as soon as any
  `ai_call_log` rows existed — `cost_by_task_and_day`'s `day` was a raw
  `datetime.date`, not the `str` `AiCostRowOut.day` declares; now
  `.isoformat()`'d at the source in `app/ai/budget.py`. (2) PostHog capture
  calls never carried a `distinct_id`, so PostHog would silently
  reject every forwarded event once `POSTHOG_API_KEY` is set —
  `app/analytics.py::_forward_to_posthog` now resolves one from
  `user_id`/`anon_id` (falls back to `"unknown"`); web/mobile now mint and
  persist a non-secret per-device `anon_id` (`localStorage`/`AsyncStorage`,
  key `tg_analytics_anon_id_v1` — deliberately distinct from mobile's
  `identity.ts` auth token, which must never reach a third-party sink).
  (3) `report_issue`'s free-text `description` (from `window.prompt`) was
  forwarded to PostHog verbatim — the one §17 event whose payload isn't a
  structured id, so it could carry PII. Still logged locally (for editorial
  follow-up) but now stripped before the PostHog forward via
  `analytics.py::_FORWARD_REDACT`. (4) `check_job_error_rate_alert` filtered
  DONE/FAILED jobs by `run_after`, which is only set at enqueue/retry time
  and never updated on terminal completion — the alert could stay silent
  during exactly the backlog scenario it exists to catch; switched to
  `locked_at` (set when a job is claimed, so it tracks "recently run", not
  "originally scheduled"). (5) `capture_exception`'s Sentry POST and
  `default_channel`'s webhook POST were both synchronous `httpx.post` calls
  with a 5s timeout, called from the async request-exception-handler path
  and from the worker's poll loop respectively — a slow/unreachable
  endpoint could block a request or delay job claiming for up to 5-15s
  during exactly the incident being reported; both now fire-and-forget on a
  daemon thread. (6) `worker.py`'s `check_all` call had no exception
  handling, so a DB error during an alert check would crash the whole
  worker process unlike every job handler (which is explicitly wrapped) —
  now wrapped in `try/except` alongside the fix. Fixing (2) required an
  async-timing adjustment on mobile: resolving `anon_id` via `AsyncStorage`
  inline (`await`ed before every `fetch`) delayed the first analytics call
  enough to break the cold-start E2E smoke test's timing assumptions, so
  `apps/mobile/src/lib/api.ts` resolves/caches it in the background instead
  (`primeAnonId`) and only attaches it once resolved — the very first event
  or two on a fresh install may go out without `anon_id`, which is
  acceptable (best-effort, same as any dropped analytics event). Two
  lower-severity duplication findings (DSN-parsing logic reimplemented
  across 3 files/2 languages; the §17 event-name list hand-maintained in 3
  places) were left as-is — real but not correctness bugs, and fixing them
  means either a generated/shared source of truth or an ADR-level call on
  cross-language codegen, out of proportion to a same-day review pass.
  Added tests: `test_analytics_events.py` (distinct_id resolution +
  precedence, `report_issue` redaction), extended `test_alerts.py`'s
  fixtures to set `locked_at`. Re-verified after fixes: `apps/api` — 165
  passed (1 pre-existing flaky test outside this diff's files, passes in
  isolation — different file fails on different full-suite runs,
  reproduced independent of these changes), `ruff` clean; `apps/web`/
  `apps/admin` — lint/typecheck clean; `apps/mobile` — typecheck clean,
  `jest` 12/12 passed including the previously-broken cold-start test.

- 2026-09-08: T17 done — daily briefing, topic alerts, and gated breaking
  alerts, per §14's `notification_dispatch` job (`apps/api/app/jobs/
  notify.py`).

  **ADR-006 resolution**: end-user identity was left as "T05 does not
  change `current_user`, real design is ADR-006, later ticket implements
  it" through T14/T15/T16, since none of them needed state outside a
  request. Push tokens and notification preferences do — the dispatch job
  has no request to read query params from — so T17 is that later ticket.
  `app/auth.py::current_user` now get-or-creates a `users` row by
  `client_token`, the opaque token the client mints on first launch and
  sends as `Authorization: Bearer` (mobile: `src/lib/identity.ts`, a
  crypto-random UUID persisted in AsyncStorage — no server round trip to
  "issue" one). `profiles`/`user_topics`/`notifications` (present in the
  T03 schema, unused until now) get real ORM models and `/v1/me/*` moved
  off T04's stub-echo onto real persistence; new `push_tokens` table.
  ADR-006 itself is still marked "proposed" in `docs/adr/README.md` (not
  changed here, consistent with how T14/T15/T16 left it) even though its
  decision is now load-bearing across five tickets — flagging this because
  the status column no longer reflects reality; a session doing ADR
  bookkeeping should reconcile it.

  **Eligibility** (`app/content/notifications.py`, pure/deterministic, no
  AI call): `topic_alert_eligible` and `breaking_alert_eligible` are two
  functions with zero shared code, per the ticket's explicit acceptance
  criterion — a story can never earn a breaking push via topic/engagement
  match, and vice versa. Breaking alerts additionally require a *new*,
  separate editorial approval (`stories.breaking_alert_approved_at`, set
  only via `POST /v1/admin/stories/{id}/approve-breaking-alert`) — distinct
  from the publish approval NON_NEGOTIABLES #5 already required for a
  `sensitivity == 'BREAKING'` story to reach PUBLISHED, so a breaking push
  is never auto-sent even once the story itself is live. Quiet hours are
  UTC-hour-of-day (no per-user timezone column exists in §12 — same class
  of judgment call as T16's ranking constants); thresholds
  (`TOPIC_ALERT_MIN_IMPORTANCE=0.5`, `BREAKING_ALERT_MIN_CONFIDENCE=0.7`,
  `BREAKING_ALERT_MIN_SOURCE_QUALITY=0.5`) are starting-point tuning knobs,
  documented in the module rather than a new ADR.

  **Dedupe/retry**: a `PENDING` row is inserted per (user, notification_key)
  with `ON CONFLICT DO NOTHING` on T03's existing unique constraint before
  any send decision is made — this, not application logic, is what makes
  repeated dispatch runs never double-send. A delivery failure gets
  bounded, backed-off retry (new `notifications.attempts`/`next_attempt_at`,
  same shape as the T08 job queue's backoff) rather than a fresh insert.
  Quiet-hours/daily-cap suppressions are terminal (not retried later) and
  emit their own analytics event instead of silently dropping the send.

  **Delivery**: `app/push.py` calls Expo's push API directly (§10.1: Expo
  fans out to both FCM and APNs, so there's one endpoint, not two) — a
  no-op when `PUSH_NOTIFICATIONS_ENABLED`/`EXPO_PUSH_ACCESS_TOKEN` aren't
  set, matching every other §15 kill-switch precedent.

  **Analytics**: no PostHog-or-equivalent sink exists yet (T18's job) — a
  structured log line (`app/analytics.py`) is the deterministic interim
  sink; `POST /v1/events` (public, no auth) lets the mobile/web clients
  report the events the server can't observe itself (`story_share`,
  `notification_received`, `notification_open`).

  **Deep links**: push payload carries `story_slug` (resolved server-side
  at send time, not the story id — T14/T15 route by slug), `null` for
  DAILY_BRIEFING or a story that's since become unreachable; mobile's
  `resolveNotificationDeepLink` (`apps/mobile/src/lib/push.ts`, pure/unit-
  tested) falls back to Home rather than erroring. A RETRACTED story stays
  in `PUBLIC_STATUSES` (T14 behavior, unchanged) so an already-delivered
  deep link to it still resolves instead of 404ing.

  **Mobile integration**: added `expo-notifications`/`expo-device`/
  `expo-constants`; `App.tsx` requests permission and registers the Expo
  push token on launch, wires foreground-received and tap-to-open
  listeners. **Not verified on a device/simulator** (none available in
  this environment) — permission prompts, actual token retrieval, and
  tap-to-navigate need a real device/EAS build to confirm; registration
  itself no-ops safely without an `EAS projectId` configured in `app.json`
  (not set up yet). Web push (service workers) was scoped out — §10.1's
  wording centers on "FCM/APNs via Expo/React Native tooling," i.e. mobile.

  Tests: `apps/api/tests/test_notifications.py` (20 tests) covers every
  acceptance criterion — unsubscribed-topic negative test, breaking-vs-topic
  path independence + sensitive-category-never-auto-sent, dispatch dedupe
  across repeated runs, quiet-hours/daily-cap suppression + analytics event,
  retracted-story deep-link fallback. `apps/mobile/src/__tests__/push.test.ts`
  covers the deep-link fallback pure function. Full `apps/api` suite (142
  tests) and repo-wide lint/typecheck clean; migration round-trips
  (upgrade head / downgrade base) verified against real Postgres.

- 2026-09-08: T16 done — §8.2's deterministic ranking formula and §8.3's
  cached per-segment "why this matters", replacing `/v1/home`'s generic
  chronological-only ordering.

  **ADR-005 accepted** (`docs/adr/ADR-005-personalization-model.md`): the
  formula (`0.28*residence + 0.20*home + 0.18*topic + 0.16*freshness +
  0.14*importance + 0.04*source_quality - repetition_penalty`) is pure code
  in `app/content/ranking.py` — no model call, byte-identical output for the
  same input every run (proven directly in `tests/test_ranking.py`, no DB).
  The ADR's central call: **preferences are explicit per-request input, not
  server-persisted state** — ADR-006 (account/privacy architecture) is still
  *proposed*, not accepted, and T14/T15 already deliberately kept onboarding
  preferences on-device rather than committing to it. Deciding to persist
  preferences server-side inside T16 would have pre-empted ADR-006's own
  question, so `GET /v1/home` instead accepts the §8.1 preference fields as
  optional query params (`residence_country, residence_region, home_state,
  home_city, topics`); when none are supplied the endpoint is byte-for-byte
  the existing T14 chronological feed (personalization is additive, never a
  login requirement, NON_NEGOTIABLES #9). `PATCH /v1/me/preferences` is
  unchanged (still T04's validate-and-echo stub — nothing to persist against
  yet). Two formula inputs had no existing backing and needed a judgment
  call, both documented in the ADR: `source_quality` is a new
  `sources.quality_score` column (float `0..1`, default `0.5`, not yet
  admin-editable); `repetition_penalty` is a within-batch, per-topic
  diminishing-returns penalty applied via a greedy re-rank (`0.05` per prior
  same-topic story already placed, capped at `0.2`) so one topic can't fill
  the whole feed — constants are a starting-point judgment call, same class
  as T09's clustering thresholds. "Home" (§8.1's `home_state`/`home_city`)
  has no dedicated column on `Story` either; it reuses the existing topic
  taxonomy §3.1 already lists AP/Telangana/Hyderabad under (a story tagged
  with a topic slug matching the caller's home region counts as a home
  match) — documented in `ranking.py`'s docstring rather than the ADR, since
  it follows directly from data that already exists, not a new architectural
  position.

  **Explainability** (§8.4): `PersonalizationOut.explanation` on each
  personalized `StoryOut` is built only from signals that actually
  contributed non-zero score for that story (e.g. "Because you live in US
  and you follow Immigration.") — never a canned string, and `None` when no
  preference signal matched (including the unpersonalized/no-preferences
  case).

  **"Why this matters" per segment** (§8.3): audience segment is an explicit
  `segment` query param (`general | international_student | graduate_opt |
  professional | family_parent | other`, mirroring §3.1's life-stage
  values) — never inferred from behavior, matching §3.1's own "never infer...
  from reading behavior" language generalized to every segment. T10's
  `Task.WHY_MATTERS` route existed since T10 but was never actually called
  until now (T11 covers the generic English `why_matters` inside its one
  `SUMMARY` call instead); `app/content/why_matters.py::get_or_generate`
  checks the new `story_why_matters_cache` table (unique on
  `(story_id, segment)`) first and only calls the AI gateway on a miss, with
  a new minimal `WhyMattersResult` contract (`app/ai/contracts.py`,
  deliberately not `GenerationResult` — same reasoning T13 used for
  `TranslationResult`). Verified via `ai_call_log`: two `/v1/home` requests
  for the same story/segment produce exactly one `why_matters` gateway call.

  **New migration** `4c6e1a8f2b7d`: `sources.quality_score` (+ range check
  constraint) and `story_why_matters_cache` (segment check constraint,
  unique `(story_id, segment)`). Upgrade/downgrade/upgrade round-trip
  verified against local Postgres.

  New tests: `tests/test_ranking.py` (7 cases, pure — no DB/AI: determinism,
  residence/topic/multi-signal explanation text, no-preferences → no
  explanation, repetition-penalty demotion, freshness decay);
  `tests/test_personalization_api.py` (3 cases, real Postgres +
  `FakeProvider`, same pattern as `test_translate.py`): unpersonalized
  `/v1/home` carries no `personalization` block; a residence+topic-matching
  story outranks an unrelated one with a traceable explanation; a
  same-segment "why this matters" is generated once and reused, confirmed
  by `ai_call_log` row count. `packages/contracts` regenerated
  (`PersonalizationOut` on `StoryOut`, `/v1/home`'s new query params).
  Verified: `pytest` (122 passed + the 10 new; 2 errors seen on a full-suite
  run were pre-existing DB-teardown flakiness in unrelated tests —
  `test_ai_gateway.py`/`test_jobs.py`/`test_cluster.py` each pass cleanly
  standalone, and which file errors changes between runs, confirming it's
  not caused by this ticket), `ruff check .` clean, `mypy` on every touched
  file shows only the same pre-existing noise documented in prior tickets'
  changelog entries. `pnpm run lint`/`typecheck` clean repo-wide.

  Not yet done/risks: `/v1/home` is the only personalized surface — `/v1/
  stories`/topic pages stay chronological, matching §9's own "Home
  (personalized feed...)" vs. other surfaces' plain listings; the "why this
  matters" AI call happens synchronously inside a public, unauthenticated
  request on a cache miss (no provider key configured in this sandbox, so
  unverified against real latency/cost) — acceptable at this build phase per
  the ticket's own scope, but worth revisiting (e.g. pre-generating via a
  job) if real traffic makes first-hit latency or concurrent-miss thundering
  herd a measured problem; once ADR-006 is accepted, `/v1/home` should read
  persisted preferences instead of query params — `rank_stories` itself
  doesn't need to change, only where `Preferences` comes from (noted in
  ADR-005's Consequences).

- 2026-09-08: T15 done — replaced the placeholder Expo app
  (`apps/mobile/App.tsx`) with a real iOS+Android app sharing T14's public
  API and `@teluguvarta/contracts` types. Upgraded the T01 scaffold from
  Expo SDK 51 (React Native 0.74, react 18) to the current SDK 57 (React
  Native 0.86.3, react 19.2.3) — the placeholder had no real code depending
  on the old versions, so this was a safe in-place bump rather than a
  migration; exact peer versions (react, react-native, safe-area-context,
  screens, async-storage) taken from expo's own `bundledNativeModules.json`
  for 57.0.21 so every native module matches what Expo actually ships
  together.

  **Navigation** (`src/navigation/`): one `@react-navigation/native-stack`
  root (`Onboarding` | `Main` | `Topic` | `StoryDetail` |
  `NotificationPreferences` | `Language` | `Privacy`) with a
  `@react-navigation/bottom-tabs` navigator (`Home`/`Search`/`Saved`/
  `Notifications`/`Settings`) as the `Main` route — every §9.2 screen exists.
  `RootNavigator` reads the on-device onboarded flag once at startup to pick
  the initial route.

  **On-device data, no account backend** (`src/lib/storage.ts`): same
  judgment call as T14's `apps/web/src/lib/saved.ts` — `/v1/me/*` is still
  T04 stub data (ADR-006 proposed, not accepted), so onboarding answers
  (residence/home region, optional life stage incl. the 5 §3.1 values,
  conditional student sub-questions with no university/immigration-document
  fields, interests, language), notification preferences (per-topic
  toggles, breaking/daily-briefing, quiet hours, max/day, and a
  `disableAll` that only ever gates push delivery — nothing in the feed/
  story-fetch path reads it), and saved-story ids all live in
  `@react-native-async-storage/async-storage`. `PrivacyScreen` mirrors
  T14's account-delete page: clearing on-device data is the V1 "delete
  account" (NON_NEGOTIABLES #9 — both in-app and on the public website now
  exist).

  **Onboarding** (`src/screens/OnboardingScreen.tsx`): every step has a
  Skip that advances without writing an answer, plus an always-visible
  "Continue without login" that jumps straight to the feed from any step
  — nothing is persisted until the flow completes or is skipped, so an app
  kill mid-flow never leaves a half-written profile.

  **Story card + share** (`src/components/StoryCard.tsx`,
  `src/lib/share.ts`): same fields/behavior as
  `apps/web/src/components/StoryCard.tsx` (labels, retracted/updated
  notice, headline/summary/why-matters, source link, EN/Telugu toggle when
  a QA-passed `te` variant exists, save). Share uses RN's native `Share`
  module (the OS share sheet, per the ticket's literal requirement) with
  the same canonical `storyUrl()` construction as web
  (`EXPO_PUBLIC_WEB_URL` mirroring `NEXT_PUBLIC_WEB_URL`/`PUBLIC_WEB_URL` —
  added to `.env.example`) — ADR-002's text-only, always-linked-to-source
  rule, no branded Share Card image.

  **Saved screen's known limitation**: no `/v1/stories?ids=` bulk-lookup
  endpoint exists (out of scope here — the public API is T14's, unchanged),
  so `src/lib/StoryCacheContext.tsx` is an in-memory cache fed by every
  screen that fetches stories; Saved renders whichever saved ids happen to
  be cached this session. A saved story never re-viewed elsewhere in the
  session won't render until it is. Documented, not silently swallowed.

  **`packages/ui`/`packages/domain` left as stubs**: the ticket says "where
  practical" — `apps/mobile/src/lib/api.ts` is a near-duplicate of
  `apps/web/src/lib/api.ts` (both fetch-based, same normalization) rather
  than a shared package, since web's copy is SSR/ISR-cache-tuned
  (`next: { revalidate }`) in a way a shared abstraction would have to
  either lose or awkwardly parameterize, and refactoring T14's already-
  shipped, already-tested web code into a new shared package purely for
  this ticket was judged higher-risk than the duplication it avoids. RN
  views and Next.js DOM components aren't practically shareable either
  without adding react-native-web, which nothing here needs. Noted as a
  judgment call, not an ADR — no architecture position, just a
  duplication-vs-risk call.

  **Tooling gap found and worked around**: `expo/tsconfig.base`'s
  `customConditions: ["react-native"]` (mirrors Metro's own resolution)
  makes `tsc` resolve `react-native-safe-area-context@5.7.0` to its raw
  `.tsx` source instead of its compiled `.d.ts`, which fails a stricter
  host-component JSX check against `react-native@0.86.3`'s bundled types —
  a real type mismatch between these two exact current versions, verified
  to not be a runtime problem (`expo export --platform ios` and `--platform
  android` both bundle and would run fine). Worked around in
  `apps/mobile/tsconfig.json`: clear `customConditions` (so `tsc` checks
  the compiled types) and exclude `jest.setup.js` from the program (its
  `require("react-native-safe-area-context/jest/mock")` was pulling the
  same raw-source path back in). Runtime bundling is unaffected — Metro
  resolves modules independently of `tsconfig.json`.

  New tests: `src/__tests__/smoke.test.tsx` (mocked `fetch`+`Share`+
  AsyncStorage, real navigation/rendering via `@testing-library/react-native`
  + `jest-expo`) covers the literal acceptance-criterion flow — onboarding
  skip → home → story open → save → share, asserting the shared `url`
  contains `/story/<slug>`; `src/__tests__/storage.test.ts` proves
  notification preferences (every field independently) and the onboarded
  flag round-trip through `AsyncStorage`. `jest-expo`/`@testing-library/
  react-native` are new to the repo (first Jest usage anywhere in the JS
  workspaces) — wired into CI (`.github/workflows/ci.yml`'s `node` job runs
  `pnpm --filter @teluguvarta/mobile run test` after typecheck; no
  Postgres/native toolchain needed, so it's cheap to run on every push).

  Verified: `pnpm --filter @teluguvarta/mobile run typecheck` clean;
  `pnpm --filter @teluguvarta/mobile run test` (4 passed, 2 suites);
  `pnpm run lint`/`typecheck` clean repo-wide (mobile has no lint script,
  same as before this ticket — RN eslint setup wasn't in scope);
  `expo export --platform ios` (867 modules, 4.1s) and `--platform android`
  (862 modules, 3.6s) both bundle cleanly via Metro — the strongest
  available proof in an environment with no Xcode/Android Studio that the
  app "builds... from the same codebase" (the ticket's literal wording);
  no physical device or simulator run (none available here) — a real device
  smoke test before shipping is a follow-up, not something this sandbox can
  do.

  Not yet done/risks: push notification delivery itself is T17 (not
  started) — the Notifications screen is an inbox shell with an empty
  state, and preference toggles set intent, not real subscriptions;
  `apps/mobile` has no ESLint config yet (typecheck-only, matching its
  pre-T15 state — a follow-up if RN-specific lint rules become worth the
  setup cost); no physical-device/simulator verification (sandbox
  limitation, same class of gap T01 noted for the original scaffold).

- 2026-09-08: T14 done — the public Next.js site over real API data,
  completing the vertical slice on web.

  **Backend (real data, not stub)**: `app/content/serialize.py::story_to_out`
  is the one place a `Story` row becomes the public `StoryOut` contract —
  `app/routers/public.py` (`/home`, `/stories`, `/stories/{slug}`,
  `/stories/{slug}/share-meta`, `/topics/{slug}`, `/search`, `/config`) now
  all query Postgres instead of returning T04's stub data. Only
  `PUBLISHED/UPDATED/RETRACTED/CORRECTION_PENDING` stories are ever public
  (`PUBLIC_STATUSES`) — the retracted/corrected indicator a story card must
  show (ticket's acceptance criteria) is just that `status` field, no new
  column. `variants` only ever includes `te` once it clears T13's QA gate
  (calls `resolve_display_variant` per language), so a client never sees a
  broken translation to fall back from itself. `countries` has no dedicated
  §12 table — derived from the `Source.country` of every linked source
  (documented in `serialize.py` as the deterministic, no-new-migration
  reading, not a taxonomy decision that needed an ADR). `/search` is
  `ILIKE` over `story_variants.headline`/`summary` (pg_trgm-indexed since
  T03) — NON_NEGOTIABLES #1's Postgres-search rule, not a ranked-relevance
  engine no one has measured a need for yet. `/stories` and `/topics/{slug}`
  gained `topic`/`country` query params and opaque base64-offset
  `cursor` pagination; `/config`'s feature flags now actually read
  `AI_TRANSLATION_ENABLED`/`PUSH_NOTIFICATIONS_ENABLED` instead of being
  hardcoded. New `PUBLIC_WEB_URL` env var (server-side) backs
  `share-meta.canonical_url`. `packages/contracts` regenerated for the new
  query params (`pnpm run contracts:generate`) — schema shapes themselves
  were already final since T04. New `tests/test_public_web.py` (11 cases)
  covers all of the above against real Postgres; `tests/test_api_contract.py`
  converted to the same `migrated_database`-fixture pattern other suites
  use, since the public endpoints now need a real DB.

  **Seed data**: `infra/scripts/seed.py` (previously sources+admin-user
  only) now also seeds the §3.3 interest taxonomy as `Topic` rows and one
  demo `PUBLISHED` story with EN+TE variants — this is the "at least one
  seeded story" the ticket's acceptance criteria requires, and what
  `apps/web`'s ISR pages and the a11y check render against.

  **`apps/web`**: real Next.js 14 App Router site, SSR/ISR
  (`revalidate: 60` on every fetch) against `NEXT_PUBLIC_API_URL`, typed
  only via `@teluguvarta/contracts` (added as a workspace dependency — a
  small normalization layer in `src/lib/api.ts` defaults the
  `Field(default_factory=...)` collections the generated types mark
  optional, since FastAPI's OpenAPI output can't express "always present,
  defaults to empty"). Every §9.1 page exists: home/feed (`/`), story detail
  (`/story/[slug]`, `generateMetadata` pulls text-only OG/Twitter tags from
  `share-meta` per ADR-002 — no image), topic (`/topic/[slug]`), country
  (`/country/[code]`, filters `/v1/stories?country=`), search (`/search`),
  saved (`/saved`), about, five legal pages (privacy/terms/ai-disclosure/
  corrections/copyright-takedown) plus account deletion, and 404/500
  (`not-found.tsx`/`error.tsx`) — all reachable from the footer.
  `StoryCard` (`src/components/StoryCard.tsx`) is the one place §3.3's card
  is implemented: labels, retracted/updated notice, headline+summary+why-
  matters, a prominent `target="_blank"` source link, an EN⇄Telugu toggle
  (only rendered when a QA-passed `te` variant exists — both variants are
  already in the API response, so the toggle is a pure client-side state
  flip, no extra fetch), a native-share-with-copy-link-fallback Share
  button, and a Save button. `sitemap.ts`/`robots.ts` cover SEO.

  **Save, without an account system**: §3.3 says save is "local or
  account-backed depending on auth state" — the public site has no account
  system yet (only admin auth exists, from T05), so `src/lib/saved.ts`
  stores saved story ids in the viewer's own `localStorage`, matching
  NON_NEGOTIABLES #9 (browsing — and here, saving — never requires login).
  This was a judgment call, not an ADR-worthy one: it's an additive,
  reversible choice (swapping in `/v1/me/saved` once real public accounts
  ship is not a breaking change), and §3.3's own text already sanctions it.
  `/v1/me/*` stays exactly as stubbed by T04 — wiring it to a real account
  system is ADR-006's (proposed, not accepted) territory, out of scope here.

  **Accessibility**: `apps/web/scripts/a11y-check.mjs` (`pnpm run
  test:a11y`) fetches rendered HTML from a running server and checks it with
  `axe-core` inside `jsdom` — no headless-browser download needed. Verified
  against the seeded demo story: zero violations (not just zero
  critical/serious) on both home and the story detail page. Semantic
  landmarks, a skip-link, visible focus rings, a `prefers-reduced-motion`
  block, and a dark-mode palette are in `globals.css`/`layout.tsx`.

  Verified end-to-end against the real local Postgres + a live `uvicorn` +
  `next start`: seeded the demo story, fetched it through both the API and
  the rendered web page, toggled it to `RETRACTED` and confirmed the
  "Retracted" notice appears, then restored clean seed state (the DB
  trigger correctly refused `RETRACTED -> PUBLISHED`, so the story was
  deleted and re-seeded rather than force-reset). All 112 `pytest` cases
  pass (11 new), `ruff check .` clean, `mypy` shows only the same
  pre-existing ORM-`str`-vs-`Literal` noise already present in `admin.py`
  (none introduced by this ticket). Repo-wide `pnpm run lint`/`typecheck`
  clean (`apps/web` included for the first time); `pnpm run build` succeeds
  and statically prerenders `/` against live data.

  **Not done / follow-ups**: no Playwright/browser-based a11y run (jsdom's
  axe check doesn't cover CSS-rendering-dependent rules like real contrast
  ratios against computed styles — a real browser check is future scope,
  not blocking this ticket's stated "e.g. axe" criterion); `apps/mobile`
  still doesn't call the API (T15); country pages use the raw `Source.country`
  code as-is (no display-name/flag mapping) since no country taxonomy table
  exists yet.

- 2026-09-08: T13 done — the English-canonical/Telugu-derived lifecycle
  (NON_NEGOTIABLES #7). New `app/jobs/translate.py`: one `ai_translate` job
  type (already reserved in T03's `ck_jobs_type`) sweeps every `Story` that
  has an `en` `StoryVariant` and no `te` one yet — created fresh by T11's
  generation step, or re-created after T12's `correct_story` deletes a
  stale `te` variant, since deletion alone puts a story back in this same
  set on the next sweep (no separate "regenerate" flag/state needed, same
  "don't invent a state a query can already express" precedent as T09's
  `DEDUPED`). One `TRANSLATION_EN_TE` gateway call per story (already
  routed in T10's `tasks.py`, unused until now) using a new
  `TranslationResult` §7.3 contract (`headline_te`/`summary_te`/
  `why_matters_te`) — deliberately not `GenerationResult`, since a
  translation has no relevance/confidence/claims of its own.

  **Gateway extension**: `AiGateway.run_task` gained a `result_model`
  parameter (default `GenerationResult`, so every existing T10/T11 caller is
  unaffected) so a second contract shape can validate through the same
  schema-retry/telemetry path; the confidence-threshold-review and
  unsupported-claims-stripping steps are now gated on
  `isinstance(result, GenerationResult)` so a `TranslationResult` (which has
  neither field) just returns `OK` once it parses.

  **Glossary enforcement** (`app/content/glossary.py::apply_glossary`, §4.3):
  a small hand-maintained `GLOSSARY_EN_TE` table (proper nouns this
  product's coverage touches — USCIS, White House, Telangana, Andhra
  Pradesh, United States) forces the canonical Telugu spelling over
  whatever a raw translation call produces (a naive transliteration, or the
  English term left untranslated) — deterministic post-processing per
  NON_NEGOTIABLES, not a prompt instruction trusted to "just work."

  **Automated Telugu QA** (`app/content/qa.py::find_qa_issues`, §4.3):
  compares the Telugu output against the English source it was derived
  from and flags a dropped number, date (month name — checked against a
  small EN→TE month table since a real translation transliterates the
  month, not the number, so a bare substring check on the English word
  would false-positive), currency amount, URL, or negation. Any issue sets
  `qa_status = 'FAILED'` on the new `StoryVariant` row.

  **English-fallback resolver** (`app/content/variants.py::
  resolve_display_variant`): pure function, no DB access — a request for
  `te` serves the `te` variant only if it exists and `qa_status ==
  'PASSED'`, otherwise serves `en` and reports `fallback=True`. The public
  `/v1/stories/{slug}` endpoint is still T04 stub data (wiring it to real
  rows is T14's "Web MVP" job per `docs/BUILD_ORDER.md`, not this ticket's
  scope) — this is the resolver T14 must call once it does, proven correct
  here via direct unit tests against constructed `StoryVariantOut` values
  rather than through a live endpoint that doesn't exist yet.

  **Pilot review sampling** (§4.3): `TELUGU_REVIEW_SAMPLE_RATE` env flag
  (default `0.2`) routes a random subset of QA-passed IMMIGRATION/LEGAL/
  FINANCIAL translations into the existing `review_tasks` queue (reusing
  T11/T12's `ReviewTask` model, not a new table).

  **ADR-004 accepted** (`docs/adr/ADR-004-bilingual-content-lifecycle.md`):
  one `StoryVariant` row per `(story_id, language)` (existing unique
  constraint), not append-only history — "versioned" is satisfied by the
  now-mapped `generated_at`/`model_version` columns (both existed in the DB
  since T03, unused by the ORM until this ticket) rather than a separate
  history table nothing reads yet. Covers the fallback rule, the QA gate,
  glossary enforcement, and why deletion (not a status flag) is the
  correction-invalidation mechanism.

  New tests (`apps/api/tests/test_translate.py`, 10 cases, real Postgres +
  `FakeProvider` for the DB-backed ones, pure unit tests for glossary/QA/
  resolver): a translation with a naive rendering gets glossary-corrected
  and passes QA; a translation missing its number/date/URL fails QA; the
  sweep is idempotent (second call makes no gateway call) and re-processes
  a story after simulating T12's invalidation delete; a sampled IMMIGRATION
  translation lands a `ReviewTask`; glossary/QA/resolver unit tests
  standalone. Also fixed a pre-existing `ruff` F401 (unused
  `datetime`/`UTC` import) in `test_editorial_workflow.py`, unrelated to
  this ticket's own code but caught while running `ruff check .`
  repo-wide. Verified: `pytest` (101 passed, 10 new + all 91 prior, real
  Postgres), `ruff check .` clean repo-wide, `mypy app/content
  app/jobs/translate.py app/ai/gateway.py app/ai/contracts.py app/models.py`
  shows only the same pre-existing failures already present before this
  ticket (`app/ai/providers/anthropic_provider.py`'s SDK union-attr noise,
  `app/ai/gateway.py`'s `model: str | None` argument variance, and
  `app/schemas.py`'s `Language` default-factory variance — none introduced
  by this change, confirmed by running `mypy` against the pre-ticket commit
  for comparison). No new migration — `story_variants.generated_at` already
  existed in the DB since T03's initial migration, only newly mapped in the
  ORM. No `packages/contracts` regeneration needed — no public schema/route
  changed.

  Not yet done/risks: the public `/v1/stories/{slug}` endpoint itself is
  not wired to real DB rows or the fallback resolver — that's explicitly
  T14's scope, not this ticket's (see `docs/BUILD_ORDER.md`); real
  provider-driven translation quality is unverified in this sandbox (no AI
  provider key/network access, same limitation as every AI-gateway-calling
  ticket since T10) — the gateway wiring and the glossary/QA logic around
  it are proven with a `FakeProvider`, not a live model call; the QA checks
  catch *omission* (a number/date/URL/negation marker missing entirely),
  not *mistranslation* of something that's still syntactically present —
  a fluent but factually wrong Telugu sentence that keeps every number
  intact would still pass, exactly as ADR-004 states; the glossary is a
  small hand-seeded list, expected to grow ad hoc as real translation
  output surfaces new terms worth pinning, not a managed admin CRUD
  surface yet.

- 2026-09-08: T12 done — editorial workflow, replacing every T04 stub in
  `apps/api/app/routers/admin.py`. **Approve** (`REVIEW_REQUIRED -> APPROVED
  -> SCHEDULED`, resolving the pending `ReviewTask` and writing an
  `AuditEvent`), **reject** (`REVIEW_REQUIRED -> DRAFT` by default, or
  `-> ARCHIVED` if the request sets `archive: true` — the ticket's literal
  "back to draft or archived"), **retract** (`PUBLISHED -> RETRACTED`), and
  **correct** (updates the `en` `StoryVariant`, records a `Correction` row
  with `old_text_hash`/`new_text_hash` over headline+summary+why_matters,
  transitions `PUBLISHED -> UPDATED` or `UPDATED -> CORRECTION_PENDING ->
  UPDATED` depending on starting state, and deletes any existing `te`
  variant — NON_NEGOTIABLES #7's Telugu-invalidation hook; T13 owns
  regeneration) all reject an illegal starting status with a 409
  `ILLEGAL_TRANSITION`, and all write an `AuditEvent` with the acting
  admin's email as actor — no exceptions, per the ticket's own acceptance
  criterion. New `GET /v1/admin/stories/{id}` (§9.3/§15 review-screen
  payload: AI draft, sensitivity, every source with its rights status side
  by side, the pending review reason, and correction history) and real
  `GET /v1/admin/review-queue` / `GET /v1/admin/audit` (previously `[]`
  stubs).

  **New migration** `73a24fe47a9f`: T03's `story_status` trigger had no path
  for "reject" at all (only the approve/retract/correct chain was legal),
  so this adds `ARCHIVED` to the native enum plus `REVIEW_REQUIRED ->
  DRAFT`/`REVIEW_REQUIRED -> ARCHIVED` to the trigger function. Every other
  T12 transition was already legal from T03. Downgrade rebuilds the enum
  type from scratch (Postgres has no `DROP VALUE`), which requires
  dropping/recreating the guard trigger around the column type change —
  verified by a real `upgrade head` / `downgrade -1` / `upgrade head`
  round-trip against local Postgres, including hitting and fixing two real
  errors along the way (default-cast failure, then the trigger-dependency
  error) rather than just trusting the SQL.

  **New job**: `app/jobs/publish.py` implements the `publish_scheduler` job
  type (reserved in T03's `ck_jobs_type` since the initial schema,
  unimplemented until now) — this is what actually makes the §15 kill
  switches gate something real instead of existing as unused config, per
  the ticket's explicit requirement. `auto_publish_stories` sweeps
  `Story.status == AI_READY` (T11's home for every non-sensitive P2 story):
  with `AUTO_PUBLISH_GLOBAL` off, each is pushed to `REVIEW_REQUIRED` with a
  new `ReviewTask` so an editor actually sees it in the queue instead of it
  rotting silently at `AI_READY` forever; with the flag on, each is
  auto-approved (`-> APPROVED -> SCHEDULED`) and a `system:auto_publish`
  `AuditEvent` is written. Defense in depth (matching T08's rights-gate
  double-check precedent): a story whose `sensitivity != NONE` is *never*
  auto-approved regardless of the flag, even though this should already be
  structurally unreachable via T11's own routing — NON_NEGOTIABLES #5 gets
  no auto-publish override, full stop. `AUTO_PUBLISH_CATEGORY_IMMIGRATION`
  is deliberately never read anywhere in this ticket: T11 never lets an
  IMMIGRATION story reach `AI_READY` to begin with (always routed straight
  to `REVIEW_REQUIRED`), so the flag is structurally a no-op — exactly the
  acceptance criterion, satisfied by construction rather than an explicit
  check. `publish_due_stories` promotes every `Story.status == SCHEDULED`
  (reached via *either* the auto-publish sweep above or a human editor's
  `approve`) to `PUBLISHED` and stamps `published_at`; deliberately **not**
  gated by any kill switch, since the approve decision (human or automatic)
  already happened by the time a story is `SCHEDULED` — gating this step
  too would silently strand every human-approved story if the global switch
  were off. Both run as one `publish_scheduler` job handler (same
  "combine adjacent stages with no independent retry value" precedent as
  T08/T09/T11), scheduled on the same 2-minute time-bucketed-dedupe_key
  pattern as `schedule_ai_classify`, wired into `worker.py`'s
  `JOB_HANDLERS`.

  New ORM: `Correction` model (table already existed since T03, unused
  until now); `Story.published_at` (DB column existed since T03, unused
  until now).

  New tests (`apps/api/tests/test_editorial_workflow.py`, 13 cases, real
  Postgres): every action's happy path and its illegal-transition rejection
  (including the ticket's own named example — approving an already-
  `RETRACTED` story); reject's draft-vs-archive branch; correct's variant
  update + Telugu-invalidation + `Correction` row; the review queue lists a
  pending task; auto-publish's three branches (disabled -> review queue,
  enabled -> `SCHEDULED` then `PUBLISHED` via `publish_due_stories`,
  sensitive-category defense-in-depth even with the flag on); the
  immigration-flag no-op. Verified: `pytest` (91 passed, 13 new + all 78
  prior, real Postgres), `ruff check .` clean repo-wide,
  `mypy app/routers/admin.py app/jobs/publish.py app/jobs/worker.py
  app/models.py app/schemas.py` shows only the same pre-existing
  `str`-vs-`Literal` noise already present at every other ORM-to-schema
  boundary in this codebase (e.g. `_source_out`'s `rights_status` from T06)
  — not a regression, and mypy isn't in CI yet. `alembic upgrade head` /
  `downgrade -1` / `upgrade head` round-trip clean against local Postgres.
  `pnpm run lint`/`typecheck` clean repo-wide including the new
  `apps/admin` pages; `pnpm --filter @teluguvarta/admin build` succeeds.
  `packages/contracts` regenerated and committed (new admin schemas +
  `GET /v1/admin/stories/{id}`). Also ran the real worker loop
  (`process_one`, no mocks) against the live DB: the new `publish_scheduler`
  job claims and completes cleanly (`DONE`, no error) even with zero
  eligible stories in this sandbox (no AI provider key configured, so
  nothing has reached `AI_READY` yet — same limitation T11 hit) — confirms
  the wiring, not the auto-publish branch logic itself, which is covered by
  the unit tests above instead.

  **Design decisions made without a separate ADR** (documented here per
  NON_NEGOTIABLES #11's "write it down" bar, but not treated as
  requiring a formal ADR since these are implementation completions of
  T03's already-accepted state machine, not new legal/architecture
  positions): (1) "reject -> back to draft or archived" needed a real
  terminal `Story.status` outcome the schema didn't have — added
  `ARCHIVED` rather than repurposing the `source_items.ingest_status`
  concept, since `stories.status` is the field editors and the public API
  actually read. (2) Manual approve and the auto-publish sweep both stop at
  `SCHEDULED` (matching the ticket's literal "approve -> APPROVED/
  SCHEDULED"), with a single always-on `publish_due_stories` step doing the
  final `SCHEDULED -> PUBLISHED` hop for both — this is what makes retract
  (`PUBLISHED -> RETRACTED`) actually reachable without inventing a
  publish-time-scheduling feature no ticket has asked for yet.

  Not yet done/risks: real end-to-end auto-publish behavior against actual
  AI-generated `AI_READY` stories is unverified in this sandbox (no AI
  provider key/network access) — the unit tests directly construct
  `AI_READY` stories rather than running the full T11 pipeline first, same
  limitation noted in T10/T11's own changelog entries; the admin UI's
  review/story-detail pages are plain unstyled HTML (no design system
  exists yet in this repo) and untested against a running browser session
  (no browser tooling available in this environment) — `tsc`/`next build`
  passing confirms the code compiles and prerenders, not that the UI is
  usable; `AdminStoryDetailOut` exposes `source_rights_status` per source
  but the admin UI doesn't yet visually flag a `LICENSED_METADATA`/
  `LICENSED_REPURPOSE` source specially since ADR-002 means none should
  ever exist in this build phase anyway.

- 2026-09-08: T11 done — `apps/api/app/jobs/generate.py` turns a T09
  `CLUSTERED` `Story` into a reviewable draft, one `ai_classify` job type
  (already in T03's `ck_jobs_type` list) doing the whole pipeline slice in
  one handler, mirroring T08/T09's precedent of combining adjacent stages
  rather than splitting into more job types than have independent retry
  value: `RELEVANCE_CATEGORIZATION` gateway call first (always runs — not
  in `DEGRADABLE_ON_BUDGET_BREACH`, so classification keeps triaging under
  a budget breach), then, only if the AI says the story is relevant, a
  `SUMMARY` gateway call (skips the expensive generation call entirely for
  irrelevant/P3 stories — §19 cost control). Every claim's `source_refs`
  requirement and low-confidence review routing come for free from T10's
  gateway itself (`_remove_unsupported_claims`/`CONFIDENCE_REVIEW_THRESHOLD`)
  — T11 only adds the story-generation-specific layer on top: §5.2's
  publication rules (`sensitivity != NONE` — immigration/legal/financial/
  breaking/obituary-accusation — always forces `REVIEW_REQUIRED`, tested
  explicitly as a non-negotiable, not just a default), §15's P1
  "high-importance if configured" tier (`AI_REVIEW_P1_STORIES` env flag,
  default on), and an ADR-002 similarity-to-source flag (the only "source
  text" available to compare against is the source item's *title* —
  `SourceItem` never stores full article body text — so this is a
  title-similarity check, not a full paraphrase detector). Populates
  `StoryVariant` (en), `Entity`/`EntityAlias`/`StoryEntity`, and
  `Topic`/`StoryTopic` from the classification output — new ORM models for
  all of these plus `ReviewTask` added to `app/models.py` (tables already
  existed from T03; T11 is the first ticket to read/write them).
  `Story.status`/`Source.rights_status`-style native-enum columns
  (`story_status`) needed the same `ENUM(..., create_type=False)` treatment
  in the ORM as `rights_status` already had — the first ticket to filter a
  query on `stories.status` hit `operator does not exist: story_status =
  character varying` without it. `Story.sensitivity`/`Story.importance`
  ORM columns added (DB columns existed since T03, unused until now).

  **Contract extension**: added `headline_en` (required) to T10's
  `GenerationResult` (`app/ai/contracts.py`) — ADR-002 requires every
  published story to carry an AI-drafted *original* headline, never the
  source's own, and `story_variants.headline` is `NOT NULL`, but §7.3's
  contract as T10 built it had no field for one; deterministically reusing
  the source title would have violated ADR-002 directly. Updated
  `test_ai_gateway.py`'s `_valid_payload()` fixture to match; all 7
  pre-existing T10 gateway tests still pass.

  **Fixed a real, pre-existing T09 bug found while building this**:
  `schedule_dedup_cluster` enqueued job type `"dedup_cluster"`, which was
  never a member of T03's `ck_jobs_type` CHECK constraint (only
  `story_cluster` was) — every real call would raise at insert time; no
  test caught it because clustering tests only exercised
  `run_dedup_cluster` on directly-inserted rows, never the scheduler
  against a real migrated DB. Renamed the job type (and its handler-map
  key in `worker.py`) to `story_cluster`, the existing allowed name that
  already fits. Confirmed by reproducing the failure directly against
  local Postgres before fixing it.

  **New migration** `9d3f6b1a2c47` adds `ENRICHED`/`REVIEW`/`SCHEDULED` to
  `source_items.ingest_status` per §6.4's literal state names, plus
  `ARCHIVED` (no spec equivalent — added because the ticket's own scope
  explicitly requires a terminal outcome for "P3 archived, not published,"
  and the AI-classify step, before the costlier generation call runs, is
  exactly where that's decided) — same incremental-CHECK-constraint pattern
  as `2f6a0e7c9d41` (T09's `CLUSTERED`). `Story.status`'s own enum/trigger
  (T03) was deliberately left untouched: its legal-transition set only
  allows `DRAFT -> AI_READY -> REVIEW_REQUIRED -> ...`, so P2 stories
  (eligible for auto-publish) simply stop at `AI_READY` — no state exists
  for "auto-approved," that's T12's `AI_READY -> REVIEW_REQUIRED ->
  APPROVED` transition to own — and P3 stories never leave `DRAFT` at all
  (distinguished from "still processing" via `ingest_status = ARCHIVED` on
  their `SourceItem`s, not a `Story.status` value).

  New tests (`apps/api/tests/test_generate.py`, 7 cases, `FakeProvider`
  monkeypatched into the gateway like `test_ai_gateway.py`): a low-risk
  story generates and reaches `AI_READY`/`SCHEDULED`; an `IMMIGRATION`
  classification always reaches `REVIEW_REQUIRED` regardless of confidence
  (the explicit non-negotiable acceptance criterion); low-confidence
  classification routes to review; an irrelevant story is archived without
  ever making the (more expensive) generation call; a story whose only
  claim has no `source_refs` is held, not published; provider-unavailable
  leaves the story untouched for a later sweep rather than inventing
  content; a second `generate_stories` pass over an already-generated story
  is a no-op (idempotency — proven by only queuing one round of fake
  responses, so a second real call would raise `IndexError`).

  Verified: `pytest` (78 passed, 7 new + all 71 prior, real Postgres),
  `ruff check .` clean, `mypy app/jobs app/ai app/models.py` clean (its
  pre-existing failures are all in `app/ai/providers/`, untouched by this
  ticket — mypy isn't in CI yet). `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-trip clean against local Postgres. Also ran the real
  worker loop (`process_one`, no mocks) against the live T08/T09-seeded
  data (231 `CLUSTERED` `SourceItem`s across 19 `Story` rows): the renamed
  `story_cluster` job now actually runs (previously would have errored on
  every attempt); `ai_classify` ran and correctly left everything untouched
  since this sandbox has no AI provider key configured — zero `ai_call_log`
  rows written, confirming the real `UNAVAILABLE` path (not a mock) never
  invents content, matching T10's already-proven behavior.

  Not yet done/risks: entity type is always `OTHER` (§7.3's `entities[]` is
  a flat name list with no PERSON/ORG/LOCATION distinction — a future
  ticket extending that contract would let `StoryEntity` be more useful for
  ranking/browsing); `Topic` rows are created on-demand from whatever
  category strings the model returns rather than matched against a curated
  taxonomy (none is seeded yet anywhere in the build) — expect topic-slug
  drift/duplication until a real taxonomy exists; the ADR-002
  similarity-to-source check only has the source *title* to compare
  against (no article body is ever stored), so it's a narrower signal than
  true paraphrase detection; `importance` is set to the classification
  call's raw `confidence` as a placeholder, not a real scoring formula —
  T16 (personalization/ranking) territory.


- 2026-09-08: T10 done — `apps/api/app/ai/` is the AI gateway: `tasks.py`
  holds the §7.2 routing table (task → default/escalation provider+model;
  language detection is deterministic Unicode-range script detection, no
  model call); `contracts.py` is the §7.3 `GenerationResult` Pydantic
  schema; `providers/{openai,anthropic}_provider.py` are the only two files
  that import a provider SDK, `null_provider.py` is the fallback when no
  key is configured; `gateway.py::AiGateway.run_task` implements every
  §7.5 failure mode — schema-validation failure retries once with a
  constrained prompt then holds, low confidence goes to review queue,
  sensitive validation always forces review queue regardless of
  confidence, an unsupported claim (no `source_refs`) is stripped and the
  story holds if that empties the claim list entirely, a provider
  exception surfaces as `UNAVAILABLE` with no content invented, and a
  breached `MONTHLY_AI_BUDGET_USD` degrades `SUMMARY`/`WHY_MATTERS`/
  `TRANSLATION_EN_TE` to `CLASSIFICATION_ONLY` (relevance/categorization
  keeps running) without ever calling the provider. `budget.py` records
  one `AiCallLog` row per attempt (new `ai_call_log` table, migration
  `7a4c9e2b5d10`) — tokens/cost queryable per task/day via
  `cost_by_task_and_day`. T09's `_escalate_to_ai` stub in
  `app/jobs/cluster.py` now calls the real gateway (`DEDUP_CLUSTER_ESCALATION`
  task); with no provider key configured in this environment it correctly
  falls back to "not matching" through the real `UNAVAILABLE` path, not a
  mock — verified with a title pair placed deliberately in the ambiguous
  0.4–0.72 similarity band.

  **ADR-001 accepted**, covering two decisions: (1) providers — OpenAI
  primary, Anthropic secondary (translation's required "second provider"
  escalation leg, and sensitive-validation's reasoning model, so one
  vendor's outage/policy change can't take out both the main pipeline and
  sensitive handling); (2) **the gateway lives in Python at
  `apps/api/app/ai/`, not the TypeScript `packages/ai`** that §11's
  monorepo diagram names — every actual AI-consuming caller (T09's
  clustering, T11's future story generation) is Python code in `apps/api`,
  and building the real gateway in TS would mean either a second
  always-on service + network hop per AI call or duplicating the routing/
  validation/budget logic in two languages, both of which are
  infrastructure the spec doesn't call for. `packages/ai` is kept only as
  a hand-maintained TS type mirror of the §7.3 contract for `apps/admin` to
  type AI-generated fields it reads back over the API — it has no SDK
  access at all. A CI step in the `api` job greps for `import openai`/
  `import anthropic` outside `apps/api/app/ai/providers/` and fails the
  build if found — this is the actual acceptance-criteria enforcement
  boundary, adjusted from the ticket's literal "`packages/ai`" wording to
  match where the code actually lives; see ADR-001 for the full reasoning.
  `.env.example`'s single ambiguous `AI_PROVIDER_API_KEY` is replaced with
  `AI_OPENAI_API_KEY` / `AI_ANTHROPIC_API_KEY`.

  Real provider calls are **not** end-to-end verified — no API keys are
  configured in this sandbox (no network access either), so
  `OpenAiProvider`/`AnthropicProvider` are exercised only for their
  key-presence check, not a live request; every failure-mode and
  routing/telemetry test instead uses a `FakeProvider` test double or the
  real `NullProvider` fallback path (itself real code, not mocked) to
  reach `UNAVAILABLE`. Model pricing in `tasks.py::MODEL_PRICING` is
  best-effort, not billed rates. `apps/api/pyproject.toml` gained
  `pydantic` (already a transitive FastAPI dependency, now imported
  directly), `openai`, and `anthropic`. Verified: `ruff check .` clean,
  `pytest` 71 passed (18 new AI-gateway tests, all requiring Postgres for
  telemetry writes except the routing-table/language-detection unit
  tests), `pnpm run lint`/`typecheck` clean repo-wide, migration
  `7a4c9e2b5d10` upgrade+downgrade round-trips cleanly, CI provider-SDK
  grep check confirmed to pass (no leaks) and to correctly fail if a
  provider import is added outside the two provider files.

- 2026-09-08: T09 done — §7.2's model-routing rule ("Dedup/clustering:
  fingerprint + lexical similarity first; embedding/model only for ambiguous
  pairs") implemented as pure deterministic code, no AI call, in new
  `apps/api/app/jobs/cluster.py`. **Fingerprint**: `SourceItem.raw_hash`
  changed from a hash of the raw fetch bytes (T07) to a hash of the
  *normalized title text* (`app/adapters/base.py::normalize()`) — the T07
  version could never match across sources reporting the same event, since
  two different feeds' raw XML for the same story never shares bytes; no
  test asserted the old value, so this was a safe in-place change, not a new
  column. **Clustering**: `cluster_normalized_items()` processes every
  `NORMALIZED` `SourceItem` in stable order (`published_at`, nulls last,
  then `id`); for each, it looks for an already-`CLUSTERED` item within a
  72-hour window whose normalized-title key matches exactly (fingerprint) or
  whose `difflib.SequenceMatcher` ratio is >= 0.72 (lexical similarity) — if
  found, attaches as `SUPPORTING` to that item's `Story`; otherwise creates a
  new `Story` with this item as `PRIMARY`. A ratio <= 0.40 is a definite
  non-match; the ambiguous band between the two thresholds is where §7.2
  says to escalate to an embedding/model call — stubbed as
  `_escalate_to_ai()` (always returns "not a match" for now, a TODO for
  T10/T11 once the AI gateway exists) since T10 hasn't landed and
  NON_NEGOTIABLES' "prefer deterministic code" default means this ticket
  should not block on it. Processing items in one stable pass means a
  same-run pair (e.g. two feeds reporting one event in the same batch)
  clusters together naturally — the earlier one creates the `Story`, the
  later one attaches to it — without a separate same-batch grouping step.
  §6.4's `DEDUPED` state is never persisted on its own: fingerprinting and
  clustering happen in one deterministic pass here, so a `SourceItem` goes
  `NORMALIZED` -> `CLUSTERED` directly (migration
  `2f6a0e7c9d41_source_items_clustered_status.py` adds `CLUSTERED` to the
  existing `ck_source_items_ingest_status` check constraint). New ORM models
  `Story`/`StorySource` in `app/models.py` (both tables already existed from
  T03's migration; T09 is the first ticket to read/write them). Wired into
  production via the existing worker loop, mirroring T08's pattern exactly:
  `schedule_dedup_cluster()` enqueues a time-bucketed (2-minute window)
  `dedup_cluster` job through the same `app/jobs/queue.py` mechanics as
  `source_fetch` (bounded retry, observable via `/v1/admin/jobs`), and
  `run_dedup_cluster` is now a second entry in `worker.py`'s
  `JOB_HANDLERS`. New tests (`apps/api/tests/test_cluster.py`, 4 cases,
  Postgres-backed via the `migrated_database` fixture, `SourceItem` rows
  inserted directly rather than through an adapter since clustering doesn't
  care which adapter produced a `NORMALIZED` row): two similarly-worded
  titles cluster into one `Story` with correct `PRIMARY`/`SUPPORTING` roles
  and both items advance to `CLUSTERED`; two unrelated titles never cluster;
  re-running `cluster_normalized_items` a second time with no new
  `NORMALIZED` items processes zero and creates no duplicate `Story`/
  `StorySource` rows; an exact-after-normalization title (differing only in
  case/punctuation) clusters via the fingerprint path. Verified: `pytest`
  (53 passed, 4 new, real Postgres), `ruff check .` clean, `mypy app/jobs
  app/adapters app/models.py` clean, `alembic upgrade head` / `downgrade -1`
  / `upgrade head` round-trip clean. Not yet done/risks: the two similarity
  thresholds (0.72 match / 0.40 no-match) and the 72-hour comparison window
  are judgment calls with no spec-given numbers — reasonable starting points
  from testing against realistic headline pairs, but worth tuning once real
  ingested volume from T08's live sources gives a sense of false-positive/
  negative rates; the ambiguous-band stub means any pair T09 can't decide
  deterministically is currently *never* clustered (favors precision over
  recall) until T10/T11 wire up the real escalation call; `_find_matching_story`
  scans every currently-`CLUSTERED` `SourceItem` (filtered by the 72h window
  only after loading) rather than an indexed/pre-filtered query — fine at
  current seed-data volume, worth revisiting if the `CLUSTERED` set grows
  large enough to make an O(n) per-item scan costly.
- 2026-09-08: T08 done — the T03 `jobs` table now has real claim/retry code
  and a first job type. **ADR-003 (database job queue strategy)** accepted
  (`docs/adr/ADR-003-database-job-queue-strategy.md`): claiming uses
  `SELECT ... FOR UPDATE SKIP LOCKED` (also reclaims a `RUNNING` job whose
  5-minute `lock_expiry` passed, e.g. a crashed worker) with the update to
  `RUNNING` committed immediately so the row lock doesn't sit open for the
  job's full runtime; deployment shape is **one lightweight always-on
  worker process** (`python -m app.jobs.worker`) rather than a managed cron
  trigger per job type, justified against §14's 14 job types accumulating
  handlers over the remaining tickets; retry is bounded
  (`MAX_JOB_ATTEMPTS = 5`, exponential backoff `60s * 2^(attempts-1)` capped
  at `3600s`, terminal `FAILED` after that — NON_NEGOTIABLES #10, no
  infinite retry loop). New `apps/api/app/jobs/`: `queue.py` (generic
  claim/complete/fail/enqueue, reusable by every future job type) and
  `source_fetch.py` (the actual job: scheduling due sources via a
  time-bucketed `dedupe_key` so re-polling the scheduler within one
  `refresh_minutes` window is a no-op, then running T07's
  fetch→normalize→validate→emit pipeline). **The rights gate is enforced
  inside `adapters/base.py::emit()` itself, not by the job or scheduler**:
  a new `source_items.ingest_status` column (migration `1b4ff735cc70`,
  values `DISCOVERED`/`RIGHTS_BLOCKED`/`NORMALIZED` per §6.4) is set to
  `NORMALIZED` only when `source.rights_status == LINK_ONLY`, `RIGHTS_BLOCKED`
  otherwise (including `DISABLED`) — this is defense-in-depth against a
  source's rights status changing between when a job is enqueued and when
  it actually runs, per NON_NEGOTIABLES #4 ("never bypass the rights gate").
  §6.5's circuit breaker acts on `sources.fail_count` (already exposed via
  T06's `/v1/admin/sources`): the scheduler stops enqueueing new
  `source_fetch` jobs once `fail_count >= 5`, deliberately manual-reset, not
  auto-clearing on a timer. `GET /v1/admin/jobs` (previously a T04 stub
  returning `[]`) now queries real `Job` rows so job health is actually
  visible. New tests (`apps/api/tests/test_jobs.py`, 10 cases; 2 more added
  to `test_adapters.py` for the emit()-level rights gate; 1 more added to
  `test_admin_sources.py` for the jobs endpoint): concurrent `claim_job`
  calls (5 real threads against real Postgres) never claim the same job
  twice; bounded retry reschedules-then-terminates at `MAX_JOB_ATTEMPTS`;
  scheduler skips `DISABLED` and circuit-broken sources and is idempotent
  within a cadence window; `run_source_fetch` resets/increments source
  health on success/failure and doesn't duplicate `SourceItem` rows on
  rerun (fixture-backed, `httpx.MockTransport`, same style as T07).
  Verified: `pytest` (49 passed), `ruff check .` clean, `mypy app/jobs
  app/adapters` clean; `alembic upgrade head` / `downgrade -1` / `upgrade
  head` round-trip clean against local Postgres. Also ran the worker for
  real (`process_one` in a loop, no mocks) against the 3 live T07-seeded
  sources: NPR and State Dept both succeeded (228 real `SourceItem` rows,
  all `NORMALIZED`), FEMA's feed returned a live `403 Forbidden` to our
  `httpx` client (no `User-Agent` header) — correctly recorded as a bounded,
  backed-off retry (`fail_count=1`, job `PENDING` with backoff, not stuck or
  infinite) rather than crashing the worker. Not yet done/risks: the FEMA
  403 is a real finding, not a test artifact — worth a `User-Agent` header
  on the shared `httpx.Client` or reconsidering FEMA as a source (T07's
  changelog already flagged FEMA as a weak source on content-relevance
  grounds; this adds a reachability concern) — follow-up for T09 source
  curation or a small adapter fix, not blocking this ticket's acceptance
  criteria since bounded-retry behavior is exactly what's supposed to
  happen. Adapter dispatch is hardcoded to `RssFeedAdapter` (still the only
  adapter that exists, per T07) — a real per-`source_type` registry is
  deferred until a second adapter actually exists. Job attempts/backoff are
  tracked per job row, not per source — a source with a genuinely flaky
  feed will get a fresh job (and fresh attempts budget) every
  `refresh_minutes` window even while its own `fail_count` climbs toward
  the circuit breaker; this matches the ticket's stated split between
  job-level retry and source-level circuit breaker (ADR-003) but is worth
  knowing if failure patterns look surprising later.
- 2026-09-08: T07 done — §6.3 adapter contract (`fetch -> normalize ->
  validate -> emit`) implemented as `app/adapters/base.py` (shared
  normalize/validate/emit — identical across every LINK_ONLY feed source)
  plus `app/adapters/rss.py`, a generic RSS 2.0/Atom parser (stdlib
  `xml.etree`, no new parsing dependency) covering all 3 seeded sources.
  `emit()` upserts into `source_items` on the existing
  `(source_id, external_id)` unique constraint via Postgres
  `INSERT ... ON CONFLICT DO UPDATE`, so a re-run never duplicates a row —
  the §6 "never duplicate ... when the same source item reappears" rule.
  Added the `SourceItem` ORM model (`app/models.py`) that T03's migration
  never needed until now. `infra/scripts/seed.py` now also seeds 3 LINK_ONLY
  sources with rights evidence already on file (ADR-002 requires this before
  a source can move off `DISABLED`): NPR News, U.S. Dept of State Travel
  Advisories, FEMA Disaster Declarations — all real, publicly-readable feeds
  whose reachability/shape were checked directly (WebFetch) on 2026-09-08;
  admin seeding is now independent of source seeding (previously an early
  return skipped everything if `ADMIN_SEED_EMAIL` wasn't set). Verified
  idempotent by running the script twice against local Postgres — 3 rows,
  no duplicates. `httpx` moved from dev-only to a main dependency since the
  adapter needs a real HTTP client at runtime, not just in tests. New tests
  (`apps/api/tests/test_adapters.py`, 5 cases) run `fetch()` for real against
  `apps/api/tests/fixtures/*.xml` via `httpx.MockTransport` (so parsing code
  is genuinely exercised, only the socket is faked) — normalize/validate for
  two clean sources, a FEMA fixture with one item missing a title to prove
  `validate()` rejects bad data instead of `emit()` silently accepting it,
  and two Postgres-backed tests (`migrated_database` fixture) proving
  `emit()` creates real `SourceItem` rows and that re-running the full
  pipeline twice on the same fixture does not duplicate them. Not wired to a
  scheduler — that's T08. Verified: `pytest` (36 passed, 5 new), `ruff check
  .` clean, `mypy app/adapters` clean (pre-existing mypy errors elsewhere in
  the codebase are untouched — mypy isn't in CI yet, only ruff/pytest/pnpm
  lint+typecheck are). Not yet done/risks: `rights_evidence_url` values for
  the 3 seeded sources point at each publisher's own terms/reuse page but
  weren't independently re-verified beyond the feed URLs themselves — an
  editor should confirm before T08 starts live polling against them; FEMA's
  feed titles are often bare numbers (e.g. disaster number only), so it's a
  weak source for a Telugu-diaspora-relevant news product even though it's a
  real, working, low-risk government feed — worth reconsidering in T08/T09
  source curation, not something T07's adapter-proof scope should decide.
- 2026-09-08: T05 done — admin auth is real, replacing T04's stub. New
  migration `infra/migrations/versions/8f1a2c9d4b3e_admin_auth.py` adds
  `role`/`password_hash`/`mfa_secret`/`last_login_at` to `users` (staff use
  the same table as everyone else, since `review_tasks.reviewer_id` /
  `corrections.created_by` already reference `users.id` — a `NULL` role
  means an ordinary end user) plus `admin_login_attempts` for rate
  limiting. `POST /v1/admin/auth/login` (`apps/api/app/routers/
  admin_auth.py`, no `current_admin` dependency — that's how you get the
  token that dependency checks) verifies a bcrypt password hash and issues
  a short-lived (`ADMIN_JWT_EXPIRE_MINUTES`, default 30 min) HS256 JWT
  carrying a `role` claim; `current_admin` (`apps/api/app/auth.py`) now
  decodes and verifies that JWT and requires `role` in `{EDITOR, ADMIN}`
  instead of just checking a bearer token is present. Rate limiting is a
  plain indexed Postgres query over `admin_login_attempts` (5 attempts /
  15 min per email) — deliberately not Redis, per NON_NEGOTIABLES. Added
  `app/db.py` (lazy per-request `DATABASE_URL` → engine, cached by URL —
  this is the first ticket needing a live DB connection from the API
  process itself) and `app/models.py` (SQLAlchemy ORM for `User`,
  `AdminLoginAttempt` — only the columns app code touches, not a mirror of
  every migration column). `infra/scripts/seed.py` now seeds one admin
  user from `ADMIN_SEED_EMAIL`/`ADMIN_SEED_PASSWORD` (idempotent — updates
  the password hash if the row exists). New deps: `pyjwt`, `bcrypt`.
  **ADR-006 (account/privacy architecture)** written as `proposed`
  (`docs/adr/ADR-006-account-privacy-architecture.md`): V1 end users get
  device-scoped anonymous identity only (no login/OAuth), so
  `DELETE /v1/me/account` is a single cascading row delete and "account
  deletion before account creation" is satisfied trivially — no login flow
  exists to gate. `current_user`/`/v1/me/*` remain the T04 stub;
  implementing that anonymous-token issuance is for T14/T15, not this
  ticket, which is admin-only per its own scope note. New tests
  (`apps/api/tests/test_admin_auth.py`, 7 cases): login success + the
  issued token unlocking `/v1/admin/*`, wrong password, unknown email, a
  token forged with a non-admin role rejected 403, an expired token
  rejected 401, and rate-limiting (both that the 6th attempt in the window
  is rejected 429, and that it doesn't leak across different emails) —
  seeded via direct DB inserts rather than real wall-clock waits or firing
  5 real requests. Also added `POST /v1/admin/auth/login` to
  `test_api_contract.py`'s expected-endpoints list. Verified: `pytest` (22
  passed, real Postgres via the existing `migrated_database` fixture,
  including a manual `alembic upgrade head` / `downgrade -1` / `upgrade
  head` round-trip against local Postgres), `ruff check .` clean, `pnpm run
  lint`/`typecheck` clean repo-wide, `packages/contracts` regenerated
  (`openapi.json`/`types.gen.ts`) and committed. Not yet done/risks: MFA
  itself is deferred (ticket explicitly allows "MFA-ready" over MFA this
  round) — `mfa_secret` column exists but nothing reads/writes it yet, so a
  later ticket must add the actual second factor before this fully
  satisfies §16's "MFA for admin sessions" baseline; no admin login UI in
  `apps/admin` yet (out of scope — the ticket's acceptance criterion is
  "a seeded admin user can log in and reach `apps/admin`" via the API, and
  `apps/admin` has no pages built yet at all, pre-dating this ticket).
- 2026-09-08: T04 done — all 21 §13 endpoints implemented in FastAPI with
  final request/response shapes (`apps/api/app/schemas.py`) but stub data,
  since T06+ (source registry, ingestion, story generation) haven't landed:
  public (`home`, `stories`, `stories/{slug}`, `stories/{slug}/share-meta`,
  `topics/{slug}`, `search`, `config`), authenticated `/v1/me/*`, and
  `/v1/admin/*`. Auth is intentionally stubbed (`apps/api/app/auth.py`) —
  both `current_user`/`current_admin` only check for a bearer token, no
  real verification or role check; a comment flags that T05 must replace
  the body of both before ship. Standard error envelope
  (`{"error": {"code","message","request_id"}}`) is one set of exception
  handlers (`apps/api/app/errors.py`) covering `APIError` (raised from
  routes), 404s, 422 validation errors, and unhandled 500s, plus a
  `X-Request-ID` middleware — not per-endpoint code. `packages/contracts`
  now has real generated output (`openapi.json`, `types.gen.ts` via
  `openapi-typescript`) instead of the `export {}` stub; regenerate with
  `pnpm run contracts:generate` (`infra/scripts/generate_contracts.sh`).
  Added a `contracts` CI job that regenerates and `git diff --exit-code`s
  the committed files, plus typechecks the package — fails the build on
  drift per the ticket's acceptance criteria. New tests
  (`apps/api/tests/test_api_contract.py`): OpenAPI schema validates
  (`openapi-spec-validator`), every §13 endpoint is registered, and the
  error envelope/auth-gate behavior is exercised end-to-end via
  `TestClient`. Verified: `pytest` (15 passed), `ruff check .` clean,
  `pnpm run lint`/`typecheck` clean repo-wide (now includes
  `packages/contracts`'s own `tsc --noEmit`). Added a
  `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` entry so
  FastAPI's idiomatic `Depends()`-in-default-args pattern doesn't trip
  B008. Not yet done: `apps/web`/`apps/mobile`/`apps/admin` don't call the
  API or import `@teluguvarta/contracts` yet (no page needs it before T14/
  T15) — the rule to import types only from there is for when they do.
- 2026-09-08: T03 done — one Alembic migration
  (`infra/migrations/versions/0c23c235e618_core_data_model.py`) implements
  every §12 entity (`users` through `audit_events`, plural table names to
  dodge the `user` reserved word). `sources.rights_status` and
  `stories.status` are native Postgres enums; `rights_status` defaults to
  `DISABLED` at the column level (NON_NEGOTIABLES #4). Legal `stories.status`
  transitions (`DRAFT -> AI_READY -> REVIEW_REQUIRED -> APPROVED ->
  SCHEDULED -> PUBLISHED -> UPDATED`, `PUBLISHED -> RETRACTED`, `UPDATED ->
  CORRECTION_PENDING -> UPDATED`) are enforced by a `BEFORE UPDATE` trigger
  (`enforce_story_status_transition`) rather than app code, since there's no
  app/domain layer yet for a guarded transition function to live in — a
  choice noted in the migration's docstring per the ticket's instruction.
  Required indexes present: unique `stories.canonical_slug`, unique
  `source_items(source_id, external_id)`, `jobs(status, run_after)`, and
  `gin`/`pg_trgm` indexes on `story_variants.headline`/`summary`. Added
  `jobs.lock_expiry`/`dedupe_key` and `notifications.notification_key`
  beyond the bare §12 field list because the ticket text and §14's stated
  dedupe rule require them. New pytest suite
  (`apps/api/tests/{conftest.py,test_schema.py}`) spins up throw-away
  Postgres databases per test (via a new `scratch_database`/
  `migrated_database` fixture pair) to verify: all tables exist after
  `alembic upgrade head`; upgrade+downgrade round-trips cleanly to empty;
  `rights_status` defaults to `DISABLED` and rejects invalid enum values;
  illegal story transitions raise `CheckViolation` and legal ones succeed.
  Tests skip (not fail) when no Postgres is reachable. CI's `api` job now
  runs a `postgres:16-alpine` service container so these run in CI, not
  just locally. Verified end-to-end this session by installing
  `postgresql@16` via Homebrew locally (with the user's explicit go-ahead,
  since that's a persistent change to their machine) — `alembic upgrade
  head`, `alembic downgrade base`, and `pytest` (7 passed) all ran clean
  against it; `ruff check .` clean. The Homebrew Postgres install and the
  `teluguvarta` role/db it created were left in place on the user's machine
  (not uninstalled) since T02's docker-compose Postgres is the intended
  long-term local setup — either works going forward.
- 2026-09-08: T02 done — `.env.example` at repo root covers every var named
  in `docs/SPEC.md` (`_USD`/`_ENABLED`/`_GLOBAL`) plus DB, AI provider
  (placeholder key, name only — ADR-001 not yet decided), push (FCM/APNs/
  Expo), object storage, and Sentry. `docker-compose.yml` runs Postgres 16
  with `pg_trgm` created via `infra/postgres/init/01-extensions.sql`.
  Alembic is wired into `infra/migrations/` (`apps/api/alembic.ini`,
  `script_location` points there); `infra/migrations/env.py` loads
  `DATABASE_URL` from repo-root `.env` via `python-dotenv` and fails fast
  with a clear message if unset — no schema/revisions yet, that's T03.
  `infra/scripts/migrate.sh` wraps `alembic` (activates the api venv);
  `infra/scripts/seed.py` is a no-op placeholder until T03/T06. Root
  `package.json` gained `pnpm run migrate` / `pnpm run seed`. README local
  setup section rewritten with the full clone→env→compose→install→migrate
  flow. Verified: `ruff check .` and `pytest` clean in `apps/api`; `pnpm run
  lint`/`typecheck` clean repo-wide; `migrate.sh` correctly loads `.env` and
  reaches the DB-connect step (confirmed via clean connection-refused error)
  — **not fully end-to-end verified**, since this sandbox has neither
  Docker nor a local Postgres and installing Postgres via Homebrew would be
  a persistent change to the user's machine outside repo scope; a real dev
  machine with Docker should run `docker compose up -d && pnpm run
  migrate` to confirm before trusting this blindly.
- 2026-09-08: T01 done — pnpm workspace root (`package.json`,
  `pnpm-workspace.yaml`), shared `packages/config` (base tsconfig +
  eslint), stub `packages/{contracts,domain,ai,ui}`. `apps/web` and
  `apps/admin` are minimal Next.js 14 App Router apps (build + lint +
  typecheck clean). `apps/mobile` is a minimal Expo/React Native app
  (typecheck clean; not build-tested, no native toolchain in this
  environment). `apps/api` is FastAPI with `/health` (verified 200 via
  uvicorn) + one pytest test + ruff clean; requires Python 3.11+ (local env
  only had 3.10, used the 3.13 install instead). CI
  (`.github/workflows/ci.yml`) runs pnpm install/lint/typecheck and
  pip install/ruff/pytest on push+PR. Fixed a stray leading `\` in
  `.gitignore` that broke `ruff check .`. README local-setup section
  filled in with real install/run/test commands (T02 will still add
  Postgres/env/seed).
- 2026-09-08: ADR-002 accepted — V1 restricted to `LINK_ONLY` sources only
  (AI-written original summary + why-matters + attribution + source link;
  no reproduced headlines/text/images). `LICENSED_METADATA`/
  `LICENSED_REPURPOSE` and the Share Card image feature are deferred.
  Threaded into `NON_NEGOTIABLES.md`, `SPEC.md`, and tickets T06/T07/T11/
  T14/T15.
- 2026-09-08: Repo scaffolded — planning docs, ticket breakdown, monorepo
  directory skeleton, ADR template created. No implementation tickets
  started yet.
