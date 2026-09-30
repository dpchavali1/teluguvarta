# Live product review and improvement plan — 2026-09-30

Review requested by the owner after website and Android launch. This is a
review and proposed backlog, not an accepted architecture decision or an
implementation ticket. SPEC V5.2 and accepted ADRs remain authoritative.
No production content, settings, sources, or budgets were changed.

## Scope and evidence limits

- Inspected BUILD_ORDER, current PROGRESS, NON_NEGOTIABLES, the previous review,
  relevant ADRs, and web/mobile/admin/API code.
- Used the live website at its phone viewport and at 1440×900; checked home,
  a story link, and Telugu search. Visited admin and confirmed the login gate.
- Read the public stories API at approximately 2026-09-30 23:35 UTC
  (18:35 America/Chicago). Snapshot: 17 published stories, no next page;
  15 attributed to ntnews.com and 2 to NPR; all 17 had a Telugu variant by
  snapshot time; 15 had IN geography, 2 had none. Inventory was growing during
  review, so these are snapshot counts, not daily totals.
- Admin findings beyond the login screen are code inspection. No authenticated
  admin session, production DB/logs, provider billing, backup evidence, or
  physical mobile device was available in this review. Mobile findings are
  code inspection and local tests, not a new device acceptance pass. The owner’s
  recent Android install is recorded in PROGRESS; iOS release parity is unverified.

## Assessment

There is now a functioning source-to-publication pipeline and a recognizable
shared visual identity. The immediate weaknesses are reading reliability,
Telugu quality, coverage balance, and operational visibility. Increasing volume
or adding decorative imagery would amplify these weaknesses. Keep the current
palette and source attribution; improve the usefulness and reliability first.

## Findings, ordered by priority

### R1 — P1: Telugu-slug website stories return 404

Confirmed in browser: opening the tribal-leaders story from Home rendered
“Page not found.” Separate direct checks: story
`9f334ada-b40f-4461-8e15-295175ee5bec` returned API 200 but website HTTP 404;
an older ASCII-slug story returned API 200 and website HTTP 200.

Likely cause: `apps/web/src/app/story/[slug]/page.tsx` passes the route param
directly to `getStory` and `getShareMeta`, which call `encodeURIComponent`
in `apps/web/src/lib/api.ts`. This repo already documents encoded Next path
params and decodes cursor params in `pathCursor`; story params have no equivalent.
The observed failure is confirmed; the encoding diagnosis needs a regression
test before implementation. Native detail uses the API directly, but shared
links still land on the broken website.

Next: safely normalize route slugs once for both metadata and content, preserve
existing canonical URLs, and cover Telugu, ASCII, malformed encoding, direct
open, feed click and native shared-link journeys. Do not rename all live slugs.

### R2 — P1: mixed-script Telugu is marked PASSED and served

Four of 17 snapshot variants contained Kannada or Devanagari characters. Concrete
examples: `9f334ada…` headline starts `ఇತ್ತೀಚಿನ` (Kannada inside Telugu);
`c3061756…` headline contains Hindi `प्रस्तावित`. Other two had smaller script
contamination. Both prominent examples were visible in the live search results.
This is a script-quality finding, not a claim that every translation is false.

`apps/api/app/content/qa.py::_script_issue` counts only Telugu and Latin letters;
other scripts are excluded from the denominator. Its 25% floor therefore cannot
reject these outputs. Native-speaker fidelity sampling remains necessary.

Next: identify unexpected scripts deterministically with a documented exception
policy for legitimate quoted names/text; add regression fixtures, hold invalid
variants, and correct already-published ones through an audited workflow.
Do not “fix” contamination by deleting characters. Provide admin failed-field
diagnostics and EN/TE comparison. Clarify “automated checks passed” versus human
translation review; PASSED is not a fidelity guarantee.

### R3 — P1 operational follow-up: disaster recovery still lacks verified evidence

Current PROGRESS records backup setup, offsite storage, restore drill, monitor
dead-man configuration, and alert testing as owner steps. Scripts and runbooks
exist; this review did not establish that these steps have since been completed.
Treat them as unverified, not as a newly discovered outage.

Next: record newest successful offsite backup, restore drill result/RPO/RTO,
monitor last success and test-alert receipt. Show age and failure in admin.
No new infrastructure is needed for the dashboard itself.

### R4 — P2: admin budget wording disagrees with the gateway

Admin Home and Observability say “paid AI is paused” when the monthly degradation
budget is crossed. Gateway policy actually keeps classification running until
the hard cap; free calls can remain eligible. ADR-024 added the $60 monthly hard
cap, but Observability’s API response and UI do not expose it.

Today’s spend already exists in `/v1/admin/observability` and its page. Home
shows only month-to-date. Day/month windows use UTC without a visible label;
provider free quota uses Pacific time. Costs are token-price estimates, not a
reconciled invoice; cached tokens are priced conservatively. Main totals round
to cents, which can conceal tiny nonzero spend.

Next: put estimated spend today on Home, expose both thresholds and an explicit
mode (normal / classification only / paid calls stopped), label reporting
timezone and quota reset separately, show enough precision for small totals,
and distinguish estimates from billing reconciliation. Keep current UTC budget
semantics unless a timezone change is accepted explicitly. Do not promise that
a pre-call ceiling prevents the final in-flight call from crossing it.

### R5 — P2: admin does not explain where stories and money are going

Home shows active sources, reviews and job counts, but not the editorial funnel,
publication yield, translations awaiting work, or money spent on failed/held
stories. AI breakdown groups every historical call by day/task, without a date
range; the page hides it in a details table. Model/provider, failure rate,
retry spend and per-story cost are absent from this view despite underlying logs.

Next: bounded date-range aggregates, stage counts and age, actionable drilldowns,
provider/model/task breakdown, token categories and call outcomes. Define
“cost per publication” carefully: show publication count and call-window spend
separately, and compute story-linked lifecycle cost for the publication cohort.
Do not divide unrelated daily calls by daily published stories and imply it is
an exact unit cost. Track unlinked calls separately.

### R6 — P2: reader reports have no admin resolution workflow

Web/mobile send `report_issue` through analytics. `apps/api/app/analytics.py`
keeps the free-text description in structured logs and strips it from the
PostHog forward. There is no reports inbox in AdminNav, assignment, resolution
or reader-report lifecycle. A received report can therefore be operationally
missed even though the request succeeded.

Next: a private editorial inbox with story/source context, categories,
received time, open/resolved state, reason and audited correction/retraction
links. This is moderation of private feedback, not public UGC/comments.
Retention, abuse controls and access policy need an ADR before implementation.

### R7 — P2: review/admin navigation will struggle as volume grows

`/review-queue` returns all pending tasks; the list renders all rows, with only
an always-human-reviewed toggle. Home downloads the whole queue merely to count
it; detail also fetches the queue. Home/list refresh on mount or explicit revision,
while Observability refreshes each minute. Published-story management and global
audit navigation are not first-class surfaces; an audit endpoint exists but is
limited to the most recent 200 events.

Next: server-side cursor pagination, real total counts, search and filters for
reason/source/topic/language/age, stale-data indicators and refresh, a content
library for draft/scheduled/published/corrected/retracted work, and searchable
audit history. Keep individual sensitive decisions; no bulk sensitive approvals.
Add unsaved-edit protection and conflict/version handling when introducing
concurrent editors; assignment/locking mechanics need an ADR.

### R8 — P2 product: published coverage is concentrated

15/17 snapshot stories came from one publisher, and politics plus overlapping
regional/local/state categories dominate navigation. No immigration or student
topic appeared in this published sample. Enabled feeds do not prove useful
published coverage. Student and NRI value needs a deliberate editorial plan.

Next: source-to-publication yield by topic, age and publisher; daily coverage
review; curate approved AP, Telangana, cinema, practical NRI and student work.
Consolidate presentation of overlapping categories into a small reader-facing
navigation set through an accepted product decision. Preserve existing topic
IDs/links and rights rules. “Top stories” is currently chronological for users
without preferences, not editor-selected importance: rename or define its role.

### R9 — P2 product/design: verbose content creates oversized phone cards

Observed lead: six headline lines before summary, followed by generic commentary
and a long source-title action. Several Telugu headlines are sentence-length.
Why-matters examples explain that political disagreement creates political
tension rather than giving a concrete reader implication. Short FULL summaries
can pass the word-count alternative in ADR-026; passing that rule does not make
the content useful.

Next: an editorial brevity guide for each language, informative summaries and
evidence-backed why-matters (omit if no supported implication). Use shorter
display headlines; avoid hiding the complete headline solely to disguise poor
copy. On feeds keep compact attribution; expose the full source title in detail.
Do not invent dates, actions or local impact to make a card appear richer.

### R10 — P2: mobile polish and offline reading remain incomplete

`MainTabs.tsx` uses text glyphs for icons, which depend on system font rendering.
Its old package-type conflict should be reassessed after the recent Next peer
type fix, not assumed resolved. `StoryDetailScreen` clears the story and fetches
again; it does not read StoryCacheContext on network failure. The cache is memory
only, while Saved resolves current API content. This is not durable offline
reading.

Next: consistent vector icons, a deliberate Home/Latest navigation decision,
readability controls, cache-assisted opening, and explicit stale/offline labels.
Persisted offline news needs expiry and correction/retraction behavior defined
in an ADR. Check Android/iOS large text, TalkBack/VoiceOver, poor network,
background return, push opening and Unicode shared links on devices.

### R11 — P2 security follow-up: admin session design remains open

`apps/admin/src/lib/auth.ts` retains bearer tokens in localStorage. ADR-028
proposes server-side revocable HttpOnly cookie sessions and CSP but is not
accepted. Existing React escaping and account-role rereads are useful controls;
this review found an exposure path, not evidence of compromise.

Next: decide ADR-028, then implement revocation/logout, session activity and CSP
as a focused ticket with cookie/CORS/CSRF tests. Do not silently change auth
architecture during a cosmetic admin refresh.

### R12 — P2 scale: search is basic and regional personalization is fragile

Live Telugu substring search worked (4 results for తెలంగాణ). API search uses
ILIKE over headline/summary, capped at 20 by default, without a next cursor or
relevance scoring. The frontend reports returned length as the result count.
Home-region ranking matches state/city names to topic slugs, while the live
sample is tagged politics/local/regional rather than regional place slugs.
Country geography work does not supply state/city matching.

Next: explain returned result limits, add pagination and Postgres-backed
relevance when inventory warrants it, test Telugu query behavior, and define
state/city editorial tagging before claiming precise hometown personalization.
Do not add OpenSearch or infer geographic facts from publisher location.

## Proposed admin experience

Admin should answer four questions immediately: what needs my decision, what
published today, what is failing, and what are we spending?

| Surface | Most useful information/actions | Priority |
|---|---|---|
| Overview | Published today, pending review/oldest age, pending Telugu, estimated AI spend today/month, mode and cap, worker last activity, refreshed time | First |
| AI costs | Today/yesterday/7d/MTD/custom dates; trend; provider/model/task/outcome; free vs paid; thinking/cache tokens; retries; story-linked cost; budget and hard-cap remaining | First |
| Review | Reason-first triage, filters/search, EN/TE and evidence comparison, QA diagnostics, preview, guarded decisions, next item, unsaved edits | First |
| Content library | All lifecycle states, published search, topics/geography/language, corrections/retractions, scheduling and blocked publication | Next |
| Pipeline | Fetched→clustered→classified→drafted→reviewed→published→translated; stage age; holds/retry exhaustion; failed-job context and bounded recovery | Next |
| Sources | Rights evidence/reviewer, active state, fetch health, fresh yield, duplicate/archive/review rates, published diversity | Next |
| Reader reports | Private unresolved reports, correction links, owner, resolution reason/history | Next; ADR |
| Audit/security | Searchable actor/entity/action/date history; sessions and sign-out; roles/MFA state without exposing secrets | Next; ADR-028 |
| Notifications | Pending approvals, delivery/failure/open counts, quiet-hour/cap suppressions, story-linked delivery history | Later |
| Product health | Aggregate readership, source clicks, save/share and language usage; student/NRI coverage; avoid unnecessary personal tracking | Later |
| Operations | Backup/offsite age, restore proof, monitor alerts, release version/readiness, acknowledged incidents | First verification; then UI |

Spend drilldown should open the stories/calls responsible for a spike. Alerts
should state the problem, when it started, impact and next safe action. Provider
keys and secrets never belong in the browser. Budget changes and retry/recovery
actions should be role-restricted and audited, with existing retry bounds intact.

## Proposed visual direction

### Website

Keep the warm dark/light palette, purple accent, original text and prominent
attribution. Shorten the phone lead and reduce introductory/CTA height so a
reader reaches useful news sooner. Use one strong lead, several compact rows
and clear section boundaries. Desktop can keep its lead-plus-rail layout.
Limit main topic navigation to a curated set plus All topics; provide visible
horizontal-scroll affordance on phones. Reserve accent backgrounds for selected
navigation and the primary story rather than every card.

Story detail: calm reading width, language-aware type/line height, precise
updated/published information, clear fallback state, restrained why-matters,
and a distinct original-source action. Keep Share/Save/Report predictable.
Improve local language chrome incrementally; today Telugu story selection
coexists with English navigation. Do not copy publisher imagery or add stock
images that imply reporting evidence; source images/share cards remain deferred.

### Mobile app

Carry the same typography hierarchy and concise card copy, while using native
spacing, consistent icons, safe-area controls and accessible feedback. Make
Latest easy to reach alongside a genuinely personalized Home. Add compact and
comfortable reading modes only after default large-text behavior passes device
checks. Show loading, offline, refresh and translation states with stable layout.
Avoid duplicating oversized cards in student briefing and the main feed without
a clear benefit.

### Admin

Use a compact work interface: overview metric row, actionable attention list,
review workspace and drilldowns. On desktop use side-by-side evidence and draft
with decisions nearby. On phones use a summary of blocking checks followed by
the story and a reachable action bar; currently CSS puts decisions above the
story while DOM order differs, so validate reading/focus order. Status needs
text plus color. Reuse design tokens but prioritize scanability over decorative
public-site cards. Show success, errors, unsaved changes and session expiry.

## Implementation sequence and completion criteria

These are proposed review tickets; do not mark existing build tickets complete
or treat the list as authority until scoped and accepted. One ticket per session.

1. **Reading reliability:** Unicode route normalization and browser regression
   journeys. Done when live EN/TE links, metadata and native shares open the same
   correct story, without changing canonical URLs.
2. **Telugu quality:** unexpected-script policy/checks, audited live corrections,
   reviewer diagnostics and native-speaker sample. Done when bad variants are
   withheld and valid bilingual fixtures pass without extra unbounded AI calls.
3. **Operational proof:** offsite backup/restore and monitor-alert evidence.
   Done when restore and alert receipt are recorded, not merely scripts present.
4. **Admin overview + AI cost MVP:** reuse logs, bounded aggregates and generated
   contracts; today/month/cap/mode/timezone/update state. Done when fixture totals
   reconcile to call logs, every budget state has correct wording, and refresh
   failure is visible. No provider price/model changes needed.
5. **Review and content library:** count/pagination/filtering, lifecycle access,
   search, audit drilldowns and safe edit UX. Done on zero/large/error/stale
   fixtures at phone/desktop widths, preserving all human-review gates.
6. **Coverage and copy:** editorial targets and source yield; concise original
   headlines, meaningful implications and curated navigation. New product
   taxonomy/region requirements require an ADR; no speculative rights approvals.
7. **Web/app visual pass:** shared components/tokens, compact cards/icons,
   accessibility and performance on real bilingual inventory. Done with phone
   and desktop visual checks, keyboard/axe checks, Android large text/TalkBack
   and iOS VoiceOver where that release exists.
8. **Further admin tools:** private reports, secure sessions, persisted offline
   reading, translation timing and multi-editor controls after their ADRs.

Useful acceptance dashboard measures: broken-link rate; mixed-script failures;
fresh publications and publisher/topic mix; oldest review/stage age; bilingual
availability lag; provider/schema/QA failures; paid retry cost; publication-cohort
cost; worker/backup freshness. Establish targets from observed workload and
editor capacity, not arbitrary growth promises.

## Verification

- Public API snapshot and direct URL comparisons with system curl: confirmed.
- Live home phone/desktop, Telugu search, broken story link and admin login:
  checked through browser UI. No admin mutations or report submissions.
- `pnpm --filter @teluguvarta/web test`: 4 passed (sitemap only; does not cover R1).
- Web/admin TypeScript checks passed.
- `pnpm --filter @teluguvarta/mobile test --runInBand`: 6 suites / 24 tests
  passed, with existing Expo/React act warnings. An initial invocation added an
  extra `--`, so Jest treated the flag as a pattern and found no tests; corrected
  command above passed.
- Not performed: full API suite, paid model eval, load/security penetration test,
  provider invoice reconciliation, authenticated admin journeys, physical mobile
  acceptance or server restore drill. Those limits are material to this review.
