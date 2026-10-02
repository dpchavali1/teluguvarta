// A native SDK can collect before JS runs. Keep these defaults off even when
// the app is rebuilt or the consent UI changes.
const firebaseConfig = require("../../firebase.json");
const appConfig = require("../../app.json");

test("Firebase collection and Messaging auto-init start disabled", () => {
  expect(firebaseConfig["react-native"]).toMatchObject({
    app_data_collection_default_enabled: false,
    analytics_auto_collection_enabled: false,
    google_analytics_automatic_screen_reporting_enabled: false,
    messaging_auto_init_enabled: false,
  });
  expect(appConfig.expo.ios.infoPlist.FIREBASE_ANALYTICS_COLLECTION_ENABLED).toBe(false);
});

test("native Firebase files belong to the existing app identifiers", () => {
  const android = require("../../google-services.json");
  const iosPlist = appConfig.expo.ios.googleServicesFile;
  expect(android.project_info.project_id).toBe("theteluguedit-app");
  expect(android.client[0].client_info.android_client_info.package_name).toBe(appConfig.expo.android.package);
  expect(iosPlist).toBe("./GoogleService-Info.plist");
});
