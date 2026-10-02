# Project improvement plan — 2026-10-01

Owner request: review the project, plan improvements, and start changing them one
at a time. SPEC V5.2 and accepted ADRs remain authoritative. This plan proposes
work; it does not accept new architecture or declare deployment complete.

## Assessment and evidence

Keep the modular monolith, Postgres queue/search, shared contracts and design
tokens. The project has substantial implemented functionality; the highest
return now comes from reliable releases, trustworthy bilingual content and
clear reading/editorial journeys rather than more feature surfaces.

Reviewed build order, progress, constraints, the existing comprehensive/live
reviews, T19, CI, database fixtures, and selected search, QA, publication queue,
web card and mobile cache code. This is a repository review with regression
verification, not a fresh full production/browser/device audit. Existing review
findings are carried forward only where current progress still leaves them open.

The September 30 review is partly stale: R1/R2/R4–R7/R9 and R11 have implementation
entries; R8 has measurement, and mobile has additional reader controls. Rebuilding
these would waste effort. Several entries still say not deployed or not visually
verified, and T19 remains partial. Confirm current production versions before
assuming those fixes are live.

## Ordered improvement backlog

| Order | Improvement | Scope and completion evidence |
|---|---|---|
| 1 | Reliable regression checks (T19) | Unique scratch DB per fixture, close pooled application connections before dropping it, cleanup on setup failure. API suite passes without the previously recorded fixture error. |
| 2 | Release and recovery proof (T19/R3) | Confirm deployed API/admin versions together, migration heads, cookie/MFA/logout journeys, backup age, restore RPO/RTO and alert receipt. Owner evidence required for infrastructure and device checks; scripts alone do not close this. |
| 3 | Telugu quality lifecycle (R2) | Withhold contaminated variants, show failed-field diagnostics, and define an audited repair path for already-PASSED variants before implementation. Native-speaker sample establishes fidelity; deterministic script checks alone cannot. New retry/lifecycle behavior needs an ADR. |
| 4 | Search usability (R12) | First label returned results honestly; then scope bounded pagination and Postgres relevance, with bilingual queries, empty/error states and stable paging tests. Decide regional tagging through an ADR before promising hometown relevance. |
| 5 | Editorial usefulness and coverage (R8/R9) | Use existing yield dashboard to investigate SUMMARY_TOO_SHORT holds and publisher/topic imbalance. Sample actual output against the brevity guide. Accept ADR-030 before changing taxonomy/navigation; preserve rights and sensitive-review gates. |
| 6 | Reading design and accessibility | Verify existing compact cards and EN/TE detail on phone/desktop; refine spacing, horizontal-navigation affordances, source actions and loading/failure states using current tokens. Keyboard/axe and large-text checks must support changes. |
| 7 | Mobile completion (R10) | Finish Android/iOS accessibility, poor-network, background-return and push journeys; validate release parity. Persisted offline reading needs an accepted expiry/correction/retraction ADR first. |
| 8 | Maintainability | Reduce mypy errors module by module, keep contracts/generated tokens reproducible, and shorten PROGRESS into a current summary plus linked history in a separately scoped documentation change. |

Implement one focused ticket at a time, with acceptance tests and progress updates.
Do not mark T19 complete until its remaining release gates have evidence. No new
source approvals, infrastructure, public UGC, or publication-policy changes are
implied by this plan.

## First change

The database fixture previously derived its name from the test name (truncated
at 63 characters) and pre-dropped that database. Repeated/concurrent runs could
therefore share a name; leftovers could require terminating another connection.
Application engine cache clearing also discarded references without disposing
pools. These are plausible contributors to the recorded intermittent
InsufficientPrivilege failures, not a proven diagnosis of every previous run.

Scratch databases now use random UUID names and quoted SQL identifiers. Setup
never drops an existing named database, and the administrative connection closes
even when creation/drop fails. The migrated fixture tracks and disposes every
application engine it creates, including engines forgotten by local cache clears.
Regression checks cover overlapping databases and failed creation cleanup.

Verification: schema/runtime-switch tests 20 passed; full API suite 523 passed
with no fixture error, scoped ruff and diff whitespace checks clean. Existing
mypy count is 70 (CI baseline 71). This first change touched the API test fixtures only; the interface follow-ups are recorded below.


## Comprehensive website and app interface program

Owner authorized this interface program on 2026-10-01. It is an incremental
follow-up to T14/T15 and the accepted ADR-009/010/014 component/token contracts,
not a new palette or architecture. Infrastructure evidence remains an open T19
track; it does not block independently testable presentation improvements.
Preserve native implementations, complete original headlines, sources, browsing
without login, existing topic URLs and bilingual fallback semantics.

### Design direction

News first: use the edition date and a compact introduction, then a distinct lead
and quieter supporting stories. The hierarchy should come from type, spacing and
rules; reserve indigo for navigation/actions and semantic colors for real states.
Personalization supports reading instead of occupying a competing promotional
card. Keep source attribution legible and the original-source action prominent.

Design against actual English/Telugu copy, including long headlines and missing
translations. Do not use truncation to conceal weak editorial copy. Avoid stock
photography that implies reporting evidence. Reuse Folio tokens and platform
icons; motion must be optional, subtle and respect reduced-motion settings.

### Sequential interface tickets

Each row is one scoped follow-up; scope it in a self-contained ticket before
implementation. Verify existing work first. The owner requested one-by-one
implementation, so complete and record one ticket before starting the next.

| ID | Surface and change | Acceptance and dependencies | Status |
|---|---|---|---|
| UI01 | Web Home: compact edition introduction and secondary personalization link | First lead visible at phone/desktop/200% layouts; onboarding/edit path stays reachable, 44px link target, first-visit and returning states, no overflow in EN/TE/light/dark. No feed/ranking changes. | Done locally; not deployed |
| UI02 | Web topics: improve horizontal-scroll discoverability and selected state | All existing topics reachable with keyboard/touch; visible edge/scroll affordance only when overflowing; current topic evident; no document overflow. Keep taxonomy and topic IDs; curated categories await ADR-030. | Implemented locally; browser verified |
| UI03 | Web feed cards: audit lead/brief density and metadata hierarchy | Real long EN/TE headlines remain complete; compact source attribution, working Save and source links, no duplicate action clutter; zero/one/many stories and fallback layouts pass. Build on R9 instead of redoing it. | Implemented locally; browser verified |
| UI04 | Web story detail: reading measure, type rhythm and action placement | Comfortable line length and Telugu line height, obvious source action, published/updated/correction information, clear EN fallback; Save/Share/Report remain reachable and keyboard ordered at 320px and 200% zoom. | Implemented locally; browser verified |
| UI05 | Web search: honest result wording and useful empty/error states | Preserve query, label returned limits accurately, provide retry/browse paths and accessible search feedback. Pagination/relevance is a separately scoped API/contracts follow-up, with bilingual and paging tests. | Implemented locally; recovery verified |
| UI06 | Web Saved and utility pages: consistent recovery and navigation | Empty Saved explains the action, unavailable stories do not leave broken cards, privacy/deletion/corrections remain reachable; storage failure and copy/share feedback accessible. | Implemented locally; storage recovery verified |
| UI07 | App Home: tighter edition and clearer Latest entry | First story appears promptly, existing preferences/student briefing work, loading and refresh do not displace controls; retain current tab destinations. Changing tab IA requires a scoped product decision. | Implemented locally; device acceptance pending |
| UI08 | App cards and detail: align editorial hierarchy with web | Native spacing, coherent icons, full Telugu headline and summary, distinct source/action rows, existing text-size controls apply; font scale 1.5/2.0 has no clipping or overlapping targets. | Implemented locally; device large-text acceptance pending |
| UI09 | App discovery: Topics/Search/Saved consistency | Clear selected filters, query-preserving loading/errors, useful zero results, consistent save state across screens; small-phone and screen-reader journeys pass. Preserve backend and topic identity. | Implemented locally; device acceptance pending |
| UI10 | App feedback and connectivity: stable reading states | Cached copy visibly dated, Retry reachable, authoritative 404 evicts copy, network failure retains reading position where practical; background return and deep links work. Durable offline cache remains ADR-gated. | Implemented locally; resume/404 regressions pass |
| UI11 | App Settings/onboarding: audit current reader controls | Theme/language/text size/interests/hidden topics/history easy to find, edits retained, skip still works; deletion/clear-data effects truthful and consistent. Reuse M1–M6 implementations. | Implemented locally; ADR-033 A accepted, failure/retry verified |
| UI12 | Cross-surface accessibility and localization | Keyboard/focus/landmarks/contrast, reduced motion, dynamic feedback, TalkBack/VoiceOver and Telugu reading checks. Localized chrome needs reviewed strings; do not invent unreviewed Telugu translations. | Browser/code checks complete; device speech/localization evidence pending |
| UI13 | Performance and layout stability | Compare baseline and changed page weight/CLS/loading; lazy-load only justified features, preserve SSR and accessible skeletons; no new font/icon library unless measured. | Saved and Telugu hydration shifts reduced locally; production/native performance gates open |
| UI14 | Release visual acceptance | Before/after phone/tablet/desktop screenshots, EN/TE/light/dark, first/returning reader, Android device and iOS when supported; deploy status and app-store release tracked separately. | Local visual acceptance complete; device/production release pending |

### State coverage and delivery rules

For each touched flow include populated, empty, loading, failed and stale states
where it has them. Check real bilingual inventory plus deliberately long text;
use synthetic fixtures only as labelled regression data, never as public news.
Web viewports: 320/390/768/1440 CSS pixels plus a 640×400 layout representing
200% laptop zoom. Check both themes and visible focus. Native checks include
safe areas, large system text, app text-size overrides and accessible labels.

Run scoped lint/typecheck/tests/build, then browser layout and axe checks for web.
Record visual inspection separately from automated checks. Device tests remain
unverified until actually performed; screenshots and passing component tests do
not establish TalkBack/VoiceOver behavior. No arbitrary performance success
claim: retain SPEC targets and compare measured baselines.

Keep a completion record with changed files, commands/results, screenshots when
available, and deployment/device limitations in PROGRESS. Review one change before
broadening it. New taxonomy, regional tagging, durable offline expiry, editorial
repair/retry policy and concurrent editor behavior require their own accepted ADRs.

### Model choice for this program

For highest-quality broad design/review work, use GPT-6 Astra with Extra high
reasoning if time and usage permit. GPT-6.1 Sol with High/Extra high is a strong
implementation choice; use Medium for small styling iterations. This is a
workflow recommendation, not a guarantee that more reasoning improves every
visual choice. Compare rendered results with the same acceptance criteria.
Current official guidance: [model selection](https://developers.openai.com/api/docs/guides/model-selection)
and [Codex code generation](https://developers.openai.com/api/docs/guides/code-generation).
This recommendation changes no product AI provider/model routing or app budgets.


### UI01 completion — 2026-10-01

Changed `apps/web/src/components/OnboardingCta.tsx` and Home edition rules in
`apps/web/src/app/globals.css`. Replaced the promotional card with an underlined
44px secondary link and concise first-visit/returning hint; tightened phone
heading/spacing. No changes to feed data, topic identity or mobile behavior.

Validation: web lint/typecheck, 8 unit tests and production build passed.
A local fixture API + Chromium checked 20 viewport/theme/language combinations
(320/390/768/1440 widths and 640×400 short layout): no horizontal page overflow,
lead headline above fold, 44px preference target. Axe on 390px Home in both themes
found no serious/critical issues; focus outline and returning edit link checked.
Visually inspected phone Telugu/light and desktop English/dark screenshots.
Synthetic headlines exercise long Telugu text; this is not production content QA.

At 390×844 the fixture's lead begins approximately 78px higher than a browser
reconstruction of the old CSS/CTA (decorative icon approximated). Screenshots:
`/tmp/tte-ui01/`. Browser scripts are temporary verification tools, not CI tests;
existing visual-regression script continues to cover Home visibility/overflow.
A build started concurrently with the dev server failed due to shared `.next`
output; rerun with dev stopped passed. Final matrix passed after CSS correction.
No deployment, real-device or new native-speaker verification. Subsequent work is recorded below.

### UI02–UI14 implementation record — 2026-10-01

Website: topic controls reveal horizontal navigation, selected topics stay in view
and arrows disappear when the list fits. Lead attribution follows its deck;
grid summaries are complete. Detail has a prominent original-source action,
Telugu leading, wrapping source titles and separated actions. Search retains its
query on failure, provides Retry/Browse and states its 20-result cap. Saved
preserves unavailable IDs, reports unreadable storage and refuses to overwrite
corrupt bookmarks. Browser clearing reports errors instead of claiming success.
Header controls have 44px targets and full language names; the narrow masthead
wraps safely. Saved uses one placeholder while its bookmark count is unknown.

App: Home has a smaller introduction, Latest near the top and Student Briefing
after the main feed. Cards use the existing vector icon set, expose compact-list
sources, wrap actions and report source/share launch failures. Detail timestamps
and cached-copy notices remain visible during refresh; focus/background return
rechecks after five minutes, while authoritative 404 still evicts the copy.
Search labels its cap/count, clears the query and offers topic discovery; old
results disappear while the next query is delayed. Saved filters wrap. Settings
has named groups/accessible headings; language radios use checked state and the
header follows settings changes, including a late initial-storage-read race.
Both surfaces suppress unexpected why-matters commentary on link-first briefs
under ADR-019, while retaining the source action.

ADR-033 option A is accepted by the owner. The combined deletion button confirms
server deletion before removing local data or identity. A failed server request
retains both for retry; a subsequent local-clear failure says the server account
is deleted and retries cleanup. Requests are exclusive. Only full completion
reports success; a later operation confirms server deletion again. Strict secure
storage reset surfaces errors. Successful cleanup also clears live saved/read/
story cache state and prevents initial storage reads from restoring old IDs.

| Validation | Result and scope |
|---|---|
| Web lint, typecheck, unit tests, production build | Passed; 9 unit tests. Shared first-load JS rounds from 102 to 103 kB against HEAD; Home remains 114 kB, Saved 113 → 114 kB. |
| Native typecheck and full Jest suite | Passed; 68 tests across 14 suites. Includes deletion retention/retry/exclusivity, secure storage failure, language synchronization, brief guard, resume refresh and 404 eviction. |
| Expo export | Android and iOS bundles passed (approximately 2.3/2.2 MB); build verification only. |
| Responsive browser matrix | 140 local layouts: seven pages × five sizes × two languages × two themes; no document overflow and Home lead begins above fold. |
| Browser axe | 28 page/theme/language checks at 390px; no serious/critical WCAG 2.2 findings. Keyboard topic focus/navigation/edges and controls disappearing after resize verified separately. |
| State journeys | Topic navigation, zero/one-story Home and returning preference link, English fallback/updated/brief detail, search cap/error/empty, unavailable/corrupt bookmarks. Synthetic fixtures only. |
| Visual inspection | Phone Telugu/light Home, Telugu/dark detail and desktop English/dark Home inspected separately from automated checks. |
| Performance comparison | 18 cold-context comparisons against isolated HEAD `286fc4e` on identical synthetic data. Phone empty Saved CLS ~0.151 → ~0.024. Sample compressed JS grows ~0.7–1.4 kB; font bytes identical. |

The first comparison identified a release concern: direct cold Telugu detail at 320px measured
~0.148 → ~0.152 CLS; the multi-page final matrix measured a higher worst case
(~0.217) during preference hydration. These are local observations with different
cache/journey conditions. They do not establish production Core Web Vitals or
close the performance target. The scoped language-hydration fix and its cost are
recorded below; production acceptance still requires live evidence.
No pre-change native-device/bundle baseline was captured, so no native performance
improvement is claimed.

Changed implementation groups:

- Web components: `OnboardingCta`, new `TopicBar`, `SiteHeader`, `StoryCard`, `LanguageToggle`; `globals.css`; Search, Saved and browser-data deletion pages; API search limit and bookmark storage helpers.
- App components: `StoryCard`, `StoryList`, `LanguageToggle`; Home, Topics, Search, Saved, StoryDetail, Settings, Language and Privacy screens; API search limit, identity reset and StoryCacheContext.
- Regressions: web `saved.test.mjs`; native deletion-recovery, identity, UX reliability, settings and text-size tests.
- Verification tooling: web `interface-check.mjs`, `interface-performance.mjs`, loopback-only `interface-fixture-api.cjs`, package scripts and README reproduction steps.
- Tracking: individual UI01–UI14 tickets, this plan, BUILD_ORDER, PROGRESS and accepted ADR-033/registry.

Local outputs: `/tmp/tte-interface-final/` (matrix/screenshots),
`/tmp/tte-interface-journeys/` (state reruns), `/tmp/tte-interface-performance/`
(before/after screenshots and resource/CLS data), `/tmp/tg-mobile-bundle-check/`
(native exports). These temporary outputs are local review evidence; reusable
scripts make the checks reproducible. No production deployment or store release.

Remaining work is explicit: Android/iOS real-device safe-area, system font scales
1.5/2.0, TalkBack/VoiceOver, Telugu pronunciation/native-speaker review, and
live backend/deep-link/push release journeys. No Android device or booted iOS
simulator was available during this run. UI12–UI14 and T19 release gates stay
partially open. Broader backlog items 2–5/7–8 remain separate work: recovery
proof, approved-variant repair decisions, API search pagination/relevance,
ADR-030 coverage/navigation, durable offline policy and mypy cleanup. This
interface implementation does not declare that broader backlog complete.

### UI13 follow-up — Telugu first paint (2026-10-01)

Available English and Telugu headline/deck/why text now renders in the initial
story HTML. A small head script reads the existing browser-local language
preference before paint; CSS exposes the chosen copy with its correct typeface
and line height. Each card retains a single visible/accessible headline and one
set of actions. English canonical metadata, source links, brief guards and
missing-Telugu fallback are preserved. No cookies, server personalization,
new translations, dependencies or fonts were added.

Language controls and onboarding now update the same preference/event. Relevant
cross-tab storage changes synchronize existing pages. A failed write retains the
current session choice through client navigation and onboarding, even if old
stored English remains readable; reload may restore the persisted choice.

| Follow-up validation | Result and scope |
|---|---|
| Web checks | Lint, typecheck, 11 unit tests and fresh production build pass. |
| Layout/accessibility | 140 layouts pass; 28 phone axe checks have no serious/critical findings. Five state journeys pass in a separate rerun after scoping the fallback assertion to the primary heading. Telugu phone detail visually inspected. |
| Language browser checks | Telugu before React bundles load; English static Home with all scripts disabled; one accessible primary heading; switching/action labels; cross-tab updates; English fallback; quota-failure navigation and onboarding pass. No hydration/runtime errors observed in checked normal journeys. |
| Controlled comparison | 36 cases: Home/Saved/detail × 320/390/1440px × EN/TE × cold/previously visited page. Same fixtures and isolated pre-fix working-tree snapshot, rather than HEAD. Worst CLS 0.2106 → 0.0255; responsive matrix worst 0.2174 → 0.0283. |
| Delayed resources | Separate 320px Telugu-detail cold comparison, each JS/font request delayed 1500ms: CLS 0.1717 → 0.0105. This delay simulation is not a mobile-network benchmark. |
| Cost | Compressed HTML +177–449 bytes; CSS +93 bytes; font bytes unchanged. Rounded build first-load JS Home/Saved 114 → 115 kB; shared 103 kB unchanged. Captured JS resource totals include speculative prefetch/cache timing; their apparent decrease is not a bundle-size claim. |

Changed files: web `storyLanguage.ts`, `onboarding.ts`, root layout,
`StoryCard`, `LanguageToggle`, global CSS, language unit tests and
`language-layout-check.mjs`; expanded performance/check scripts, package scripts
and README; UI13 ticket, this plan and PROGRESS. Reports/screenshots are in
`/tmp/tte-ui13-matrix/`, `/tmp/tte-ui13-performance/` and `/tmp/tte-ui13-slow/`.

The dynamic story route's existing streamed loading boundary needs its inline
stream-completion script; blocking React bundles works, but disabling every
script leaves that boundary loading. Static Home's script-disabled English SSR
is verified. Fully script-disabled detail delivery remains a separate follow-up.
No production, physical-device, native-speaker or store acceptance is implied.
Native checks above remain evidence from the earlier implementation; this
follow-up changes only the website. All changes remain local and uncommitted.
