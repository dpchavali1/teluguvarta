import {
  DefaultTheme,
  NavigationContainer,
  createNavigationContainerRef,
  type LinkingOptions,
  type Theme,
} from "@react-navigation/native";
import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useRef } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { siteUrl, trackEvent } from "./src/lib/api";
import { registerForPushNotificationsAsync, resolveNotificationDeepLink } from "./src/lib/push";
import { StoryCacheProvider } from "./src/lib/StoryCacheContext";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { colors } from "./src/theme/tokens";
import type { RootStackParamList } from "./src/navigation/types";

const navigationTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.text,
    background: colors.bg,
    card: colors.surface,
    text: colors.text,
    border: colors.border,
    notification: colors.accent,
  },
};

const navigationRef = createNavigationContainerRef<RootStackParamList>();

// Design-review fix: sharing a story produced a plain https:// URL that
// couldn't reopen the app even when installed — no scheme/linking config
// existed at all. This wires path -> screen mapping for both the custom
// `teluguglobal://` scheme (works today) and the web origin (works once
// iOS associatedDomains / Android intentFilters + the corresponding
// apple-app-site-association / assetlinks.json are added — that needs the
// real Apple Team ID and Android signing-cert fingerprint, which don't
// exist yet pre-App-Store-Connect/Play-Console registration; deliberately
// not fabricated here). Story/topic slugs map 1:1 with apps/web's routes
// (storyUrl/getTopic), so the same shared link resolves the same way on
// both surfaces.
const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ["teluguglobal://", siteUrl()],
  config: {
    screens: {
      Main: {
        screens: {
          Home: "",
          Search: "search",
          Saved: "saved",
        },
      },
      Topic: "topic/:slug",
      StoryDetail: "story/:slug",
    },
  },
};

// A notification arriving while the app is foregrounded still shows an
// alert/sound — Expo's default is to suppress it, which would make a
// TOPIC_ALERT/BREAKING_ALERT silently invisible if the app happens to be open.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export default function App() {
  const registeredForPush = useRef(false);

  useEffect(() => {
    if (!registeredForPush.current) {
      registeredForPush.current = true;
      registerForPushNotificationsAsync();
      trackEvent("app_open");
    }

    const receivedSub = Notifications.addNotificationReceivedListener((notification) => {
      trackEvent("notification_received", { data: notification.request.content.data });
    });

    // Deep link: opening a tapped notification goes to its story, or falls
    // back to Home if there's no story (DAILY_BRIEFING) or it's since
    // become unavailable (apps/api/app/jobs/notify.py resolves the slug at
    // send time, so a retracted/deleted story already arrives as `null`).
    const responseSub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as Record<string, unknown>;
      trackEvent("notification_open", { data });
      const route = resolveNotificationDeepLink({
        type: data.type as "DAILY_BRIEFING" | "TOPIC_ALERT" | "BREAKING_ALERT" | undefined,
        story_slug: data.story_slug as string | null | undefined,
      });
      if (!navigationRef.isReady()) return;
      if (route.screen === "StoryDetail") {
        navigationRef.navigate("StoryDetail", { slug: route.slug });
      } else {
        navigationRef.navigate("Main", { screen: "Home" });
      }
    });

    return () => {
      receivedSub.remove();
      responseSub.remove();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <StoryCacheProvider>
        <NavigationContainer ref={navigationRef} theme={navigationTheme} linking={linking}>
          <RootNavigator />
          <StatusBar style="auto" />
        </NavigationContainer>
      </StoryCacheProvider>
    </SafeAreaProvider>
  );
}
