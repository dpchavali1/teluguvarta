# The Telugu Edit: engineering, product, operations and AI-cost review

Review date: September 29, 2026 (America/Chicago).

## Assessment and scope

The modular monolith is appropriate for this project. PostgreSQL search and jobs, a single AI gateway, shared contracts, deterministic ranking, bilingual fallback, MFA, and editorial audit events are useful foundations. The immediate investment should be content reliability, evidence validation, spend controls and operational visibility. More infrastructure or a visual redesign would not resolve the current bottleneck.

Reviewed local source, current progress, build order and non-negotiables, plus the public website at phone-width viewport: home, story detail, English/Telugu switching, latest, and entertainment. Latest displayed exactly two entries and no older-page link. Entertainment displayed no published stories. Both stories came from NPR. The lead story repeats its headline as its summary and has no why-matters section. Telugu switching worked for both displayed stories.

This is a source and public-experience review, not a penetration test. No production credentials, private database, provider invoice or server logs were accessed. The installed phone binary was not operated; mobile findings derive from current source and tests and may differ from that binary. A direct public API browser request was blocked by the browser; website observations remain valid. Production flags, source health, current backlog counts and deployed revision require verification. No implementation, publishing, source permissions or production settings were changed. Proposed architecture/product/security changes require the repo's ADR process where applicable.

## Why only two stories

This appears to be a content/publication bottleneck shared by web and phone, rather than a phone-only display defect. The precise current production cause is not proven.

PROGRESS.md records that two previously held stories were manually drafted, approved, and published. It also records earlier missing paid-provider holds and schema-validation failures; the schema prompt fix was subsequently deployed and translation succeeded. Those historical issues must not be reported as still broken without fresh logs. Existing NO_PAID_PROVIDER stories are not automatically returned to generation when a key is added: generation selects DRAFT stories whose items are CLUSTERED, while held stories are REVIEW_REQUIRED with REVIEW items. New successful generation still does not imply publication: sensitive stories require human approval, and normal stories go to review when global auto-publication is off unless they qualify for the accepted brief lane.

First production investigation should produce a funnel, not bypass safeguards:

1. Record deployed revision, migrations, worker heartbeat and enabled routes/flags without exposing keys.
2. Count active, rights-reviewed sources; inspect last successful fetch and circuit breakers.
3. Count items by ingest_status and stories by status, source, age and review reason.
4. Inspect recent AI calls by task/status/model, including successful classification and summary since the schema fix.
5. Inspect pending/failed jobs and oldest due job; compare SCHEDULED stories with publication latency.
6. Triage old holds through an explicit supported recovery operation that preserves audit, sensitivity review and idempotency. Adding a key alone does not recover them.
7. Verify one newly fetched, permitted item through cluster, classification, draft, review/eligible brief, publication and Telugu QA.

## Findings and recommended modifications

P1 means high priority before expanding automated publication or ingestion. P2 means the next improvement tranche. These are review priorities, not new acceptance requirements.

### 1. P1 — Recurring sweeps bypass bounded story-level AI retries

Evidence: apps/api/app/jobs/generate.py:_generate_story and generate_stories; apps/api/app/jobs/translate.py:_translate_story and translate_stories. HOLD, UNAVAILABLE and DEFERRED return without persistent attempt limits or next-attempt time for the story/task. Each new time-bucketed sweep can call again. Queue attempts are bounded for a job, but each sweep is a new job. Successful classification is repeated if summary fails; budget degradation can repeat classification indefinitely.

Fix: persist attempts, next_attempt_at, failure class and input/content version per story/task in PostgreSQL. Cache successful classification for that version. Back off transient errors, honor quota retry timing, and route permanent invalid results/configuration to an actionable hold. Permit audited manual recovery. Add tests spanning multiple distinct sweep windows, not just retries of one queue row.

### 2. P1 — Monthly AI budget is a degradation threshold, not a total spend ceiling

Evidence: app/ai/tasks.py:DEGRADABLE_ON_BUDGET_BREACH excludes classification; gateway checks accumulated cost before calls, without reserving projected cost, and does not repeat that check before its schema retry. Concurrent future workers can race. DAILY_AI_ALERT_USD is an alert, not a daily blocking limit.

Fix: retain the accepted classification-only degradation policy only inside a separately bounded classification allocation. A true overall paid-call ceiling needs an ADR. Reserve estimated maximum cost atomically, impose output limits, reconcile actual usage, and enforce per-day/per-month plus per-task limits. Refuse unsafe/missing budget configuration at production startup. Use a provider-side project spend cap as a second guard; Google documents delayed billing and possible overages, so neither control should promise an exact zero-overrun guarantee.

### 3. P1 — Gemini billing telemetry can undercount usage and omit billed failed responses

Evidence: app/ai/providers/gemini_provider.py:73-77 records promptTokenCount and candidatesTokenCount only. Thinking-token usage is not added. json.loads runs before a ProviderResponse is returned, so malformed JSON raises outside gateway schema handling and no usage log is written for that response. Provider failures are also not uniformly logged.

Fix: preserve usage independently of parse success, include billed thinking tokens according to the provider's metadata, distinguish cached input if caching is enabled, record parse/transport/blocked statuses, and reconcile estimated cost against billing. Test malformed JSON, safety blocks, thinking usage and schema retries. Pricing is model/provider-specific already, which is good.

### 4. P1 — Auto-brief headline is not checked for invented facts

Evidence: app/jobs/brief_lane.py:_check_brief checks headline similarity, then applies title_match to brief_en and claim text, not headline_en. An original-looking headline can introduce an unsupported name/number/context while the body passes. Title word overlap also cannot prove semantic entailment; valid source IDs are provenance checks, not proof a claim is supported.

Fix: apply evidence validation to headline and body, and validate each claim against its own cited titles rather than the union of every claim's citations. Keep uncertain cases in review. Add negative cases with invented headline numbers/names, changed negation, reversed relationships and wrong per-claim attribution. Do not expand auto-publication until these pass.

### 5. P1 — Telugu QA accepts changed and added numbers

Evidence: app/content/qa.py:find_qa_issues uses substring presence. Direct reproduction: find_qa_issues('5 people', '50 మంది') returns []; '5 మంది, 100 కేసులు' also returns []. It checks whether required numbers survived, not whether the translated numeric facts stayed identical. Negation checks are presence-based, and a missing why_matters_te is not checked when the English field exists.

Fix: compare normalized numeric tokens/multisets with boundaries and currency/date context; reject added/changed numeric facts; require canonical nonempty fields and corresponding why-matters when present. Add a Telugu-script sanity check. Strengthen negation tests and retain native-speaker review for semantic fidelity. Deterministic QA is valuable but should not be presented as comprehensive translation accuracy.

### 6. P1 — Current published content does not deliver the promised full-story experience

Evidence: both live stories repeat their headline as summary and have no why-matters text. Neither displayed a Brief badge. Manual drafting requires only nonblank headline and summary; why_matters is optional. GenerationResult also allows empty strings. The full-story similarity check checks summary, while the prompt is the main original-headline safeguard.

Fix: validate publication by format: FULL requires a useful original summary and why-matters; BRIEF follows ADR-019 and carries its label. Flag duplicate headline/summary and source-headline reproduction. Enforce validation centrally for manual approval, auto approval and final publication, with consistent admin feedback. Review existing two stories manually. Rights decisions must follow accepted ADRs; source link titles and own headlines are distinct surfaces.

### 7. P1 — Rights are not rechecked at final publication

Evidence: app/jobs/publish.py:auto_publish_stories global path and publish_due_stories contain no source-rights recheck. Admin approve checks English content, not current rights. Brief lane has an explicit rights check; ordinary ingest emission has one too. A source can be disabled after an item was emitted but before a queued story publishes.

Fix: validate current permitted source rights before every approval/publication transition, with tests disabling a source between ingest, approval and scheduled publication. Define in an ADR what revocation means for already-published mixed-source stories and cache invalidation; do not invent removal rules or assume an inactive polling source is equivalent to revoked rights.

### 8. P1 — Unbounded AI batches can block publication and outlive the job lease

Evidence: generate_stories and translate_stories select all eligible rows; the worker runs one handler synchronously. Queue lease is 300 seconds, while each Gemini request allows 60 seconds and may retry. A backlog can monopolize the worker, delay publishing/push/alerts, and exceed the lease. A second worker could reclaim that still-running job; crash recovery can repeat paid calls. claim_job also increments attempts on expired-lease reclamation without filtering attempts against the maximum.

Fix: small bounded batches or durable per-story jobs on the existing PostgreSQL queue, explicit stage checkpoints, fair scheduling and lease renewal/ownership checks. Recover failed database transactions before recording failure; worker currently calls fail_job on the same session without rollback, which can itself fail after a flush error. Add long-running, crash and database-error recovery tests before increasing workers.

### 9. P1 — Production recovery and readiness need evidence

Evidence: PROGRESS.md says encrypted offsite backups/restore drill were not yet run on the server in the recorded ops pass. Compose healthchecks only PostgreSQL; /health returns static ok without checking dependencies. deploy.sh's health loop can exhaust all attempts and still continue to print completion.

Fix: verify whether backups are now configured; prove offsite delivery and a restore, including preservation of MFA decryption material. Make deploy fail on health timeout, add database readiness and independent worker-heartbeat/oldest-job monitoring, plus web/admin smoke checks and documented rollback compatible with migrations. Alert externally when the worker dies: alerts running inside that worker cannot detect its complete absence. Keep the single VPS for current scale, accepting its availability tradeoff.

### 10. P2 — Geography and importance are misleading inputs

Evidence: content/serialize.py derives countries from Source.country. Live UK-base story displays US because its publisher is US-based. generate.py assigns classification.confidence to story.importance, mixing certainty with editorial significance; generated countries are not persisted.

Fix: separate event geography, publisher origin and audience relevance, with explicit schema/ADR decisions. Separate classification confidence from importance. Test UK events from US publishers and high-confidence low-importance items. This improves ranking and displayed badges without making ranking an LLM task.

### 11. P2 — Product coverage and topic hierarchy exceed available inventory

Evidence: the live header exposes 26 alphabetically ordered topics, beginning with Andhra Pradesh, CPT and Campus Safety. Entertainment is empty. Only two general US stories are published. PROGRESS.md records Telugu360 as seeded but not created in production at that point; seed additions do not update an existing installation automatically.

Fix: rights-review and activate a small balanced source set for Telugu regional news, diaspora/community, useful US updates and entertainment/sports where permitted. Show populated/relevant topics first; leave the full taxonomy discoverable, including student topics. Add topic counts and helpful empty-state routes to existing content. Choose a sustainable editorial daily target rather than filling the app with unrelated or stale items. Do not bypass sensitive review or reuse prohibited source text to create volume.

### 12. P2 — Translation work is spent before editorial selection

Evidence: translate_stories has no story.status restriction. It can translate rejected/archived/retracted stories that have English and no Telugu. The brief lane can overwrite the full English draft and delete the already-paid Telugu translation, causing another translation.

Fix: establish the final English format and approval first, then translate APPROVED/SCHEDULED/PUBLISHED/UPDATED content with version-aware invalidation. Prioritize newly approved material. Preserve fallback and editorial needs; changing the accepted lifecycle/order requires an ADR. Rejected stories should not silently incur translation cost.

### 13. P2 — Public personalization can schedule additional paid AI work

Evidence: routers/public.py:get_home enqueues missing segment explanations for returned stories. Cache deduplication is good, but anonymous preferences can request supported segments; WHY_MATTERS generation does not pass the story privacy decision, so it cannot use the allowed free route. _prompt interpolates headline/summary without the untrusted-data boundary used elsewhere.

Fix: cap segment-generation spend and make demand-triggering abuse resistant. Evaluate whether generic approved explanations are sufficient for early launch; disabling/removing an accepted feature needs owner/ADR review. Use untrusted-data encoding consistently and supported privacy routing. Make the metric cost per published story include this downstream work.

### 14. P2 — Mobile feed discovery, refresh and accessibility need device validation

Evidence: HomeScreen loads on mount and pull-to-refresh, with no focus/resume refresh. Its bounded home response has no older-stories control and MainTabs lacks Latest, though topics have pagination. Tab icons use font glyphs. Some TopicScreen/StoryList empty/error Text styles use default colors, risking dark-theme readability.

Fix: add bounded resume/focus freshness, a discoverable Latest/all-stories path, consistent icon assets within the accepted design system, and theme-aware empty/error states. Test release Android/iOS builds for large text, TalkBack/VoiceOver, Telugu wrapping, safe areas, offline recovery, links, save/delete and real push. Rebuild the installed APK with the new domain URLs; PROGRESS.md records an old sslip.io API URL still used by the installed build. Current app configuration has a custom scheme but no HTTPS universal/app-link declarations; evaluate verified links via ADR if desired.

### 15. P2 — Security hardening has specific remaining gaps

Evidence: admin bearer token is in localStorage; role comes from JWT claims without a current database role/account check. Native anonymous-token fallback uses Math.random and credentials are in AsyncStorage. The backend accepts arbitrary nonempty tokens and creates users. Feed probe checks public DNS/body bounds, while the actual RSS fetch reads response.content without equivalent URL/size enforcement.

Fix: evaluate HttpOnly secure cookie admin sessions and revocation through an ADR, or document residual token-theft exposure while enforcing a strict CSP and XSS discipline. Use OS cryptographic random and secure credential storage on mobile; bound/validate tokens and rate-limit user creation. Apply a shared SSRF/DNS/response-size policy to actual fetches, not only the optional feed probe. Verify trusted reverse-proxy behavior for client-IP limiting. These are exposure paths found in code, not evidence of compromise.

### 16. P2 — SEO sitemap stops at the first story page

Evidence: apps/web/src/app/sitemap.ts calls listStories once and ignores next_cursor. As inventory exceeds the first page, older stories disappear from the sitemap. It includes local/personal utility routes such as Saved and Search while robots permits everything.

Fix: paginate or use bounded sitemap indexes, include latest, make indexing decisions for utility/empty-topic pages, and keep canonical/structured data consistent with actual content format and update timestamps. Test more than one page of inventory.

### 17. P2 — CI does not validate the things that caused the recent live failure

Evidence: CI includes lint, TypeScript, mobile tests, dependency/security scans and API tests, but no web/admin production build or browser/a11y journeys. Golden eval README explicitly says it validates deterministic fixtures, not real provider classification/translation. Python requirements are broad lower bounds without a reviewed lock in the inspected deployment path. PROGRESS.md records 71 mypy errors; CI does not run mypy.

Fix: add production builds and selected browser journeys; fixtures must cover BRIEF, zero/two/many items and errors. Add a small capped, isolated paid-model contract/evidence/Telugu eval at model or prompt changes; never run unlimited live AI on every commit. Lock Python deployment dependencies, incrementally reduce mypy debt and then gate it. Clean mobile test act warnings so meaningful regressions are visible. Do not treat all current type debt as newly introduced by this review.

## UX/UI changes in order

Keep the existing typography, dark/light palette, responsive card approach and clear source links. Improve information value first:

- Lead card: shorter original headline, distinct informative summary, publication/source age, relevant topic/geography and visible source action. Reduce the repeated long source title dominating the phone viewport while retaining required attribution.
- Details: explicit FULL/Brief treatment, useful why-matters for full stories, readable Telugu line height, corrections/update state and evidence attribution.
- Navigation: curated populated topics plus All topics; make Latest available on mobile. Present student topics prominently for students without crowding every default header.
- Sparse states: show available content and honest coverage messaging. Do not invent stories, source permissions or notification promises.
- Admin: stage funnel, last worker activity, oldest queued item, model refusal, review reasons, source status and cost per completed publication together. Provide audited recovery of held work. Preserve individual sensitive-story review.

## Keeping the AI bill low

Cheaper productive work is more valuable than free repeated failures. Fix durable retries and accounting before changing providers.

Recommended order:

1. Freshness/validity/dedup filtering before AI; bound initial feed imports and triage relevance. Non-FEMA adapters currently have no equivalent 30-day guard. Define per-source freshness policy explicitly, retaining useful evergreen material when intended.
2. Cache classification and task output by evidence/content version + model + prompt version + schema version. Preserve rights/privacy checks and editorial invalidation.
3. Determine FULL vs BRIEF before drafting/translation. Avoid full generation followed by a second brief generation followed by discarded Telugu. Keep separate classification if its privacy decision is necessary before generation.
4. Translate only selected final English material; generate once for all readers. Retain deterministic QA rather than purchasing an LLM grade for every translation.
5. Keep Flash-Lite for supported routine tasks, bound output and thinking where the model supports it, and escalate only documented failure/risk cases.
6. Use provider-native structured output with the supported schema subset, followed by existing Pydantic/evidence validation. Appending schema to the prompt was a useful repair; native enforcement should reduce wasted schema retries.
7. Consider Gemini Batch for nonurgent eligible work after retry/idempotency controls. Google lists 50% cheaper batch pricing. It is unsuitable for work needing immediate publication; inspect completion latency and delayed budget accounting first.
8. Use free tier only under the accepted privacy allowlist and separate correctly configured project; never send restricted/editor-authored text merely to save money. Production progress records a billed project with free routing disabled, so do not label current calls free.
9. Add provider-side project spend cap and in-app paid limits, per-day ingress/draft caps, usage alerts, and a dashboard for cost per successfully published bilingual story, rejected/failed spend and repeated calls.
10. Avoid speculative context caching: these prompts are short and variable and cache storage costs money. Avoid local LLM hosting on the 4 GB production VPS; quality, contention and operations can outweigh API savings. No Redis/OpenSearch/new service is warranted.

Illustrative estimate, not measured production spend: current Google standard Flash-Lite pricing is $0.30/million input and $2.50/million output tokens. Assuming each completed story totals 6,000 input and 1,500 billed output tokens across all stages, cost is $0.00555/story. At 20/day for 30 days, that is $3.33/month; at 100/day, $16.65. This assumes no extra rejected candidates, failed attempts, escalation, uncaptured thinking or segment explanations. If 100 candidates/day are processed to publish 20, candidate processing still costs money. Measure actual billable tokens and publication yield before choosing a lower ceiling. The existing $50 target is a guardrail, not an expected necessary monthly spend.

Provider references checked during review:
- https://ai.google.dev/gemini-api/docs/pricing — rates, billable thinking, free/paid data treatment and batch discount.
- https://ai.google.dev/gemini-api/docs/structured-output — provider-native output schema support.
- https://ai.google.dev/gemini-api/docs/billing — project spend caps and delayed-billing/long-task overage limitations.

## Ordered improvement backlog

1. Diagnose production funnel and verify first successful newly generated publication; recover existing holds without bypassing review.
2. Fix durable retries/checkpoints, total spend policy/accounting and bounded AI batches.
3. Fix brief headline evidence, Telugu numeric QA, publication content validation and rights rechecks.
4. Prove offsite backup/restore, deploy failure detection and independent worker monitoring.
5. Activate only rights-approved balanced coverage; improve sparse-topic navigation and content quality.
6. Establish approval-before-translation lifecycle and reduce redundant brief/segment calls with accepted ADRs.
7. Ship domain-correct mobile build, refresh/Latest improvements and device accessibility validation.
8. Add live-model contract eval, build/browser CI, dependency lock and incremental typing cleanup; address SEO and session/fetch hardening.

Suggested operational metrics: fresh published stories/day by topic/source; oldest review age; fetch-to-publication time; worker heartbeat and oldest due job; provider failures/schema-retry rate; QA failure rate; translation availability; billed cost per published bilingual story; wasted spend and monthly projected total. Set targets from owner capacity and observed load; these are proposed metrics, not spec additions.

## Verification performed

- Python ruff: passed.
- Workspace TypeScript typecheck: passed (contracts, web, admin, mobile).
- Mobile Jest: 5 suites, 19 tests passed; existing Expo/React act warnings are noisy.
- Scoped API integration/unit suite: 92 passed against local PostgreSQL (gateway, translation, editorial workflow, briefs, Gemini provider and paid routing). The initial sandboxed attempt could not access localhost; rerun with approved local access passed. JWT short-key warnings concern test fixtures, not verified production credentials.
- Direct deterministic reproduction of QA accepting 5→50 and added 100: confirmed.
- Public browser: phone-width home, detail, language switch, latest and empty entertainment verified.
- Not run: full API suite, production builds, visual/a11y suite, native phone session, production DB/log audit, live billable model eval, backup restore or load/security tests. No production settings were changed.

Only this review document was added. PROGRESS.md was not changed because no implementation ticket was completed.
