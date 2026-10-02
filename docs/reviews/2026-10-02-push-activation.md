# Push delivery diagnosis — 2026-10-02

The production public config returned `push_notifications_enabled: false`.
`app.push.push_enabled()` also requires `EXPO_PUSH_ACCESS_TOKEN`; the deploy
template leaves both disabled/empty. This is a server-side delivery block,
independent of a reader's alert preferences.

The locally built Android app has notification permission granted on the
attached device, but its checked-in `apps/mobile/app.json` has no EAS project
ID. The current APK's registration path skips obtaining an Expo push token
when the ID is missing. The client now also checks Expo's `easConfig` value,
which EAS builds can supply; a locally built APK still needs a configured
project ID and Android FCM credentials. The UI now says when delivery is not
available while continuing to save the reader's choices.

Activation needs these operator-owned steps, in order:

1. Create/link the Expo EAS project and configure the Android FCM V1
   credentials for `org.teluguglobal.app` (and APNs for iOS). Put its public
   project UUID in the app config and the Android `google-services.json` path
   in the native build config. Never commit service-account keys or Expo
   access tokens.
2. Build and install a new native app, grant notification permission, and
   verify that it registers an Expo push token with `POST /v1/me/push-tokens`.
3. Set a private `EXPO_PUSH_ACCESS_TOKEN` in VPS `.env.prod`, then enable
   `PUSH_NOTIFICATIONS_ENABLED=true` and redeploy API/worker. Check the public
   `/v1/config` flag afterward.
4. Send a test notification through Expo to the registered device and verify
   its ticket and delivery receipt. Then verify one normal daily briefing and
   one opted-in topic alert, including quiet-hours/cap behavior and admin
   failure telemetry. Only future eligible alerts are expected; old failed
   notification attempts are not replayed automatically.

Do not flip the server switch before the device credentials and test build
exist: the worker's bounded attempts would consume pending deliveries while
no device can receive them.
