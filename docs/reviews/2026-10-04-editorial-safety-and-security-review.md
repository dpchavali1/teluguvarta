# Editorial safety, notification reliability and security review — 2026-10-04

The project has a solid foundation, but editorial safety, notification
reliability and security requirements need attention before further feature
expansion. The review covered the requirements, current progress, API, mobile
notification paths, admin workflow and recent features. No files were changed
by the review itself. Line references are as reported at review time and may
have moved.

## Findings

| Priority | Finding | Recommended improvement |
|---|---|---|
| **High** | **Corrected stories cannot be retracted.** The API accepts only `PUBLISHED`; the admin also hides Retract for `UPDATED` stories (`apps/api/app/routers/admin.py:1088`). | Support retraction after correction across API, database transitions and admin. Add a correction → retraction regression test. |
| **High** | **Queued pushes can expose retracted content.** Delivery reads the headline and slug without checking that the story remains public. Retraction leaves pending alerts untouched (`apps/api/app/jobs/notify.py:399`). | Recheck publication status and applicable rights immediately before sending; suppress obsolete alerts. |
| **High** | **Turning alerts off does not stop already queued notifications.** Delivery reloads preferences but checks only quiet hours and the daily cap, not current topic, tracker or breaking-alert eligibility (`apps/api/app/jobs/notify.py:376`). | Revalidate the current subscription and alert settings on every delivery attempt. |
| **High** | **Security requirements have not been reviewed as a whole.** Controls are spread across ADRs and T19, which is "Partial". MFA, rate limits, deletion and production alerts are verified locally but not in production. The `node-forge` advisory in Expo CLI is a release blocker kept only by [ADR-038](../adr/ADR-038-unpatched-expo-cli-advisory.md); its current status was not reverified. | Run one security requirements pass before further features or release (scope below). |
| **Medium** | **Read-later reminder taps lack navigation handling.** Reminders use Expo local notifications, but App handles opens only through Firebase (`apps/mobile/App.tsx:112`). | Handle Expo notification responses and cold-start responses through the existing navigation-ready queue. |
| **Medium** | **Withdrawn exam dates still produce queued pushes.** Instead of suppressing them, the dispatcher substitutes a generic "exam date… has an update" message (`apps/api/app/jobs/notify.py:352`). | Cancel pending reminders on withdrawal and recheck status before delivery. |

## Security requirements pass — scope

- **Requirements vs. implementation.** Map each security-relevant requirement
  (SPEC, NON_NEGOTIABLES, ADRs) to the code and a test. NON_NEGOTIABLES has no
  explicit security section; list the missing requirements and record them in
  an ADR rather than guessing.
- **Notification safety.** The three high notification and retraction findings
  above are also integrity defects; they come first.
- **Admin access.** MFA enforcement, session storage
  ([ADR-028](../adr/ADR-028-admin-session-storage.md)) and approval authority.
  A single admin can currently approve their own tracker entry.
- **Input and links.** Tracker source links (exam dates accept any https URL)
  and the share-card route.
- **Perimeter.** nginx proxies correctly and app ports bind to `127.0.0.1`, but
  the VPS IP is exposed through DNS. Decide on Cloudflare plus origin
  firewalling and real client-IP handling (rate limits depend on it). An ADR
  comes first.
- **Secrets.** `.env.prod`, the Firebase key (mode 0400), and
  `google-services.json` / `GoogleService-Info.plist` in the repo. Confirm what
  is committed; rotate anything that should not be.
- **Dependencies.** Rerun `pnpm audit` and `pip-audit`; confirm ADR-038's
  blocker status and expiry.
- **Production evidence.** MFA and logout, rate limits and backup restore on
  the real stack.

## Other improvements

- **Close the release evidence gaps.** Outstanding: restore/rollback,
  production MFA/rate-limit, iOS push, accessibility, Telugu fidelity and
  performance checks.
- **Test complete user journeys.** Queued alert → unsubscribe, publish → queue
  → retract, exam approval → withdrawal, local reminder → cold-start story
  navigation.
- **Improve test reliability.** Mobile tests pass but emit extensive React `act`
  and environment warnings. API tests inconsistently skip or error when
  Postgres is unavailable, making local results harder to interpret.
- **Consolidate progress documentation.** `PROGRESS.md` retains older
  statements such as "P05–P08 not started" alongside completion entries. Keep
  one current status per ticket, with deployment and device evidence separate.
- **Finish cross-platform usability.** Web lacks several mobile personalization
  controls; recent tracker and admin screens still need browser and device
  verification and responsive polish.

## Validation performed by the review

- Workspace TypeScript checks: passed
- API Ruff and mypy: passed, 88 source files
- Web tests: 20 passed
- Mobile tests: 115 passed
- API tests: 203 passed, 384 skipped, 44 setup errors because local Postgres
  was unavailable. Database-backed behavior is unverified in that run.

## Recommended order

1. The three high notification and retraction defects.
2. The security requirements pass.
3. Reminder tap handling and withdrawn exam alerts.
4. Remaining release gates, then new features.
