# T17-firebase — native Firebase push, then consented mobile analytics

Owner-selected follow-up to T17 on 2026-10-02. Depends on accepted ADR-039.

1. Replace Expo push tokens and sender with native Firebase Messaging tokens
   and FCM HTTP v1. Keep the existing Postgres notification job, topic and
   breaking gates, quiet hours, cap, dedupe, and bounded retries. Handle
   invalid tokens and provider errors without marking a failed handoff sent.
2. Register Android/iOS apps in a Firebase project, configure native app files
   and server service-account access without committing private keys. Build
   and test on a physical device before enabling the server kill switch.
3. Add Firebase Analytics to the mobile app with collection disabled at native
   startup. Add separate opt-in/out, minimal events, deletion reset, privacy
   copy, and consent tests. Keep web analytics separate.

Acceptance: unit tests for sender success/failure/invalid tokens and consent
default-off/revocation; mobile typecheck/tests/native build; API lint/typecheck
and scoped tests; physical-device token registration and test delivery;
production push flag and delivery evidence. Analytics release also needs
privacy/consent verification. ADR-038's security gate remains blocking.
