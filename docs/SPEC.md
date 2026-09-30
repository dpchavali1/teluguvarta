# TTE — The Telugu Edit (formerly Telugu Global) — Condensed Master Specification (source: V5.2 Codex Master Spec)

This is a condensed, implementation-focused digest of the authoritative spec PDF
(`Telugu_NRI_Global_Platform_Codex_Master_Specification_V5_2.pdf`). **This file,
plus the ADRs in `docs/adr/`, is the sole product/architecture authority for this
repo.** Do not resurrect any V3/V4 architecture. If this digest and the original
PDF ever disagree, the PDF wins for prose/nuance — but no engineering session
should need to re-open the PDF; if you find a gap, fix this file and note it.

For day-to-day ticket work, prefer `docs/NON_NEGOTIABLES.md`, `docs/BUILD_ORDER.md`,
and the specific `docs/tickets/Txx.md` file over re-reading this whole document.

## 1. Product strategy

- **Definition**: Free, English-first information platform for Telugu people
  worldwide — global Telugu identity + practical info about where the user
  lives and the Indian places they call home.
- **Positioning**: "Your world. Your roots. One Telugu feed." Moat =
  personalization, bilingual access, NRI usefulness, provenance, high-signal
  curation — not raw volume of breaking news.
- **Launch wedge**: USA Telugu NRIs (immigration, money, USA local practical
  info, AP/Telangana, family/parents, community events, entertainment). Content
  model stays geography-agnostic so Canada/Australia/UK/Middle East/India can be
  added later without a rewrite.
- **No pilot**: the original PDF spec's recruited-user validation pilot
  (landing page → recruit 50-100 users → 14-day measured digest → go/no-go)
  is a product decision this repo explicitly does not implement — see
  `PROGRESS.md`'s 2026-09-16 pilot-removal entry. Ship on engineering/
  editorial judgment instead.

## 2. V1 scope

**Must ship**: public web home/feed/story pages w/ SEO; iOS + Android app
sharing the core feed; USA/AP/Telangana news categories; international
student experience (F-1/CPT/OPT/STEM OPT/H-1B transition topics, student
jobs/internships, university/campus practical info, travel, student alerts);
user preferences (country, home region, topics); English/Telugu script switch;
source attribution/provenance; AI classification/clustering/summarization/
translation; human review queue for sensitive categories; saved stories;
native share w/ canonical URLs + social preview metadata; push notifications
(daily briefing + topic alerts + gated breaking alerts); admin source registry
+ editorial queue; audit log + corrections/retract workflow; privacy/terms/AI
disclosure/copyright/contact pages; basic analytics + ops monitoring.

**Explicitly out of scope for V1**: comments/discussion, user-generated
submissions, marketplace/e-commerce, direct messaging, creator monetization,
paid subscriptions, advanced social graph, realtime chat, full vector
database, OpenSearch/Elasticsearch, Redis/Celery/Kafka, native separate
iOS/Android codebases, automated publishing of immigration/legal/financial/
breaking stories, unreviewed scraping or article republishing.

## 3. UX & information architecture

- **Onboarding** (all steps skippable — "continue without login" is always
  available, nothing blocks browsing): optional country of residence; optional
  home state/region/city; optional life stage (International Student,
  Graduate/OPT, Professional, Family/Parent, Other); if International Student
  → optional study country/state/region/metro, degree level, student topics
  (no university name or immigration-document data required for
  personalization); interest selection (Immigration, Money, AP, Telangana,
  Hyderabad, Jobs, Property, Education, Parents, Travel, Community,
  Entertainment, Sports; student topics: F-1, CPT, OPT, STEM OPT, H-1B
  transition, internships, university policy, campus safety, taxes, housing,
  scholarships, travel, student community); preferred language (English or
  Telugu); notification preferences (daily briefing / topic alerts / breaking
  alerts / combination, independently toggleable per topic, quiet hours, max
  alert frequency, and a way to disable all notifications without disabling
  news access).
- **Navigation surfaces**: Home (personalized feed + daily briefing), News
  (latest high-signal stories), USA (US/NRI practical info), India (AP,
  Telangana, India), Money (FX, banking, investments, property), Community
  (events/organizations/places, editorially curated in V1), Saved, Settings
  (language, interests, notifications, privacy, delete account).
- **Story card**: every published story has a Share action (native OS share
  sheet where available, Copy Link fallback) sharing the platform canonical
  URL — never copied source article text. Share payload = canonical URL,
  language-aware title/description, rights-safe preview image when permitted,
  attribution preserved on destination page. Recommended V1 flag: "Share
  Card" — a generated rights-safe branded image (headline, 2-3 key points,
  branding, canonical URL) for messaging/social; falls back to text-only if no
  lawful image. Card elements: original editorial headline (never copied from
  a source where rights forbid republishing), country/topic/impact labels, a
  2-4 sentence original summary, an audience-specific "why this matters," a
  prominent source attribution/link when allowed, a visible
  correction/update indicator, a one-tap EN⇄Telugu toggle, and save
  (local or account-backed depending on auth state).
- **Accessibility**: WCAG 2.2 AA target on web + equivalent accessible mobile
  behavior; dynamic text size, high contrast, screen-reader labels, keyboard
  nav on web, reduced motion, ≥44pt touch targets where practical.
- **Student experience**: selecting International Student or Graduate/OPT
  surfaces a "Student Briefing" module combining immigration, education,
  jobs, money, travel, campus/community, and India/home-region stories —
  reuses the same feed/notification/content systems, no separate student
  backend. Student profile signals are explicit preferences only; never infer
  immigration/visa status or other sensitive attributes from reading
  behavior.

## 4. Bilingual / script switch

- English is the canonical editorial language; Telugu is a **derived content
  variant**, not a separate content stream. UI language and content language
  are independent settings (e.g. English UI + Telugu stories is valid).
- Controls: global language setting in Settings; per-story segmented EN|Telugu
  toggle; first-launch language preference ask that never blocks browsing; if
  the Telugu variant is unavailable or fails QA, fall back to English and mark
  Telugu unavailable; any approved English content correction invalidates the
  derived Telugu variant for regeneration; search indexes both English and
  Telugu aliases where relevant; push notifications use the localized variant
  when it exists, else fall back to English.
- Telugu quality controls: maintain a glossary of names/places/organizations/
  domain terms; never blindly translate proper nouns with a known canonical
  Telugu spelling; store translation model/version + QA status per variant;
  run automated checks for omitted numbers/dates/entities/currency/negation/
  URLs; human-review a sample of political/legal/financial Telugu
  translations during the early-launch phase.

## 5. Legal, rights & trust by design

*(Engineering control set, not legal advice — counsel must review operating
entity, source agreements, privacy notices, ad model, India/U.S. exposure, and
app-store submissions before commercial launch.)*

- **Source rights enum**: `DISABLED | LINK_ONLY | LICENSED_METADATA |
  LICENSED_REPURPOSE`. Default for every new source is `DISABLED`. An
  editor/admin must record rights evidence (source URL, terms/policy URL,
  reviewed date, reviewer, permitted fields, restrictions, territory,
  expiration if any, evidence notes) before a source can be enabled.
  **Per ADR-002 (accepted): this build phase only enables `LINK_ONLY`
  sources — `LICENSED_METADATA`/`LICENSED_REPURPOSE` are deferred until a
  future ADR supersedes it.** See
  `docs/adr/ADR-002-source-rights-approval-policy.md`.
- **V1 publication rules**:
  | Story type | Auto-publish in V1? | Required control |
  |---|---|---|
  | Low-risk general info | Yes, after automated validation + rights gate | Source rights + provenance + confidence |
  | Immigration/legal | No | Human approval |
  | Financial/investment | No | Human approval |
  | Breaking/developing | No | Human approval or explicit override |
  | Obituary/accusation/allegation | No | Human approval |
  | User-generated content | Not supported | Feature disabled |
- **Copyright-safe behavior**: prefer licensed metadata/repurpose, government/
  public-domain material, and explicit syndication/API rights; never assume
  RSS availability implies republishing rights; never copy full articles —
  the default artifact is an original summary + source attribution/link,
  subject to rights terms; store source snapshots only when permitted and
  needed for provenance, otherwise retain minimal metadata; implement a
  takedown workflow that can disable a source or story immediately.
- **Required legal/product pages**: Privacy Policy, Terms of Use, AI Content
  Disclosure, Copyright/DMCA/Takedown Policy, Corrections Policy, Community
  Standards (define future scope even though UGC is disabled), Contact/
  Privacy Request, Account Deletion request page.
- **App-store privacy/deletion**: authentication is optional in V1 (browsing
  works without an account); if account creation is enabled, implement both
  in-app deletion and a public web deletion path, and keep Apple App Store
  privacy disclosures and Google Play Data Safety/account-deletion
  disclosures accurate (see links in `docs/SPEC.md` §14 references below).
- **India legal review**: track India-specific applicability of the DPDP
  Act/Rules, IT Rules / digital-media provisions, and grievance/contact
  requirements, plus any foreign-investment/entity issues, with counsel. Do
  not infer obligations from this spec alone.

## 6. Content source registry & rights workflow

- **Initial source strategy**: start with 3-5 sources whose permission model
  is clear enough to approve quickly — official government feeds, explicit
  APIs/licensed feeds, public-domain/explicitly-permissive sources. Do not
  start with a large list of commercial publishers.
- **Source fields**: `id, name, base_url, feed_url, source_type, country,
  language, rights_status, rights_evidence_url, rights_reviewed_at, reviewer,
  refresh_minutes, active, fail_count, last_success_at, last_error_at`.
- **Adapter contract**: `fetch() -> RawItems`, `normalize(raw_item) ->
  NormalizedItem`, `validate(normalized_item) -> ValidationResult`,
  `emit(normalized_item) -> SourceItem`.
- **X (Twitter) official-channel adapter**: V1 may ingest posts from a
  curated allowlist of verified/approved official X accounts (government
  agencies, regulators, elected offices, universities, official Telugu
  community orgs, other high-trust channels). An admin must explicitly
  approve each account and store its stable X user ID. Use the official X API
  user-posts timeline endpoint `GET /2/users/{id}/tweets` (pagination,
  exclusion filters, `since_id`/time filtering) per current X API/SDK docs —
  never scrape the public X website. X content is a **source signal, not
  automatic republication permission** — the same rights-status gate applies
  as any other source. Store X post ID, canonical X URL, author/handle,
  `created_at`, and permitted metadata; do not copy full post text/images/
  video into the published story unless current X Developer Terms/API policy
  and any applicable rights explicitly permit it. Workflow: fetch → rights
  gate → dedupe by X post ID → classify → link/create story cluster →
  evidence checks → draft original summary from permitted evidence →
  validation → editorial review when required → publish/notify. **A single X
  post must never bypass review just because the account is official.**
  Polling: high-priority official accounts may use a 1-5 minute cadence where
  permitted; persist `since_id`/`last_success_at`; fetch incrementally; back
  off on 429/errors; expose account health in admin. Treat cadence as a
  target, not a guarantee. X API pricing is pay-per-use (Post reads priced
  per-resource; a self-serve monthly Post-read cap and daily resource
  deduplication for billing apply per X's docs) — set an explicit monthly X
  budget and pause/reduce low-priority polling when the threshold is reached.
  If X API access is unavailable, do not scrape around the restriction — set
  the source to `DISABLED` or keep it `LINK_ONLY` until approved access is
  restored. Reference docs (verify current terms before production config):
  `docs.x.com/x-api/posts/timelines`, `docs.x.com/x-api/getting-started/pricing`,
  `docs.x.com/x-api/fundamentals/post-cap`.
- **Ingestion states**: `DISCOVERED -> RIGHTS_BLOCKED | NORMALIZED -> DEDUPED
  -> CLUSTERED -> ENRICHED -> REVIEW | SCHEDULED -> PUBLISHED -> UPDATED |
  RETRACTED`.
- **Source failure handling**: exponential backoff for transient errors;
  circuit breaker after repeated failures; health state visible in the admin
  dashboard; never duplicate a story when the same source item reappears; no
  infinite retry loops — use bounded retries and a failed-job record.

## 7. AI news pipeline

- **Pipeline**: `Fetch -> Parse -> Rights Gate -> Normalize -> Fingerprint ->
  Deduplicate -> Cluster -> Relevance -> Evidence -> Generate -> Validate ->
  Review/Publish -> Translate -> Index`.
- **Model routing**: product code calls internal task interfaces through an
  internal AI gateway — **never** provider SDKs directly.
  | Task | Default routing | Escalation |
  |---|---|---|
  | Language detection | Small/cheap model or deterministic library | None |
  | Relevance + categorization | Low-cost fast model | Higher-quality model on uncertainty |
  | Dedup/clustering | Fingerprint + lexical similarity first | Embedding/model only for ambiguous pairs |
  | Summary | Low-cost fast model | Quality model if validation fails |
  | "Why this matters" | Low-cost fast model | Quality model for high-value stories |
  | English → Telugu | Low-cost translation model | Second provider / human sample review |
  | Sensitive validation | Higher-quality reasoning model | Human review always in V1 |
- **Structured output contract**: `{ relevant, confidence, categories[],
  countries[], entities[], sensitivity, urgency, summary_en, why_matters_en,
  claims[], source_refs[], publish_recommendation }`.
- **Claim evidence**: every important claim must point back to one or more
  source references. High-risk categories show claims and supporting sources
  side by side in the review UI.
- **AI failure behavior**: schema validation failure → retry once with a
  constrained prompt → otherwise hold; low confidence → review queue;
  unsupported factual claim → remove claim or hold the story; model
  unavailable → do not invent content, queue for later; provider cost
  threshold hit → degrade to classification-only mode rather than exceeding
  budget.

## 8. Personalization & ranking

- **Preference model**: `residence_country, residence_region, home_state,
  home_city, topics[], language, notification_mode`.
- **Ranking formula** (V1 must be deterministic and explainable):
  `score = 0.28*residence + 0.20*home + 0.18*topic + 0.16*freshness +
  0.14*importance + 0.04*source_quality - repetition_penalty`.
- **"Why this matters"**: generate once per story/audience segment, then
  cache — never generate a custom LLM answer on every feed request.
- **Explainability**: every personalized recommendation must be attributable
  to an explicit signal, e.g. "Because you live in the USA and follow
  Immigration."

## 9. Product surfaces

- **Web**: home/feed, story detail, topic page, country/region page, search
  results, saved, about, privacy/terms/takedown/corrections/AI-disclosure,
  account deletion, 404/500.
- **Mobile** (iOS + Android from one React Native/Expo codebase): onboarding,
  home, topic/category feeds, story detail, search, saved, notifications
  inbox, settings, language switch, privacy + delete account.
- **Admin**: dashboard, sources/rights, ingestion health, review queue, story
  editor, evidence viewer, publish/schedule/retract/correct, translation
  status, notifications, audit log, feature flags, system health.

## 9.4 Sharing & notification delivery

- Topic alerts: a story is eligible only when it matches at least one
  topic/geography/entity preference the user actually selected and passes the
  notification quality threshold. A user must never get a topic alert for an
  unrelated category merely because it is high-engagement content.
- Breaking alerts are a **separate path** from topic alerts — sendable
  without an explicit topic subscription only when urgency, confidence,
  policy, source quality, and editorial thresholds all pass. Sensitive
  categories remain human-gated in V1.
- Notification controls: per-topic toggles, breaking on/off, daily-briefing
  on/off, quiet hours, max alerts/day, and notification history. Defaults
  favor low frequency and high relevance.
- Student and official-channel (X) alerts are independently optional and
  match against explicit user-selected topics/entities/life-stage, applying
  the same quality threshold, quiet hours, daily caps, and deduplication as
  any other notification.
- **Delivery targets**: priority sources polled every 1-5 min where
  permitted; normal sources processed to a story within 15 min of discovery;
  breaking candidates evaluated within 3 min of discovery; approved breaking
  pushes dispatched within 1 min of approval.
- **Deep links**: every notification carries a destination type/id and must
  open the intended story/topic page; if the destination is retracted,
  expired, or unavailable, fall back to the notification inbox or home feed.
- **Analytics events**: `story_share, share_channel (when known),
  notification_received, notification_open, notification_skipped_due_to_quiet_hours,
  notification_suppressed_by_daily_cap, notification_failed`. Never send an AI
  request per notification recipient.

## 10. Technical architecture — V1 single source of truth

| Layer | V1 choice | Why |
|---|---|---|
| Web | Next.js + TypeScript | SEO, SSR/ISR, shared contract types |
| Mobile | Expo + React Native + TypeScript | One mobile codebase for iOS/Android |
| API | FastAPI + Python | Strong data/AI ecosystem, typed API |
| DB | Managed PostgreSQL (Supabase acceptable) | Reliable, cheap, SQL search, backups |
| Search | Postgres FTS + pg_trgm | Avoid a separate search cluster in V1 |
| Jobs | Postgres job table + scheduled worker | Avoid Redis/Celery operational cost |
| Storage | S3-compatible object storage | Images/exports/log artifacts |
| CDN/DNS | Cloudflare or equivalent | Cache, TLS, rate limiting |
| Push | FCM + APNs through Expo/React Native tooling | Native delivery |
| Analytics | PostHog or equivalent | Product analytics + feature flags if desired |
| AI | Internal provider gateway | Avoid vendor lock-in |
| Monitoring | Sentry + structured logs | Error visibility without a heavy platform |

**Deliberately NOT in V1**: No Redis. No Celery. No OpenSearch. No Kafka. No
Kubernetes. No microservice fleet.

**When to add them later**: add OpenSearch only if measured search latency,
ranking quality, or indexing volume exceeds Postgres's limits; add Redis only
if job throughput, caching, or rate limiting can't be handled economically
with Postgres/CDN; split services only when independent scaling or
deployment cadence justifies the operational cost.

## 11. Monorepo layout

```
apps/
  web/                # Next.js public site
  mobile/             # Expo iOS + Android
  api/                # FastAPI
  admin/              # Next.js admin
packages/
  contracts/          # OpenAPI-derived/shared types
  ui/                 # shared design tokens/components where practical
  config/             # lint/tsconfig/eslint shared config
  ai/                 # provider gateway + task contracts
  domain/             # shared business rules/types
infra/
  migrations/
  scripts/
docs/
  adr/
  legal/
  runbooks/
tests/
  fixtures/
  e2e/
```

**Engineering rules**: strict TypeScript, no `any` in application code unless
justified; Python typed + linted + formatted; OpenAPI generated/validated on
every API build; database migrations are immutable once applied — new
changes use new migrations; no direct DB access from clients; business rules
live in domain/application layers, not UI components; every external
integration has a timeout, retry, metrics, and a failure state; every
background job is idempotent.

## 12. Core data model

| Entity | Key fields |
|---|---|
| User | id, email/auth provider id, created_at, deleted_at |
| Profile | user_id, residence_country, residence_region, home_state, home_city, language, notification_mode |
| Topic | id, slug, name, active |
| UserTopic | user_id, topic_id, weight |
| Source | id, name, feed_url, rights_status, rights_evidence, active, health |
| SourceItem | id, source_id, external_id, url, title, published_at, raw_hash |
| Story | id, canonical_slug, status, sensitivity, importance, published_at, updated_at |
| StoryVariant | story_id, language, headline, summary, why_matters, generated_at, model_version, qa_status |
| StorySource | story_id, source_item_id, role, evidence_rank |
| StoryEntity | story_id, entity_id |
| Entity | id, type, canonical_name |
| EntityAlias | entity_id, alias, language |
| StoryTopic | story_id, topic_id, weight |
| ReviewTask | id, story_id, reviewer_id, reason, status, decision |
| Correction | id, story_id, reason, old_text_hash, new_text_hash, created_by |
| Notification | id, user_id, story_id, type, sent_at, status |
| Job | id, type, payload, status, attempts, run_after, locked_at, last_error |
| AuditEvent | id, actor, action, entity_type, entity_id, metadata, created_at |

**Publication state machine**:
```
DRAFT -> AI_READY -> REVIEW_REQUIRED -> APPROVED -> SCHEDULED -> PUBLISHED -> UPDATED
PUBLISHED -> RETRACTED
UPDATED -> CORRECTION_PENDING -> UPDATED
```

## 13. API contract

**Public**: `GET /v1/home`, `GET /v1/stories`, `GET /v1/stories/{slug}`,
`GET /v1/topics/{slug}`, `GET /v1/search?q=...`, `GET /v1/config`,
`GET /v1/stories/{slug}/share-meta`.

**Authenticated**: `GET /v1/me`, `PATCH /v1/me/preferences`,
`POST /v1/me/saved/{story_id}`, `DELETE /v1/me/saved/{story_id}`,
`POST /v1/me/push-tokens`, `DELETE /v1/me/account`.

**Admin**: `GET /v1/admin/sources`, `PATCH /v1/admin/sources/{id}`,
`GET /v1/admin/review-queue`, `POST /v1/admin/stories/{id}/approve`,
`POST /v1/admin/stories/{id}/reject`, `POST /v1/admin/stories/{id}/retract`,
`POST /v1/admin/stories/{id}/correct`, `GET /v1/admin/jobs`,
`GET /v1/admin/audit`.

**Error envelope**: `{ "error": { "code": "SOURCE_DISABLED", "message":
"Source is not approved", "request_id": "..." } }`.

## 14. Background jobs & automation

**V1 jobs**: `source_fetch, x_official_account_fetch, source_normalize,
story_fingerprint, story_cluster, ai_classify, ai_summarize, ai_translate,
story_validate, review_reminder, publish_scheduler, notification_dispatch,
cleanup, health_check, backup_verify`.

- X job behavior: claim due accounts, fetch only new posts using `since_id`
  where supported, persist usage/cost telemetry, dedupe, enqueue evaluation,
  update account health; never poll disabled or budget-blocked accounts.
- Priority-source scheduling: `source_fetch` supports a per-source cadence
  including a 1-5 minute cadence for approved priority feeds/official
  alerts; the system must respect each source's rate limits and terms —
  cadence is a configuration target, not a guarantee if a source disallows
  frequent polling.
- Notification worker: batch users, compute story-level eligibility once,
  match against deterministic preferences, apply quiet hours and daily caps,
  deduplicate by `user_id + notification_key`, dispatch through the push
  provider, persist delivery status; retries use capped backoff and must
  never create duplicate notifications.

**Postgres job pattern**: a `jobs` table with `status, run_after, attempts,
lock_expiry, dedupe_key`; workers claim jobs using transactional row
locking; scheduled invocation can be a managed cron trigger or one
lightweight always-on worker depending on the deployment platform.

**Idempotency**: each source item gets a stable dedupe key; each story
generation task uses `story_id + variant + generation_version` as its
idempotency key; notification sends use `user_id + notification_key`;
publish transitions reject duplicate transitions.

**Automation guardrails**: budget guard stops expensive AI tasks when the
daily/monthly spend threshold is crossed; source guard auto-disables a
source after repeated structural/feed failures; content guard can stop
auto-publish globally or per category; translation guard pauses Telugu
generation if the QA failure rate spikes.

## 15. Admin / editorial workflow

- Review priority: **P0** (breaking/legal/immigration/financial) = immediate
  human review; **P1** (high importance/confidence) = review if configured;
  **P2** (normal low-risk) = auto-publish after validation; **P3**
  (low-value/duplicate) = archive/ignore.
- Review screen shows: source + rights state, original metadata, story
  cluster, claim/evidence pairs, AI draft, EN/Telugu variants, sensitivity
  labels, publish controls, correction/retract controls, audit trail.
- Operator kill switches (config/env-style flags): `AUTO_PUBLISH_GLOBAL`,
  `AUTO_PUBLISH_CATEGORY_IMMIGRATION`, `AI_TRANSLATION_ENABLED`,
  `PUSH_NOTIFICATIONS_ENABLED`, per-source `SOURCE_<id>_ENABLED`.

## 16. Security, privacy, reliability

- **Baseline**: TLS everywhere, managed secret store, MFA for admin sessions
  with short-lived tokens, RBAC, rate limiting on auth/search/admin, input
  validation/output encoding, signed webhook verification, dependency
  scanning, SAST in CI, encrypted backups.
- **Privacy**: no-account browsing by default, coarse geography only, no GPS
  in V1, no data sale, separate analytics consent, retention schedules,
  cross-system deletion job.
- **Reliability targets**: API availability 99.5%/month; feed P95 < 800ms
  cached / < 1.5s uncached; story page < 1.5s; job success 95% on first
  attempt or retry; zero known duplicate publishes at release; daily backups
  + a monthly restore test.

## 17. Analytics & validation

- **Core events**: `app_open, feed_view, story_open, story_save,
  story_share, language_switch, search, notification_open,
  notification_opt_in, onboarding_complete, account_delete_request,
  report_issue`.
- **North star**: weekly retained users who consume ≥1 personalized story
  and return on another day. Supporting metrics: notification open rate,
  saves/active user, story completion, language-switch usage, zero-result
  search rate, correction rate, AI hold rate.
- **Experiment candidates**: headline format, "why matters" placement,
  briefing timing, notification frequency, onboarding questions, EN/Telugu
  default, home-vs-local content mix.
- **Cost telemetry**: AI tokens/cost by task/provider/source/story/day;
  infra cost proxies (requests, egress, storage, image transforms).

## 18. Testing & AI evaluation

- **Layers**: unit (ranking/rights/state machines/dedupe), integration
  (feeds/DB/AI gateway), OpenAPI contract tests, web E2E, mobile smoke/E2E,
  security/dependency scanning, load testing (feed/search), accessibility,
  AI regression suite.
- **Golden AI test set**: ≥30 human-reviewed representative stories
  (politics, money, immigration, entertainment, AP, Telangana, US, common
  names, numbers, multilingual) with expected labels/facts/entities/
  translation invariants; run on every prompt or model change. The set may
  grow past 30 only with items that have passed the same human review — see
  ADR-013.
- **Release gates**: no P0/P1 security defects; all critical migrations
  pass; no rights-disabled source can publish; no sensitive-category story
  bypasses review; an English correction invalidates the stale Telugu
  variant; account deletion works end-to-end; notification dedupe works;
  rollback verified; backup restore verified; AI eval does not regress
  beyond an agreed threshold.

## 19. Cost-control design

- **Goal**: keep the service free to users, minimize operator spend, keep
  ops complexity low, reuse cached content, generate-once wherever possible.
- **Levers**: AI (cheapest viable model first, generate once per
  story/segment), Search (Postgres before any search cluster), Jobs
  (Postgres before Redis), Images (optimize/cache), Notifications
  (only high-signal sends), Hosting (managed + autoscale + CDN), Analytics
  (sample high-volume events). A user-facing AI chat assistant is explicitly
  **not** in V1 and, if ever added, requires an explicit per-user budget and
  rate limit.
- **X API cost controls**: curated allowlist with per-account priority,
  shortest permitted polling interval, track `x_api_posts_read`,
  `x_api_cost_estimate`, `x_api_budget_remaining`, and rate-limit errors;
  downgrade lower-priority polling first when thresholds are hit; always
  fetch incrementally via `since_id`, never re-fetch full timelines.
- **Budget config**: `MONTHLY_AI_BUDGET_USD`, `MONTHLY_INFRA_BUDGET_USD`,
  `DAILY_AI_ALERT_USD`, `AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH=true`.

## 20. Development workflow (build order)

1. Product validation landing page + analytics
2. Repo scaffolding, CI, environments, contracts
3. DB schema + seed + admin auth
4. One permitted source → normalized item → story → publish → web
5. AI classification + summary + evidence validation
6. Review queue + corrections + rights controls
7. English/Telugu variants
8. Mobile app consumes same API
9. Personalization + push
10. Hardening, observability, load/accessibility/security tests

**Vertical slice definition**: one permitted source produces a
rights-approved story, passes relevance/validation, creates EN+Telugu
variants, appears in the web+mobile feed, can be opened/saved/attributed/
corrected/retracted — all with audit events. This is the milestone to prove
before broadening source count or feature surface.

See `docs/BUILD_ORDER.md` and `docs/tickets/` for the concrete ticket
breakdown Codex/Claude Code should execute against.

## 21-23. Ticket list, master build prompt, behavior rules

Moved to their own files so a working session only loads what it needs:
- Ticket definitions: `docs/tickets/*.md` (index in `docs/tickets/README.md`)
- The literal Codex master build prompt: `docs/CODEX_BUILD_PROMPT.md`
- Stop conditions and required ADRs: `docs/NON_NEGOTIABLES.md` and `docs/adr/`

## 24. Production ops & bug-proofing

- **Preventative**: feature flags for risky features, DB constraints for
  impossible states, typed API contracts, centralized error handling,
  idempotent jobs, timeouts everywhere, circuit breakers for flaky
  sources/providers, graceful empty/error states, offline/cache handling on
  mobile, capped-backoff retries, audit events for all admin mutations.
- **Incident modes** (each a step down from the last): Normal (all
  automations run) → AI degraded (fallback models, hold low-confidence
  output) → Source degraded (disable the failing source, continue others) →
  Editorial emergency (auto-publish off, notifications restricted) →
  Read-only (public reading only, mutations disabled) → Full lockdown
  (admin-only, publishing disabled).
- **Correction policy**: every published story supports update/correct/
  retract; the public UI shows an updated/corrected indicator; the audit log
  retains who/what/when; translation variants are revalidated when source
  content changes.

## 25. Deployment

- **Environments**: local → preview/staging → production.
- **CI gates**: format/lint, typecheck, unit tests, integration tests,
  OpenAPI diff check, migration validation, build web/mobile/API,
  dependency/security scan, E2E smoke tests.
- **Principle**: managed hosting + one-click rollback; migrations are
  forward-only and backward-compatible where practical; app/API version
  compatibility is preserved across rolling deploys.
- **Store readiness**: Apple/Google privacy disclosures match actual runtime
  data collection; account deletion is implemented before account creation
  is enabled; support/privacy/deletion URLs are live and stable; store
  screenshots/metadata are accurate.

## 26. Launch checklist (acceptance criteria highlights)

See `docs/NON_NEGOTIABLES.md`
for the full release-gate list, including: native share with Copy Link
fallback everywhere; shared URLs resolve to the canonical page with correct
social metadata (no preview image if rights aren't established); priority
sources configurably pollable at 1-5 min with freshness observable in admin;
normal stories live within 15 min of discovery; topic alerts only match
subscribed topics plus quality/quiet-hour/daily-cap/dedup rules; breaking
alerts use a separate threshold, never triggered by topic match alone;
notification history/deep-links work on iOS/Android/web and fail gracefully
for retracted destinations; landing-page validation shows repeat engagement;
3-5 source rights approvals documented; no `DISABLED` source can publish;
legal/privacy pages counsel-reviewed where required; admin review staffed
for sensitive categories; EN/Telugu QA passes thresholds; backup restore +
account deletion tested; app-store forms accurate; notification opt-in/quiet
controls work; topic toggles persist per-device after sign-in;
broken-source/AI-failure/cost-guardrail/correction-retraction failure modes
simulated and pass; student onboarding/briefing/topics/independent alerts
work on web + both mobile platforms; X polling fetches only new posts via
`since_id` without bypassing rights/editorial gates; admin shows X account
health/poll state/`since_id`/errors/cost/active state; X budget guard
reduces/pauses low-priority polling without taking unrelated ingestion
offline; no `DISABLED` X source publishes and X-derived stories preserve
canonical attribution; performance/accessibility/security release gates
pass.

## 27. 90-day post-launch roadmap

- **Days 0-14**: fix reliability issues, monitor source quality, validate
  onboarding/notifications.
- **Days 15-30**: improve ranking, search, Telugu glossary, source coverage.
- **Days 31-60**: add 1-2 new countries, stronger local community discovery,
  richer daily briefing.
- **Days 61-90**: evaluate OpenSearch/Redis only if metrics justify it; test
  monetization pilots without charging users.
- **V1.1 guidance**: measure share rate by channel/topic before investing in
  direct WhatsApp APIs, social publishing automation, or advanced referral
  mechanics — rely on the OS share sheet first.
- **Explicitly not V1 or near-term**: Canada/Australia/UK/Middle East
  profiles, India-first mode, moderated community submissions, local
  business directory, jobs marketplace, travel tools, an interactive AI
  assistant with per-user budgets, premium sponsorship/ads, advanced
  semantic search, personalized newsletters.

## 28. Legal/platform reference links

*(Verify current terms before production config — these change.)*
- X API: `docs.x.com/x-api/posts/timelines`,
  `docs.x.com/x-api/getting-started/pricing`,
  `docs.x.com/x-api/fundamentals/post-cap`.
- App stores: Apple App Review Guidelines and account-deletion docs; Google
  Play User Data/Privacy policy, account-deletion docs, and Data Safety
  section.
- India: MeitY Act & Policies, India DPDP Rules 2025.
- **Disclaimer**: this spec is not a legal opinion. Counsel must review
  source licensing, corporate structure, data protection, advertising,
  defamation, copyright, tax, consumer protection, and jurisdiction-specific
  obligations before public launch.

## Appendices

- **A — Sample content object**: `story_id, status, sensitivity, importance,
  topics[], countries[], variants: {en, te}, sources[], claims[]`.
- **B — Sample EN/Telugu UI strings**: Home, Latest, "Why this matters",
  "Read in Telugu/English", Saved, Settings, "Important for you" — maintain
  the full string table in the i18n resource files, not in this doc.
- **C — Recommended initial team**: Founder/Product (validation, policy,
  launch owner); Codex/engineering agent (builds code/tests/docs); Human
  editor (approves sensitive stories and corrections); Legal counsel
  (rights/privacy/terms/jurisdiction); Designer (optional, post-functional-
  flow).
- **D — Final authority rules**: this V5.2 spec plus its recorded ADRs is
  the sole authority for V1. V3/V4 specs are historical only and must never
  be loaded into Codex/Claude Code as active instructions. Conflict
  resolution order: (1) an explicit rule in this document, (2) an approved
  ADR, (3) the safest implementation that preserves the constraints here —
  then stop and record an ADR if the gap is material.
