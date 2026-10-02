# Progress — current handoff

Updated 2026-10-01. This page is the current status for build-order decisions.
The [verbatim prior tracker](docs/history/PROGRESS-through-T14-search-2026-10-01.md)
preserves the full implementation chronology, commands, results, and rationale
through T14-search. See the [improvement plan](docs/reviews/2026-10-01-improvement-plan.md)
for the ordered follow-ups and the [ADR registry](docs/adr/README.md) for decisions.
Local implementation is distinct from deployment and device acceptance.

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

**Current T19/X5 follow-up (2026-10-01, uncommitted):** The requested release
proof is in progress. [Preflight evidence](docs/reviews/2026-10-01-release-preflight.md)
shows CI for `fa780eb` failed on an RSS type-only import and an unpatched
high-severity node-forge advisory in Expo CLI. The RSS import is fixed locally;
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

1. Deploy compatible API/admin/web versions and confirm migrations, public
   search cursors, repair flow, account deletion, and rollback path. Deploy API
   before or with search readers. No deployment has been performed in this work.
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

The [historical tracker](docs/history/PROGRESS-through-T14-search-2026-10-01.md)
contains detailed earlier statuses and validation. Temporary synthetic screenshots
and logs are under `/tmp`; they are not production or device evidence.
