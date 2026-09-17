# App-store readiness (T19 §25)

Maps what the mobile app (`apps/mobile`) actually collects at runtime, as
of T19, to Apple's App Privacy ("nutrition label") and Google Play's Data
Safety disclosures — so those store listings can be filled in accurately
rather than guessed at when the app is actually submitted. This
document does not submit anything; there is no App Store Connect / Play
Console account in this sandbox to submit to.

## What the app actually collects (ground truth, not aspirational)

| Data | Collected? | Where | Linked to identity? | Used for tracking (ad-style, cross-app)? |
|---|---|---|---|---|
| Device-scoped identifier (`client_token`, T17) | Yes | `apps/mobile/src/lib/identity.ts`, sent as `Authorization: Bearer` to `/v1/me/*` | Yes — it *is* the identity (ADR-006) | No — never shared with a third party, never used for ads |
| Push token (Expo push token) | Yes, if notifications enabled | `apps/mobile/src/lib/push.ts` → `POST /v1/me/push-tokens` | Yes, to the same device identity | No |
| Coarse preferences (residence country/region, home state/city, topics, life stage) | Yes, optional, user-entered | Onboarding → `PATCH /v1/me/preferences` | Yes | No |
| Precise/GPS location | **No** — never requested, no location permission in `app.json` | — | — | — |
| Analytics events (§17 list: `app_open`, `story_open`, etc.) + a separate anonymous `anon_id` | Yes | `apps/mobile/src/lib/api.ts::trackEvent` → `POST /v1/events` → PostHog (T18), when `POSTHOG_API_KEY` is configured | No — `anon_id` (T18) is a *separate*, non-auth identifier from `client_token`, generated specifically so analytics never carries the auth identity | No — first-party product analytics only, no ad network |
| Crash/error reports | Yes, if configured | Sentry-compatible HTTP protocol (T18), `EXPO_PUBLIC_SENTRY_DSN` | Tagged with the structured-logging `actor` (the device identity) when available | No |
| Name, email, phone, payment info | **No** — no account/login exists for end users (NON_NEGOTIABLES #9); only internal admin/editor accounts have an email + password, and that surface is never exposed to app-store reviewers as "the app's" data collection | — | — | — |
| Contacts, photos, microphone, camera | **No** — no permission requested for any of these | — | — | — |

## Apple App Privacy ("nutrition label") mapping

- **Identifiers** → Device ID (the `client_token` and Expo push token) —
  linked to the user, not used for tracking.
- **Usage Data** → Product Interaction (the §17 analytics events) — **not**
  linked to identity (separate `anon_id`), not used for tracking.
- **Diagnostics** → Crash Data, Performance Data (Sentry) — linked to
  identity only via the same device-scoped actor tag, not used for
  tracking.
- **Location, Contact Info, Financial Info, Health, Contacts, Browsing
  History, Search History (of other apps), Sensitive Info, User Content**
  → none collected; every one of these categories should be left
  unchecked.
- No data is sold, and none is used for third-party advertising (§16
  privacy baseline) — Apple's "Data Used to Track You" section should be
  empty.

## Google Play Data Safety mapping

Same substance as above in Play's categories: **Device or other IDs**
(collected, not shared, required for app functionality — notification
delivery); **App activity** (analytics events, not linked to
Device/personal identifiers per the separate-`anon_id` design, used for
analytics only); **App info and performance** (crash logs). No location,
personal info (name/email/address), financial info, health, contacts, or
messages categories apply. Data is encrypted in transit (TLS, §16
baseline) and account deletion is available in-app (this ticket's real
`DELETE /v1/me/account`, see `PROGRESS.md`'s T19 entry) — Play's "data
deletion" disclosure question can point directly at
`apps/mobile/src/screens/PrivacyScreen.tsx`.

## Required URLs (must be live and stable per both stores' submission forms)

| URL | Status |
|---|---|
| Privacy policy | `apps/web/src/app/privacy` — live on the public web app |
| Terms of service | `apps/web/src/app/terms` |
| Support / contact | `apps/web/src/app/about` (no dedicated support page/email exists yet — **gap**, see below) |
| Account deletion (public web, required since the app offers deletion) | `apps/web/src/app/account/delete` |
| Account deletion (in-app) | `apps/mobile/src/screens/PrivacyScreen.tsx` (real as of this ticket, not a stub) |
| AI-disclosure (product-specific, not store-required but referenced from the privacy policy) | `apps/web/src/app/ai-disclosure` |

**Gap**: neither store's submission form is satisfied by "an about page" —
both expect a distinct support contact (an email address or a dedicated
support URL). No support email/page exists yet; this needs a real decision
(which inbox, monitored by whom) before submitting to either store, not
something to invent here.

## Store metadata / screenshots

Not produced in this sandbox — screenshots require a running
simulator/device build (same limitation T15 documented: no
Xcode/Android Studio/physical device available here) and store copy is a
product/marketing decision, not an engineering one. Not this ticket's work.

## What this document is not

Not a substitute for actually filling out App Store Connect's privacy
questionnaire or Play Console's Data Safety form — those are structured
forms on each platform with their own exact category names and this
document's job is to make sure whoever fills them out is describing what
the app in this repository actually does, not what an earlier or
aspirational version of it did.
