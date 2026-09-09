# Progress tracker

Update this file at the end of every ticket. This is the source of truth for
"what's actually done" — trust it over assumptions, git log archaeology, or
prior conversation history.

**Pre-build validation gate** (product decision, not a ticket — see
`docs/BUILD_ORDER.md`): NOT STARTED.

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
| T17 Push notifications | not started | |
| T18 Observability | not started | |
| T19 Hardening | not started | |
| T20 Pilot | not started | |

## X adapter

| Ticket | Status | Notes |
|---|---|---|
| X1 X source registry fields | not started | |
| X2 Incremental X fetch | not started | |
| X3 X post to story pipeline | not started | |
| X4 X monitoring/budget guard | not started | |

## Student experience

| Ticket | Status | Notes |
|---|---|---|
| S1 Student life-stage profile | not started | |
| S2 Student topics/alerts | not started | |

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
| ADR-007 Production hosting/cost limits | not started |

## Changelog

(newest first — one line per ticket completion)

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
