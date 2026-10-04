// A native SDK collects before JS runs, so these native defaults must match
// the JS default in mobileAnalytics.ts (on, per ADR-051).
const firebaseConfig = require("../../firebase.json");
const appConfig = require("../../app.json");

test("Analytics starts on (ADR-051); screen reporting and Messaging auto-init stay off", () => {
  expect(firebaseConfig["react-native"]).toMatchObject({
    app_data_collection_default_enabled: true,
    analytics_auto_collection_enabled: true,
    google_analytics_automatic_screen_reporting_enabled: false,
    messaging_auto_init_enabled: false,
  });
  expect(appConfig.expo.ios.infoPlist.FIREBASE_ANALYTICS_COLLECTION_ENABLED).toBe(true);
});

test("native Firebase files belong to the existing app identifiers", () => {
  const android = require("../../google-services.json");
  const iosPlist = appConfig.expo.ios.googleServicesFile;
  expect(android.project_info.project_id).toBe("theteluguedit-app");
  expect(android.client[0].client_info.android_client_info.package_name).toBe(appConfig.expo.android.package);
  expect(iosPlist).toBe("./GoogleService-Info.plist");
});
