# Mobile reader options — plan (2026-09-30)

Owner feedback after installing the R10 build: "no option of light and dark
modes". The app already follows the phone's system setting (`useAppTheme` →
`useColorScheme`, `app.json` `userInterfaceStyle: automatic`), but readers
can't choose it, and Settings has only Notifications, Notification preferences,
Language and Privacy. This plan covers reader-facing options, ordered by value
per effort. Each item is one session. **M1–M4 done 2026-09-30.**

## Guardrails (from NON_NEGOTIABLES, unchanged)

- Everything here is on-device preference (`lib/storage.ts`, AsyncStorage).
  No login, no account sync, no new backend profile. Browsing never depends on
  any of it.
- "Delete my data" (Privacy screen) must clear every new key. Add each key to
  that path and its test.
- No comments/UGC. "Feedback" means the existing private reader-report path
  (ADR-029), not public posts.
- A new native module means a rebuilt APK (and `expo prebuild`); say so per item.

## Now (no ADR, JS-only, small)

**M1 — Appearance: System / Light / Dark.** New `themePreference` key
(default `system`). A `ThemePreferenceProvider` at the root feeds
`useAppTheme`, so every screen that already uses it switches with no per-screen
work. Also: React Navigation theme, `StatusBar` style, and Android's navigation
bar colour follow the chosen scheme, not the system one. Settings → "Appearance"
row with a three-way segmented control. Tests: preference persists, `system`
still tracks `useColorScheme`, delete-data clears it. JS only.

**M2 — Edit my profile and interests.** Today the onboarding answers (country,
home state/city, life stages, student details, interest topics) can't be changed
without reinstalling. Add Settings → "Your profile" that reuses the onboarding
step components in edit mode (no reset of `onboarded`), then refreshes Home's
personalized feed. Biggest customer-facing gap after M1. JS only.

**M3 — Settings basics.** App version and build number, "About The Telugu
Edit", and links to the web privacy policy and terms. JS only. A general
"Report a problem" is **not** in M3: ADR-029 reports are
`POST /v1/stories/{story_id}/reports` with a cascading story FK, so a
story-less report needs an ADR (new endpoint/table, abuse limits) first.

## Next (after the R10 device checks)

The R10 device checks are still owed: large system text, TalkBack/VoiceOver,
poor network, opening from a push, Unicode shared links. Do them on the
Android phone before M4, because M4 changes the same layouts.

**M4 — Reading text size.** Small / Default / Large / Extra large, applied as a
multiplier on top of the system font scale for story body and card text (not
chrome), with Telugu line height tuned separately. The review said compact and
comfortable modes come only after large text passes on a device. JS only.

**M5 — Show less of this.** On a card's overflow: "Hide stories from this
topic", kept on the device and editable in Settings → "Hidden topics". Filters
client-side, and Home and Latest respect it. JS only. A source-level mute needs
source ids on the card payload; check the contract first.

**M6 — Reading history and "read" state.** Dim stories you've opened, add a
"Recently read" list in Saved. On-device, capped (e.g. last 200), cleared by
delete-data. JS only.

## Needs a decision or ADR first

- **Offline saved stories (persisted).** Already flagged in R10: expiry, and how
  corrections and retractions reach a stored copy. ADR before code.
- **Home vs Latest tab layout.** Owner decision (R10 open item).
- **Daily briefing time / digest time.** The time is chosen on the server's
  schedule today. A per-device time needs an API change to push scheduling.
  ADR on the scope.
- **Listen to story (text-to-speech).** `expo-speech` is a new native module
  (APK rebuild). Telugu voice quality varies by device, so test it on the phone
  before committing.
- **iOS build.** The iPhone is paired, but the repo has no iOS release path
  (signing, provisioning). Separate infra task; see `docs/APP_STORE_READINESS.md`.

## Shipping

Each item: tests in `apps/mobile/src/__tests__`, `pnpm typecheck`, `pnpm test`,
`bundle-check`, then a release APK installed on the owner's phone
(`apps/mobile/README.md` command) with the change checked in light and dark.
Update PROGRESS.md per item.
