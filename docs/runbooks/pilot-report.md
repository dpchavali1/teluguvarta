# T20 — Pilot report and go/no-go decision

**Status: NO-GO for public launch, pilot not yet run.**
Last updated: 2026-09-09 (revised after the Next.js RCE fix and the
`/pilot` landing page, both below).

## 1. Pre-build validation gate — engineering side shipped, pilot itself not run

`docs/BUILD_ORDER.md`'s "Pre-build validation gate" (landing page + 3 example
personalized feeds → recruit 50-100 target users → 14-day digest pilot →
measure repeat usage before *any* V1 build) was recorded in `PROGRESS.md` as
NOT STARTED — the full T01-T19 build proceeded without it. That's flagged
per T20's explicit instruction, not silently skipped, and it's why this
report is NO-GO. As of 2026-09-09, the engineering half of the gate exists:

- **`/pilot`** (`apps/web/src/app/pilot/page.tsx`): pitch copy + 3 example
  personalized feeds, each a real preview via the T16 `/v1/home` ranking
  (not mock data) — professional (jobs/immigration/money), international
  student (education/immigration/community), and family/parent (Andhra
  Pradesh/Telangana/parents/property), the three segments closest to
  `docs/BUILD_ORDER.md`'s "target USA Telugu NRI users". Each has an email
  signup form.
- **`POST /v1/pilot-signups`**: public, rate-limited, dedupes by email,
  stores segment + which example feed drew the signup + an optional
  recommend-willingness score (0-10) — the concrete opt-in/recommend
  metrics the gate asks for. `GET /v1/admin/pilot-signups` gives product/ops
  the running count and roster.
- Verified, not assumed: 6 new pytest cases green, full existing suite still
  green, `next build` includes `/pilot`, a11y check (axe-core) passes on it
  with zero violations, manual curl-verified signup + validation + DB write.

**What's still missing — and still the reason this is NO-GO**: nobody has
been recruited yet, and no real visitor has used `/pilot`. Zero rows in
`pilot_signups`. No opt-in count, no recommend-willingness data, no repeat-
usage signal. Recruiting the actual 50-100 target users and running the
14-day window is a product-owner/ops action Claude Code cannot perform (it
requires reaching and observing real external people) — it cannot be closed
by further engineering work. What changed today is that product/ops now has
a concrete URL to send people to instead of a from-scratch build step.

## 2. Build-order gate — T19 is not fully "done", but its release blocker is fixed

`docs/BUILD_ORDER.md` requires T19 complete before starting T20.
`PROGRESS.md` records T19 as "partial — see changelog". Its **P0 release
blocker is now resolved** (2026-09-09): `next@14.2.35` (unpatched
unauthenticated RCEs, no 14.x fix) was upgraded to `15.5.25` in both
`apps/web` and `apps/admin`, with the resulting async-`params` breaking
change fixed in the four affected server-component pages. `pnpm audit
--audit-level=high` now reports zero high/critical findings (verified, plus
`next build`/`lint`/`typecheck`/a11y all still pass against a real backend —
see the 2026-09-09 changelog entry in `PROGRESS.md` for the full trace).
This is no longer a reason to withhold a pilot.

Still unresolved from T19 (lower severity, not release-blocking on their
own): MFA/rate-limiting/backups have only been exercised locally, not
against real managed infra (ADR-007); the golden AI eval set is 30 items vs.
§18's required ≥300, with no live-provider run.

## 3. What this session did

Given (1) and the then-open RCE in (2), recruiting/running an actual 50-100
person pilot would have meant asking real people to use a build with a known
unauthenticated RCE and an unvalidated product premise — not something to
proceed on silently. This session limited itself to what T20 assigns Claude
Code regardless of pilot outcome: verifying the pilot is *instrumentable*
and checking the launch checklist against what's actually built. A follow-up
pass then fixed the RCE itself (§2) — engineering's contribution to closing
this NO-GO is now done; what remains is product/ops-owned.

### Analytics readiness (verified, not assumed)

All twelve §17 core events (`app_open, feed_view, story_open, story_save,
story_share, language_switch, search, notification_open,
notification_opt_in, onboarding_complete, account_delete_request,
report_issue`) are implemented server-side in `apps/api/app/analytics.py`
and forwarded to PostHog when configured (T18). Client emission confirmed
present (not just the endpoint) in:
- `apps/web`: `src/lib/analytics.ts`, `src/components/TrackEvent.tsx`,
  `src/components/StoryCard.tsx`, account-deletion page.
- `apps/mobile`: `src/lib/api.ts`, plus per-screen calls in Home, Search,
  StoryDetail, Onboarding, Privacy, and NotificationPreferences screens,
  with a dedicated `src/__tests__/analytics.test.tsx`.

So: if a pilot were run today, the north-star metric (weekly retained users
consuming ≥1 personalized story, returning on another day) and every
supporting metric in §17 would actually be captured. This criterion is met.

## 4. §26 launch checklist status

| Item | Status |
|---|---|
| Native share + Copy Link fallback everywhere | Done (T15/T14) |
| Shared URLs resolve to canonical page, no preview image absent rights | Done (ADR-002 enforced) |
| Priority sources pollable 1-5 min, freshness observable in admin | Done (T08, T18) |
| Normal stories live within 15 min of discovery | Not load-tested against this specific SLA — T19's load test covered feed/search targets, not ingestion-to-publish latency under real traffic. **Deferred**: needs a real pilot to measure. |
| Topic alerts match subscribed topics + quality/quiet-hour/cap/dedup | Done (T17) |
| Breaking alerts separate threshold from topic match | Done (T17) |
| Notification history/deep-links work iOS/Android/web, fail gracefully for retracted destinations | Done (T17), not device-farm verified — simulator/local only |
| Landing-page validation shows repeat engagement | **Not done** — see §1, blocks launch |
| 3-5 source rights approvals documented | Done — 3 `LINK_ONLY` sources with rights evidence (T06/T07) |
| No `DISABLED` source can publish | Done, enforced at ingest (`adapters/base.py::emit()`) and DB default |
| Legal/privacy pages counsel-reviewed where required | `apps/web/src/app/privacy` and `/terms` exist but **counsel review cannot be confirmed by Claude Code** — this is a human legal action; treat as open until product/legal signs off |
| Admin review staffed for sensitive categories | Product/ops responsibility, not verifiable from the repo — **deferred, not Claude Code's to close** |
| EN/Telugu QA passes thresholds | `app/content/qa.py` checks run (T13); no live-provider volume run to confirm real pass rate at scale (same no-network-access gap noted since T10) |
| Backup restore + account deletion tested | Backup/restore: one real local restore test passed (T19). Account deletion: cross-system deletion implemented and covered by tests (T19), not exercised against real managed infra |
| App-store forms accurate | `docs/APP_STORE_READINESS.md` exists (T19) — accurate as documented, not submitted |
| Notification opt-in/quiet controls work | Done (T17) |
| Topic toggles persist per-device after sign-in | Done (ADR-006 anonymous-identity model, T16/T17) |
| Broken-source/AI-failure/cost-guardrail/correction-retraction failure modes simulated and pass | Circuit breaker, AI degrade modes, budget-breach auto-publish gate, and correction/retraction flows are all implemented and unit/integration-tested (T08, T10, T12, T19); not simulated under real production load |
| Student onboarding/briefing/topics/independent alerts on web + both mobile platforms | **Not built** — S1/S2 (student life-stage tickets) are parallel/insertable tickets in `docs/BUILD_ORDER.md`, not yet started. Explicitly deferred: no student pilot cohort possible until S1/S2 land |
| X polling incremental via `since_id`, no rights/editorial bypass | **Not built** — X1-X4 are parallel/insertable tickets, not yet started. Deferred: no X-derived content in this pilot |
| Admin shows X account health/poll state/cost | Not applicable — X adapter not built |
| X budget guard behavior | Not applicable — X adapter not built |
| No `DISABLED` X source publishes, canonical attribution preserved | Not applicable — X adapter not built |
| Performance/accessibility/security release gates pass | Accessibility: WCAG 2.2 AA axe pass, 12 pages (T19, re-verified after the Next.js upgrade). Performance: local load test within §16 targets (T19), not against real infra. Security: the P0 RCE is fixed (§2); `pnpm audit --audit-level=high` clean; §19's other T19 gaps (real-infra MFA/backup exercise, 300-item golden AI eval) remain open but are not P0 |

## 5. Go/no-go decision

**NO-GO** — but the blocker set has shrunk to one, and it's product/ops-owned:

1. ~~T19 open P0 security blocker (unauthenticated RCEs in
   `next@14.2.35`)~~ — **fixed 2026-09-09**, see §2.
2. **Pre-build validation gate was never run** — no evidence yet that the
   product premise (repeat weekly usage, qualitative utility) holds for the
   target audience. This is the remaining reason engineering readiness
   alone can't flip this to GO.
3. No actual pilot has been run — north-star and supporting metrics above
   are *instrumented*, not *measured*, because no real users have used the
   product yet. (Downstream of #2 — once the validation gate or a
   substitute produces a repeat-usage signal, the actual pilot is the next
   step, not a blocker in itself.)

## 6. What has to happen before this can flip to GO

- **Product/ops: recruit the actual 50-100 target users and send them to
  `/pilot`, then run the 14-day measurement window and check
  `GET /v1/admin/pilot-signups` plus qualitative follow-up against §1.5's
  repeat-usage bar.** This is now the only open item — the landing page and
  signup capture it depends on already exist and are verified working.
- Engineering: decide whether S1/S2 (student cohort) and X1-X4 (X adapter)
  are in scope for the pilot cohort or explicitly out of scope — if out of
  scope, the corresponding checklist rows above stay "not applicable" and
  don't block; if in scope, they need to be built first.
- Product/legal: confirm counsel review of `/privacy` and `/terms`, and
  confirm admin staffing plan for sensitive-category review during the
  pilot window.
