# apps/mobile — Expo iOS + Android app

See `docs/tickets/T01.md` (scaffold) and `docs/tickets/T15.md` (this app's
real scope).

## Local setup

```
pnpm install
cp ../../.env.example ../../.env   # if you haven't already for apps/api
pnpm --filter @teluguvarta/mobile run start
```

Then press `i` (iOS Simulator) or `a` (Android Emulator) in the Expo CLI, or
scan the QR code with Expo Go on a physical device.

On a physical device, `EXPO_PUBLIC_API_URL` (`.env` at the repo root) must
point at a LAN-reachable address for `apps/api` (not `localhost`), since the
device isn't the same machine running the API.

## Commands

- `pnpm run typecheck` — `tsc --noEmit`.
- `pnpm run test` — Jest + `@testing-library/react-native` (see
  `src/__tests__/smoke.test.tsx`).
- `pnpm run bundle-check` — bundles the app for iOS and Android via Metro
  (`expo export`) without needing Xcode/Android Studio. This is the
  strongest available verification in an environment with no native
  toolchain — it doesn't produce an installable app, but it proves every
  module in the dependency graph resolves and compiles for both platforms.

## Data model

No account/auth backend exists yet for end users (ADR-006 is still
proposed) — onboarding answers, notification preferences, and saved
stories all live on-device (`src/lib/storage.ts`, `@react-native-async-storage/async-storage`),
mirroring the same judgment call `apps/web/src/lib/saved.ts` made for T14.
Swapping in a real account-backed store once ADR-006 ships is additive, not
a breaking change.
