import {
  DarkTheme,
  DefaultTheme,
  NavigationContainer,
  createNavigationContainerRef,
  type Theme,
} from "@react-navigation/native";
import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useMemo, useRef } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { trackEvent } from "./src/lib/api";
import { initializeMobileAnalytics } from "./src/lib/mobileAnalytics";
import {
  listenForNotificationOpens,
  listenForPushTokenRefresh,
  registerForPushNotificationsAsync,
  resolveNotificationDeepLink,
  type DeepLinkRoute,
} from "./src/lib/push";
import { HiddenTopicsProvider } from "./src/lib/HiddenTopicsContext";
import { StoryCacheProvider } from "./src/lib/StoryCacheContext";
import { linking } from "./src/navigation/linking";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { TextSizeProvider } from "./src/theme/TextSizeContext";
import { ThemePreferenceProvider } from "./src/theme/ThemePreferenceContext";
import { useAppTheme } from "./src/theme/useAppTheme";
import type { RootStackParamList } from "./src/navigation/types";

const navigationRef = createNavigationContainerRef<RootStackParamList>();

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
  // Outside AppContent because AppContent's own useAppTheme reads it.
  return (
    <ThemePreferenceProvider>
      <TextSizeProvider>
        <AppContent />
      </TextSizeProvider>
    </ThemePreferenceProvider>
  );
}

function AppContent() {
  const registeredForPush = useRef(false);
  // A cold-start tap resolves before NavigationContainer is ready; hold the
  // route here and apply it from onReady.
  const pendingRoute = useRef<DeepLinkRoute | null>(null);
  const flushPendingRoute = () => {
    const route = pendingRoute.current;
    if (!route || !navigationRef.isReady()) return;
    pendingRoute.current = null;
    if (route.screen === "StoryDetail") {
      navigationRef.navigate("StoryDetail", { slug: route.slug });
    } else if (route.screen === "Trackers") {
      navigationRef.navigate("Trackers");
    } else {
      navigationRef.navigate("Main", { screen: "Home" });
    }
  };
  // ADR-014: this was a static, light-only Theme, so every native-stack
  // header/background (Topic, StoryDetail, Settings' pushed screens, etc.)
  // ignored system dark mode — the same functional bug as MainTabs' tab
  // bar, just for the stack chrome instead of the tab chrome.
  const { scheme, colors } = useAppTheme();
  const navigationTheme: Theme = useMemo(() => {
    const base = scheme === "dark" ? DarkTheme : DefaultTheme;
    return {
      ...base,
      colors: {
        ...base.colors,
        primary: colors.text,
        background: colors.bg,
        card: colors.surface,
        text: colors.text,
        border: colors.border,
        notification: colors.accent,
      },
    };
  }, [scheme, colors]);

  useEffect(() => {
    if (!registeredForPush.current) {
      registeredForPush.current = true;
      initializeMobileAnalytics().catch(() => undefined);
      registerForPushNotificationsAsync();
    }

    const unsubscribeTokenRefresh = listenForPushTokenRefresh();

    const receivedSub = Notifications.addNotificationReceivedListener((notification) => {
      trackEvent("notification_received", { data: notification.request.content.data });
    });

    // Deep link: opening a tapped notification goes to its story, or falls
    // back to Home if there's no story (DAILY_BRIEFING) or it's since
    // become unavailable (apps/api/app/jobs/notify.py resolves the slug at
    // send time, so a retracted/deleted story already arrives as `null`).
    const stopOpens = listenForNotificationOpens((data) => {
      trackEvent("notification_open", { data });
      pendingRoute.current = resolveNotificationDeepLink(data);
      flushPendingRoute();
    });

    return () => {
      receivedSub.remove();
      stopOpens();
      unsubscribeTokenRefresh();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <StoryCacheProvider>
        <HiddenTopicsProvider>
          <NavigationContainer ref={navigationRef} theme={navigationTheme} linking={linking} onReady={flushPendingRoute}>
            <RootNavigator />
            {/* "auto" follows the system, which is wrong once the reader picks a scheme. */}
            <StatusBar style={scheme === "dark" ? "light" : "dark"} />
          </NavigationContainer>
        </HiddenTopicsProvider>
      </StoryCacheProvider>
    </SafeAreaProvider>
  );
}
