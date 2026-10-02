# Firebase push activation — 2026-10-02

ADR-039 supersedes the earlier Expo/EAS activation path. The Firebase project
`theteluguedit-app` has Android and iOS apps registered under
`org.teluguglobal.app`. A new native build registers FCM tokens. The API
worker now uses FCM HTTP v1, but `PUSH_NOTIFICATIONS_ENABLED` remains false.
The current installed APK still has the old Expo registration code.

To activate after ADR-038's release gate clears:

1. The dedicated `tte-fcm-sender@theteluguedit-app.iam.gserviceaccount.com`
   service account now has only the **Firebase Cloud Messaging API Admin**
   role on `theteluguedit-app`, and FCM API is enabled. Provision its JSON
   credential on the VPS at
   `secrets/firebase-messaging.json` (mode 0400, outside Git). The worker
   mounts this directory read-only at `/run/tte-secrets`. No credential or
   OAuth access token belongs in the app or Git.
2. Add `FCM_PROJECT_ID=theteluguedit-app` and
   `GOOGLE_APPLICATION_CREDENTIALS=/run/tte-secrets/firebase-messaging.json`
   to the existing VPS `.env.prod`; new installs get these defaults. Keep
   `PUSH_NOTIFICATIONS_ENABLED=false` while building and deploying the
   compatible API/worker.
3. Build/install the updated native app on a physical Android device, grant
   OS notification permission, and verify a non-Expo FCM registration in
   `POST /v1/me/push-tokens`. Configure APNs credentials in Firebase before
   testing iOS. Verify that revoking permission prevents registration.
4. With a known test device and the sender credential in place, enable the
   push flag in a controlled test window. Send a test notification through
   the existing Postgres job. Confirm FCM acceptance and actual device
   display/open. Verify a topic alert, quiet hours, daily cap, and invalid
   token deactivation; inspect bounded retries and failure telemetry. Turn
   the flag off if delivery or duplicate behavior differs from expectation.
5. Record device, API revision, outcome, and rollback evidence before
   considering production push live. Existing Expo tokens are never sent to
   FCM and are deactivated when encountered. Future eligible notifications
   are generated normally; failed historical rows are not replayed.

The job records one notification per reader. Acceptance by any active device
completes that reader's handoff, avoiding duplicate alerts on devices that
already accepted it. A transient failure affecting another device is reported
as `PARTIAL_DEVICE_FAILURE`; device-level guaranteed delivery would require
separate durable per-device bookkeeping and a new ticket.
