# ADR-039: Firebase for mobile push and analytics

- **Status**: accepted (owner selected Firebase for push and analytics, 2026-10-02)
- **Date**: 2026-10-02
- **Ticket**: T17-firebase

## Context

T17 currently gets Expo push tokens and sends through Expo's push API.
ADR-007 names Expo for push and PostHog for analytics. The locally installed
Android build has no EAS project ID, production has push switched off, and
the owner prefers Firebase for both mobile delivery and mobile analytics.
This amends ADR-007's mobile push and analytics choices without changing its
VPS, Postgres, job-queue, or web analytics decisions.

The SPEC requires separate analytics consent and cross-system deletion. A
Firebase SDK must not start collecting analytics merely because it is included
in a build.

## Decision

1. The mobile app uses native Firebase Cloud Messaging registration tokens.
   Android delivery uses FCM; iOS uses FCM with APNs credentials configured
   in Firebase. The API worker sends through FCM HTTP v1 from the existing
   `notification_dispatch` job. It retains matching, quiet hours, caps,
   deduplication, and the `PUSH_NOTIFICATIONS_ENABLED` kill switch. An Expo
   account or EAS project is not needed for local native builds.
2. Firebase service-account credentials remain only on the VPS, never in the
   app or Git. Native app configuration files contain project identifiers,
   not service-account private keys. No push delivery is enabled until a
   physical-device token, one test send, and its outcome are verified.
3. Firebase Analytics is mobile-only. It starts disabled before SDK startup,
   requires a separate, affirmative reader choice, and can be turned off
   again. Never set Firebase user ID, send authentication tokens, free text,
   search terms, story IDs, or sensitive profile attributes as analytics
   properties. The account-deletion flow disables collection and resets
   Firebase's app analytics identifier. Update the privacy copy before
   enabling collection. Existing server operational logs and web analytics
   remain separate.
4. Keep the accepted ADR-038 dependency gate. A locally tested native build
   does not qualify as a release while the high-severity audit remains red.

## Consequences

The app no longer needs Expo push registration or Expo's sender, but Firebase
native modules and Android/iOS app credentials require a fresh native build.
The Android package and iOS bundle identifiers stay unchanged so an updated
build can replace the current app. Old Expo push-token rows are not sent to
FCM; they can be retired after device re-registration.

Firebase Analytics provides richer mobile usage reports but requires a
separate consent flow and updates to privacy/deletion behavior. Push and
analytics can be implemented and verified in separate changes under this ADR;
neither feature is considered live until its own production evidence exists.

## Alternatives considered

- Keep Expo push and add Firebase Analytics: less push code, but the owner
  selected Firebase for both.
- Send directly to FCM for Android and APNs for iOS: avoids the native
  Firebase messaging module on iOS, but leaves two server transports to
  maintain.
- Enable Firebase Analytics automatically: conflicts with the SPEC's
  separate-consent requirement.
